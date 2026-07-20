import pytest

from cys_core.domain.messaging import extract_message_content


@pytest.mark.unit
def test_extract_plain_string():
    assert extract_message_content("hello") == "hello"


@pytest.mark.unit
def test_extract_list_blocks():
    content = [{"text": "part1"}, {"text": "part2"}]
    assert extract_message_content(content) == "part1part2"


@pytest.mark.unit
def test_extract_empty_list():
    assert extract_message_content([]) == ""
