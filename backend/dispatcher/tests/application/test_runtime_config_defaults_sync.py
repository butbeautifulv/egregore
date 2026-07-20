from __future__ import annotations

import ast
import inspect

import pytest

from bootstrap.settings import Settings
from cys_core.application import runtime_config

# runtime_config.py mirrors ~60 Settings fields as module-level globals (a facade so
# cys_core.application/domain don't import bootstrap directly — see import-linter's
# no_config_in_domain_application contract). Each mirrored field carries its OWN hardcoded
# default, independent of Settings' default, copied over by configure_from_settings() at
# bootstrap. If the two literals drift (e.g. someone bumps a limit in settings.py but
# forgets runtime_config.py, or vice versa — this happened for triage_recursion_limit
# 15->22), any code path that reads a runtime_config getter before configure_from_settings()
# runs (early import, a test that doesn't bootstrap settings first) silently gets the
# stale default instead of the intended one.
#
# This test statically parses runtime_config.py's module-level `_name: type = literal`
# assignments and compares each against the matching Settings field's default — source-level,
# so it doesn't depend on whether configure_from_settings() has already run in this process.


def _module_level_literal_defaults(module) -> dict[str, object]:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    defaults: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if not name.startswith("_") or node.value is None:
            continue
        try:
            defaults[name[1:]] = ast.literal_eval(node.value)
        except ValueError:
            continue  # non-literal default (e.g. a call) — nothing to statically compare
    return defaults


@pytest.mark.unit
def test_runtime_config_literal_defaults_match_settings_defaults():
    runtime_defaults = _module_level_literal_defaults(runtime_config)
    mismatches = []
    for name, runtime_default in runtime_defaults.items():
        field = Settings.model_fields.get(name)
        if field is None:
            continue  # not every runtime_config global mirrors a Settings field 1:1
        if field.default != runtime_default:
            mismatches.append((name, runtime_default, field.default))
    assert not mismatches, (
        "runtime_config.py hardcoded default disagrees with bootstrap/settings.py "
        f"default (name, runtime_config value, Settings value): {mismatches}"
    )
