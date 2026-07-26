"""Migration helpers that keep ciphertext columns from accepting arbitrary bytes.

A `bytea NOT NULL` column with only an `octet_length(...) > 0` constraint accepts plaintext and
still looks correct in review. The check below additionally requires the ENCV1 magic prefix, so a
write that skipped the encryption runtime is rejected by the database itself.
"""

from __future__ import annotations

import re

from .envelope import ENVELOPE_MAGIC

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_MIN_ENVELOPE_BYTES = 64


def _magic_literal() -> str:
    return "\\x" + ENVELOPE_MAGIC.hex()


def encv1_prefix_check(column: str) -> str:
    """Return the SQL boolean expression asserting a column holds an ENCV1 envelope."""

    if _IDENTIFIER_PATTERN.fullmatch(column) is None:
        raise ValueError("invalid column identifier")
    prefix_length = len(ENVELOPE_MAGIC)
    return (
        f"substring({column} from 1 for {prefix_length}) = '{_magic_literal()}'::bytea"
        f" AND octet_length({column}) >= {_MIN_ENVELOPE_BYTES}"
    )


def encv1_check_constraint(table: str, column: str) -> tuple[str, str]:
    """Return the `(constraint_name, condition)` pair for an ENCV1 ciphertext column."""

    if _IDENTIFIER_PATTERN.fullmatch(table) is None:
        raise ValueError("invalid table identifier")
    return f"ck_{table}_{column}_encv1", encv1_prefix_check(column)
