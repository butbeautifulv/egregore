from __future__ import annotations

import pytest

from cys_core.application.use_cases.run_worker_job import (
    _CONSULTANT_FINDING_NUDGE,
    _EMIT_FINDING_NUDGE,
    _SIEM_FINDING_NUDGE,
)
from cys_core.application.workers.timeout_salvage import _LADDER_BLOCK_MARKERS
from cys_core.middleware.tool_ladder_middleware import (
    _MSG_CONSULTANT_LADDER_COMPLETE,
    _MSG_SIEM_LADDER_COMPLETE,
    _MSG_SIEM_REPEAT_BLOCKED,
    _MSG_SIEM_VEIL_LADDER_COMPLETE,
    _MSG_VEIL_BUDGET_EXHAUSTED,
)

# timeout_salvage._is_ladder_block_output() filters cached tool-output previews that are
# just an echo of a ladder-block/nudge message (not real agent progress) out of a salvage
# finding. It matches by substring against _LADDER_BLOCK_MARKERS, which duplicates text
# authored independently in tool_ladder_middleware.py and run_worker_job.py's nudge
# constants. This test fails loudly if the two drift apart instead of silently breaking
# salvage filtering.
_KNOWN_SOURCE_TEXTS = (
    _MSG_SIEM_REPEAT_BLOCKED,
    _MSG_SIEM_VEIL_LADDER_COMPLETE,
    _MSG_SIEM_LADDER_COMPLETE,
    _MSG_VEIL_BUDGET_EXHAUSTED,
    _MSG_CONSULTANT_LADDER_COMPLETE,
    _SIEM_FINDING_NUDGE,
    _EMIT_FINDING_NUDGE,
    _CONSULTANT_FINDING_NUDGE,
)

@pytest.mark.unit
def test_ladder_block_markers_match_a_known_source_text() -> None:
    unmatched = [
        marker
        for marker in _LADDER_BLOCK_MARKERS
        if not any(marker in source for source in _KNOWN_SOURCE_TEXTS)
    ]
    assert not unmatched, (
        f"_LADDER_BLOCK_MARKERS entries with no matching source text (tool_ladder_middleware "
        f"message or run_worker_job nudge changed without updating the other side): {unmatched}"
    )
