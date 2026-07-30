"""Allowlisted logging fields."""

ALLOWED_FIELDS = frozenset(
    {
        "request_id",
        "correlation_id",
        "service_name",
        "environment",
        "action",
        "outcome",
        "row_count",
        "state",
        "error_code",
    }
)


def safe_log_fields(**values: object) -> dict[str, object]:
    return {name: value for name, value in values.items() if name in ALLOWED_FIELDS}
