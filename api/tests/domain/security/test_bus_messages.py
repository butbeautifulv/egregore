from __future__ import annotations

import pytest

from cys_core.domain.security.bus_messages import (
    MESSAGE_CONTROL,
    MESSAGE_DELEGATE,
    MESSAGE_ESCALATION,
    MESSAGE_FINDING,
    MESSAGE_REPORT,
    MESSAGE_REVISION,
    BusMessageType,
)


@pytest.mark.unit
def test_bus_message_type_values() -> None:
    assert BusMessageType.FINDING == "finding"
    assert BusMessageType.ESCALATION == "escalation"


@pytest.mark.unit
def test_bus_message_backward_compatible_aliases() -> None:
    assert MESSAGE_FINDING == BusMessageType.FINDING.value
    assert MESSAGE_DELEGATE == BusMessageType.DELEGATE.value
    assert MESSAGE_REVISION == BusMessageType.REVISION.value
    assert MESSAGE_ESCALATION == BusMessageType.ESCALATION.value
    assert MESSAGE_CONTROL == BusMessageType.CONTROL.value
    assert MESSAGE_REPORT == BusMessageType.REPORT.value
