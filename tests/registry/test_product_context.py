from cys_core.registry.product_context import ProductContext


def test_product_context_loads_manifest_and_rules():
    ctx = ProductContext()
    assert ctx.manifest.name == "cys-agi"
    assert ctx.manifest.default_plan == "full-assessment"
    assert "Security rules" in ctx.rules_block or "security" in ctx.rules_block.lower()
    assert ctx.personas_dir.is_dir()
    assert ctx.skills_dir.is_dir()


def test_rules_augment_prompt():
    ctx = ProductContext()
    augmented = ctx.augment_prompt("Base prompt.")
    assert "Base prompt." in augmented
    assert "## Global rules" in augmented
