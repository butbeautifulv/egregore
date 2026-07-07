from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "cys_core"
APPLICATION = CORE / "application"
REGISTRY = CORE / "registry"
DOMAIN = CORE / "domain"

# --- Shrink-only allowlists (may only decrease in size; see tests/architecture/test_layer_contracts.py) ---

# Phase 4: tool gateway inversion (resolved)
ALLOWLIST_APPLICATION_INTERFACES: frozenset[str] = frozenset()

# Phase 7: config/DI migration for application bootstrap imports (resolved)
ALLOWLIST_APPLICATION_BOOTSTRAP: frozenset[str] = frozenset()

# Phase 5: catalog/registry ports (resolved)
ALLOWLIST_APPLICATION_INFRASTRUCTURE: frozenset[str] = frozenset()

ALLOWLIST_APPLICATION_REGISTRY: frozenset[str] = frozenset()

# Phase 7: observability ports (resolved)
ALLOWLIST_APPLICATION_OBSERVABILITY: frozenset[str] = frozenset()

# Phase 6: resolved — parse_json_text moved to domain; worker pipeline split
ALLOWLIST_APPLICATION_RUNTIME: frozenset[str] = frozenset()

# Phase 4 + Phase 7: cys_core → bootstrap/interfaces (infra settings, registry tool adapters)
ALLOWLIST_BOOTSTRAP_INTERFACES: frozenset[str] = frozenset(
    {
        "cys_core/benchmarks/gaia_pipeline.py",
        "cys_core/infrastructure/auth/broker.py",
        "cys_core/infrastructure/auth/factory.py",
        "cys_core/infrastructure/bootstrap/application_settings_adapter.py",
        "cys_core/infrastructure/bootstrap/catalog_seed_adapter.py",
        "cys_core/infrastructure/bootstrap/policy_defaults_adapter.py",
        "cys_core/infrastructure/bootstrap/product_pack_adapter.py",
        "cys_core/infrastructure/bus_transport.py",
        "cys_core/infrastructure/engagement/factory.py",
        "cys_core/infrastructure/catalog/catalog_registry.py",
        "cys_core/infrastructure/job_store/factory.py",
        "cys_core/infrastructure/k8s_sandbox.py",
        "cys_core/infrastructure/kafka_audit.py",
        "cys_core/infrastructure/kafka_bus.py",
        "cys_core/infrastructure/kafka_bus_events.py",
        "cys_core/infrastructure/kafka_control_events.py",
        "cys_core/infrastructure/kafka_events.py",
        "cys_core/infrastructure/kafka_paused.py",
        "cys_core/infrastructure/kafka_publisher.py",
        "cys_core/infrastructure/kafka_queue.py",
        "cys_core/infrastructure/memory/factory.py",
        "cys_core/infrastructure/queue.py",
        "cys_core/infrastructure/rag/retrieve.py",
        "cys_core/infrastructure/rag/store.py",
        "cys_core/infrastructure/sandbox.py",
        "cys_core/infrastructure/tools/adapters/search_stack.py",
        "cys_core/infrastructure/tools/adapters/siem.py",
        "cys_core/middleware/security_middleware.py",
        "cys_core/observability/logging_setup.py",
        "cys_core/observability/otel_provider.py",
        "cys_core/observability/platform_gauges.py",
        "cys_core/persistence.py",
        "cys_core/registry/discovery_tools.py",
        "cys_core/registry/mcp_tools.py",
        "cys_core/registry/product_context.py",
        "cys_core/registry/skills_tool.py",
        "cys_core/registry/tools.py",
        "cys_core/registry/veil_tools.py",
        "cys_core/registry/siem_tools.py",
        "cys_core/security/rate_limit.py",
    }
)

# Phase 4 audit: interfaces/api → infrastructure (health probe only)
ALLOWLIST_INTERFACES_API_INFRASTRUCTURE: frozenset[str] = frozenset(
    {
        "interfaces/api/app.py",  # lazy infra_health for /health
    }
)

# Phase 4 audit: infrastructure wrapping use cases (shrink toward zero)
ALLOWLIST_INFRASTRUCTURE_USE_CASES: frozenset[str] = frozenset()

# Phase 4: infrastructure tool gateway adapter (resolved)
ALLOWLIST_INFRASTRUCTURE_INTERFACES: frozenset[str] = frozenset()

# Phase 4: registry → interfaces tool gateway (resolved)
ALLOWLIST_REGISTRY_INTERFACES: frozenset[str] = frozenset()

# Backward-compatible alias for tests importing ALLOWLIST
ALLOWLIST = ALLOWLIST_BOOTSTRAP_INTERFACES


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _lazy_module_imports_in_file(path: Path, prefix: str) -> list[str]:
    """Detect imports with given prefix inside function/method bodies."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._depth = 0

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._depth += 1
            self.generic_visit(node)
            self._depth -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._depth += 1
            self.generic_visit(node)
            self._depth -= 1

        def visit_Import(self, node: ast.Import) -> None:
            if self._depth > 0:
                for alias in node.names:
                    if alias.name.startswith(prefix):
                        violations.append(f"lazy {alias.name}")
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if self._depth > 0 and node.module and node.module.startswith(prefix):
                violations.append(f"lazy {node.module}")
            self.generic_visit(node)

    _Visitor().visit(tree)
    return violations


def _lazy_infra_imports_in_file(path: Path) -> list[str]:
    return _lazy_module_imports_in_file(path, "cys_core.infrastructure")


def _domain_plan_filesystem_io(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    flags: list[str] = []
    if "yaml.safe_load" in text or "import yaml" in text:
        flags.append("yaml")
    if "read_text(" in text and "Path" in text:
        flags.append("path_read_text")
    return flags


def _scan_layer(
    root: Path,
    *,
    prefix: str,
    allowlist: frozenset[str],
) -> list[str]:
    violations: list[str] = []
    if not root.exists():
        return violations
    for path in root.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowlist:
            continue
        for mod in _imports_in_file(path):
            if mod.startswith(prefix):
                violations.append(f"{rel}: {mod}")
    return violations


def check_bootstrap_interfaces() -> list[str]:
    violations: list[str] = []
    for path in CORE.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST_BOOTSTRAP_INTERFACES:
            continue
        for mod in _imports_in_file(path):
            if mod.startswith("bootstrap.") or mod.startswith("interfaces."):
                violations.append(f"{rel}: {mod}")
    return violations


def check_application_no_interfaces() -> list[str]:
    return _scan_layer(APPLICATION, prefix="interfaces.", allowlist=ALLOWLIST_APPLICATION_INTERFACES)


def check_application_no_bootstrap() -> list[str]:
    return _scan_layer(APPLICATION, prefix="bootstrap.", allowlist=ALLOWLIST_APPLICATION_BOOTSTRAP)


def check_application_no_infrastructure() -> list[str]:
    return _scan_layer(
        APPLICATION,
        prefix="cys_core.infrastructure.",
        allowlist=ALLOWLIST_APPLICATION_INFRASTRUCTURE,
    )


def check_application_no_registry() -> list[str]:
    return _scan_layer(APPLICATION, prefix="cys_core.registry.", allowlist=ALLOWLIST_APPLICATION_REGISTRY)


def check_application_no_observability() -> list[str]:
    return _scan_layer(
        APPLICATION,
        prefix="cys_core.observability.",
        allowlist=ALLOWLIST_APPLICATION_OBSERVABILITY,
    )


def check_application_no_runtime() -> list[str]:
    return _scan_layer(APPLICATION, prefix="cys_core.runtime.", allowlist=ALLOWLIST_APPLICATION_RUNTIME)


def check_registry_no_interfaces() -> list[str]:
    return _scan_layer(REGISTRY, prefix="interfaces.", allowlist=ALLOWLIST_REGISTRY_INTERFACES)


def check_infrastructure_no_interfaces() -> list[str]:
    infra = CORE / "infrastructure"
    return _scan_layer(infra, prefix="interfaces.", allowlist=ALLOWLIST_INFRASTRUCTURE_INTERFACES)


def check_interfaces_api_no_infrastructure() -> list[str]:
    """interfaces/api routers should not import infrastructure (except health in app.py)."""
    violations: list[str] = []
    api_root = ROOT / "interfaces" / "api"
    if not api_root.exists():
        return violations
    for path in api_root.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST_INTERFACES_API_INFRASTRUCTURE:
            continue
        for mod in _imports_in_file(path):
            if mod.startswith("cys_core.infrastructure."):
                violations.append(f"{rel}: {mod}")
        for mod in _lazy_infra_imports_in_file(path):
            violations.append(f"{rel}: {mod}")
    return violations


def check_infrastructure_no_use_cases() -> list[str]:
    """Infrastructure adapters should not import application use cases (hexagon inversion)."""
    violations: list[str] = []
    infra = CORE / "infrastructure"
    if not infra.exists():
        return violations
    for path in infra.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST_INFRASTRUCTURE_USE_CASES:
            continue
        for mod in _imports_in_file(path):
            if mod.startswith("cys_core.application.use_cases."):
                violations.append(f"{rel}: {mod}")
    return violations


def check_application_ports_no_infrastructure() -> list[str]:
    """Ports must depend on domain only; adapters live in infrastructure."""
    violations: list[str] = []
    ports_root = CORE / "application" / "ports"
    if not ports_root.exists():
        return violations
    for path in ports_root.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        for mod in _imports_in_file(path):
            if mod.startswith("cys_core.infrastructure.") or mod.startswith("bootstrap."):
                violations.append(f"{rel}: {mod}")
            if mod.startswith("interfaces."):
                violations.append(f"{rel}: {mod}")
    return violations


def check_domain_no_infrastructure() -> list[str]:
    violations: list[str] = []
    if not DOMAIN.exists():
        return violations
    for path in DOMAIN.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        for mod in _imports_in_file(path):
            if mod.startswith("cys_core.infrastructure."):
                violations.append(f"{rel}: {mod}")
        for mod in _lazy_infra_imports_in_file(path):
            violations.append(f"{rel}: lazy {mod}")
    return violations


def check_domain_no_plan_filesystem_io() -> list[str]:
    violations: list[str] = []
    if not DOMAIN.exists():
        return violations
    for path in DOMAIN.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        flags = _domain_plan_filesystem_io(path)
        if flags:
            violations.append(f"{rel}: {','.join(flags)}")
    return violations


def _print_bucket(name: str, violations: list[str], deferred: int) -> bool:
    if violations:
        print(f"FAIL {name}:")
        for line in sorted(violations):
            print(f"  {line}")
        return False
    print(f"OK {name} (deferred: {deferred} files)")
    return True


def main() -> int:
    checks = [
        ("bootstrap/interfaces in cys_core", check_bootstrap_interfaces(), len(ALLOWLIST_BOOTSTRAP_INTERFACES)),
        ("application → interfaces", check_application_no_interfaces(), len(ALLOWLIST_APPLICATION_INTERFACES)),
        ("application → bootstrap", check_application_no_bootstrap(), len(ALLOWLIST_APPLICATION_BOOTSTRAP)),
        ("application → infrastructure", check_application_no_infrastructure(), len(ALLOWLIST_APPLICATION_INFRASTRUCTURE)),
        ("application → registry", check_application_no_registry(), len(ALLOWLIST_APPLICATION_REGISTRY)),
        ("application → observability", check_application_no_observability(), len(ALLOWLIST_APPLICATION_OBSERVABILITY)),
        ("application → runtime", check_application_no_runtime(), len(ALLOWLIST_APPLICATION_RUNTIME)),
        ("registry → interfaces", check_registry_no_interfaces(), len(ALLOWLIST_REGISTRY_INTERFACES)),
        (
            "infrastructure → interfaces",
            check_infrastructure_no_interfaces(),
            len(ALLOWLIST_INFRASTRUCTURE_INTERFACES),
        ),
        (
            "interfaces/api → infrastructure",
            check_interfaces_api_no_infrastructure(),
            len(ALLOWLIST_INTERFACES_API_INFRASTRUCTURE),
        ),
        (
            "infrastructure → application.use_cases",
            check_infrastructure_no_use_cases(),
            len(ALLOWLIST_INFRASTRUCTURE_USE_CASES),
        ),
    ]
    port_violations = check_application_ports_no_infrastructure()
    checks.append(
        (
            "application ports → infrastructure/bootstrap/interfaces",
            port_violations,
            0,
        )
    )
    checks.append(("domain → infrastructure", check_domain_no_infrastructure(), 0))
    checks.append(("domain plan filesystem I/O", check_domain_no_plan_filesystem_io(), 0))

    ok = True
    print("Architecture import boundary summary:")
    for name, violations, deferred in checks:
        if not _print_bucket(name, violations, deferred):
            ok = False

    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
