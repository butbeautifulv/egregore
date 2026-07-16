from __future__ import annotations

from pathlib import Path

import yaml

from cys_core.domain.events.plans import PlanRoutingConfig, parse_plan_routing_from_dict


def load_plan_routing(path: Path) -> PlanRoutingConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return parse_plan_routing_from_dict(data, plan_id=path.stem)


def load_plans_from_dir(plans_dir: Path) -> list[PlanRoutingConfig]:
    if not plans_dir.is_dir():
        return []
    configs: list[PlanRoutingConfig] = []
    for path in sorted(plans_dir.glob("*.yaml")):
        configs.append(load_plan_routing(path))
    return configs
