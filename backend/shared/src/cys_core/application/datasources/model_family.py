from __future__ import annotations

from cys_core.domain.datasources.schema_models import ModelFamily, ModelFamilyKnobs, SchemaExportOptions


def knobs_for_model_family(family: ModelFamily | str = ModelFamily.GENERIC) -> ModelFamilyKnobs:
    resolved = ModelFamily(family) if isinstance(family, str) else family
    if resolved == ModelFamily.OPENAI:
        return ModelFamilyKnobs(
            family=ModelFamily.OPENAI,
            strict_additional_properties=True,
            normalize_required=True,
            reject_unknown_args=True,
        )
    return ModelFamilyKnobs(family=ModelFamily.GENERIC)


def export_options_for_family(family: ModelFamily | str = ModelFamily.GENERIC) -> SchemaExportOptions:
    knobs = knobs_for_model_family(family)
    return SchemaExportOptions(
        strict_additional_properties=knobs.strict_additional_properties,
        normalize_required=knobs.normalize_required,
    )
