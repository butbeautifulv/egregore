from __future__ import annotations

import pytest


@pytest.mark.unit
def test_product_context_defaults_rules_and_paths(tmp_path, monkeypatch):
    from cys_core.registry import product_context

    root = tmp_path / "product"
    root.mkdir()
    ctx = product_context.ProductContext(root)
    assert ctx.manifest.name == "cys-agi"
    assert ctx.rules_block == ""
    augmented = ctx.augment_prompt("base")
    assert "SYSTEM_INSTRUCTIONS:" in augmented
    assert "base" in augmented
    assert "SECURITY_RULES:" in augmented
    assert ctx.skills_path == str(root / "skills")

    rules_root = tmp_path / "rules-product"
    (rules_root / "rules").mkdir(parents=True)
    (rules_root / "rules" / "README.md").write_text("skip", encoding="utf-8")
    ctx_empty_rules = product_context.ProductContext(rules_root)
    assert ctx_empty_rules.rules_block == ""

    (rules_root / "manifest.yaml").write_text(
        'name: custom\nversion: "2.0"\ndescription: desc\ndefault_plan: plan-a\n',
        encoding="utf-8",
    )
    (rules_root / "rules" / "security.md").write_text("No secrets", encoding="utf-8")
    ctx_with_rules = product_context.ProductContext(rules_root)
    assert ctx_with_rules.manifest.default_plan == "plan-a"
    assert "## Global rules" in ctx_with_rules.augment_prompt("base")

    monkeypatch.setattr(product_context.settings, "agents_root", str(rules_root))
    product_context.get_product_context.cache_clear()
    try:
        assert product_context.default_agents_root() == rules_root
        assert product_context.get_product_context().manifest.name == "custom"
    finally:
        product_context.get_product_context.cache_clear()
