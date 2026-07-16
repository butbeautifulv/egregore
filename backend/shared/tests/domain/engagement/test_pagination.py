from __future__ import annotations

import pytest

from cys_core.domain.engagement.pagination import InvalidListCursor


@pytest.mark.unit
def test_invalid_list_cursor_is_value_error() -> None:
    with pytest.raises(InvalidListCursor, match="cursor"):
        raise InvalidListCursor("cursor cannot be decoded")
