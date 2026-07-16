from __future__ import annotations

import pytest
from api_gateway.api.request_id import REQUEST_ID_PATTERN, select_request_id


@pytest.mark.parametrize("candidate", ["req-123", "abc.DEF:123", "A", "x" * 64])
def test_select_request_id_preserves_one_valid_value(candidate: str) -> None:
    assert select_request_id([candidate]) == candidate


@pytest.mark.parametrize(
    "values",
    [
        [],
        ["one", "two"],
        [""],
        [" leading-space"],
        ["line\r\nbreak"],
        ["unicode-đ"],
        ["x" * 65],
    ],
)
def test_select_request_id_replaces_missing_duplicate_or_unsafe_values(values: list[str]) -> None:
    selected = select_request_id(values)

    assert selected not in values
    assert REQUEST_ID_PATTERN.fullmatch(selected) is not None
