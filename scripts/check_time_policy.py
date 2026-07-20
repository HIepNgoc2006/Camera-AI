"""Validate the versioned time policy and sanitized compatibility fixtures."""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Never
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

POLICY_PATH = Path("packages/time-policy/time-policy-v1.json")
FIXTURE_PATH = Path("packages/test-fixtures/ansvis/timestamps.synthetic.json")
SYNTHETIC_MARKER = "SYNTHETIC_TEST_DATA_ONLY"

TIME_POLICY_INVALID = "TIME_POLICY_INVALID"
TIME_TIMESTAMP_INVALID = "TIME_TIMESTAMP_INVALID"
TIME_TIMESTAMP_NAIVE = "TIME_TIMESTAMP_NAIVE"
TIME_OFFSET_UNKNOWN = "TIME_OFFSET_UNKNOWN"
TIME_FRACTION_PRECISION = "TIME_FRACTION_PRECISION"
TIME_EVENT_FUTURE = "TIME_EVENT_FUTURE"
TIME_REPLAY_WINDOW_EXCEEDED = "TIME_REPLAY_WINDOW_EXCEEDED"
TIME_LOCAL_AMBIGUOUS = "TIME_LOCAL_AMBIGUOUS"
TIME_LOCAL_NONEXISTENT = "TIME_LOCAL_NONEXISTENT"
TIME_TIMEZONE_INVALID = "TIME_TIMEZONE_INVALID"
TIME_TIMEZONE_UNAPPROVED = "TIME_TIMEZONE_UNAPPROVED"
TIME_SOURCE_UNHEALTHY = "TIME_SOURCE_UNHEALTHY"

RFC3339_WITH_OFFSET = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?(?P<offset>Z|[+-]\d{2}:\d{2})$"
)
RFC3339_NAIVE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$")
LOCAL_WALL_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
STABLE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
ERROR_CODE = re.compile(r"^TIME_[A-Z0-9_]{2,63}$")


class TimePolicyError(ValueError):
    """Fail with a stable code without returning rejected fixture content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str = TIME_POLICY_INVALID) -> Never:
    raise TimePolicyError(code)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail()
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        _fail()
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        _fail()
    return value


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail()
    result = float(value)
    if not math.isfinite(result):
        _fail()
    return result


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail()
    return value


def _load_json(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _fail()
    return _mapping(value)


@dataclass(frozen=True, slots=True)
class TimePolicy:
    policy_version: str
    default_business_timezone: str
    max_fractional_digits: int
    warning_offset_seconds: float
    critical_offset_seconds: float
    future_tolerance_seconds: float
    replay_window_seconds: float
    nonce_retention_seconds: float
    stable_error_codes: frozenset[str]


def parse_rfc3339(value: object, max_fractional_digits: int) -> datetime:
    """Parse the strict project profile and return a UTC-aware instant."""

    if not isinstance(value, str):
        _fail(TIME_TIMESTAMP_INVALID)
    match = RFC3339_WITH_OFFSET.fullmatch(value)
    if match is None:
        if RFC3339_NAIVE.fullmatch(value) is not None:
            _fail(TIME_TIMESTAMP_NAIVE)
        _fail(TIME_TIMESTAMP_INVALID)
    if match.group("offset") == "-00:00":
        _fail(TIME_OFFSET_UNKNOWN)
    fraction = match.group("fraction")
    if fraction is not None and len(fraction) - 1 > max_fractional_digits:
        _fail(TIME_FRACTION_PRECISION)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(TIME_TIMESTAMP_INVALID)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(TIME_TIMESTAMP_NAIVE)
    return parsed.astimezone(UTC)


def canonical_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        _fail(TIME_TIMESTAMP_NAIVE)
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_policy(document: dict[str, object]) -> TimePolicy:
    expected_top_level = {
        "policy_id",
        "policy_version",
        "status",
        "owner_code",
        "approver_code",
        "purpose_code",
        "data_class",
        "effective_at",
        "expiry_trigger",
        "terminal_action",
        "transport_timezone",
        "persistence_timezone",
        "default_business_timezone",
        "timezone_config_version",
        "timestamp_profile",
        "clock_health",
        "event_validation",
        "stable_error_codes",
    }
    if set(document) != expected_top_level:
        _fail()
    fixed_values = {
        "policy_id": "camera_event_time",
        "policy_version": "time_policy_v1",
        "status": "active",
        "owner_code": "platform_operations",
        "approver_code": "project_owner",
        "purpose_code": "event_integrity",
        "data_class": "high",
        "expiry_trigger": "superseded_or_security_change",
        "terminal_action": "retire_and_replace",
        "transport_timezone": "UTC",
        "persistence_timezone": "UTC",
        "default_business_timezone": "Asia/Ho_Chi_Minh",
        "timezone_config_version": "school_timezone_v1",
    }
    if any(document.get(key) != value for key, value in fixed_values.items()):
        _fail()
    parse_rfc3339(document.get("effective_at"), 6)

    profile = _mapping(document.get("timestamp_profile"))
    if profile != {
        "format": "RFC3339",
        "offset_required": True,
        "uppercase_designators_required": True,
        "unknown_offset_allowed": False,
        "leap_second_allowed": False,
        "max_fractional_digits": 6,
        "canonical_utc_suffix": "Z",
    }:
        _fail()

    health = _mapping(document.get("clock_health"))
    expected_health = {
        "sample_interval_seconds": 60,
        "warning_offset_seconds": 1,
        "critical_offset_seconds": 5,
        "warning_consecutive_samples": 3,
        "recovery_consecutive_samples": 5,
    }
    if health != expected_health:
        _fail()

    event = _mapping(document.get("event_validation"))
    expected_event = {
        "future_tolerance_seconds": 30,
        "replay_window_seconds": 300,
        "nonce_retention_seconds": 600,
    }
    if event != expected_event:
        _fail()

    codes = _mapping(document.get("stable_error_codes"))
    expected_codes = {
        "timestamp_invalid": TIME_TIMESTAMP_INVALID,
        "timestamp_naive": TIME_TIMESTAMP_NAIVE,
        "offset_unknown": TIME_OFFSET_UNKNOWN,
        "fraction_precision": TIME_FRACTION_PRECISION,
        "event_future": TIME_EVENT_FUTURE,
        "replay_window_exceeded": TIME_REPLAY_WINDOW_EXCEEDED,
        "local_ambiguous": TIME_LOCAL_AMBIGUOUS,
        "local_nonexistent": TIME_LOCAL_NONEXISTENT,
        "timezone_invalid": TIME_TIMEZONE_INVALID,
        "timezone_unapproved": TIME_TIMEZONE_UNAPPROVED,
        "source_unhealthy": TIME_SOURCE_UNHEALTHY,
    }
    if codes != expected_codes:
        _fail()
    code_values = frozenset(_text(value) for value in expected_codes.values())
    if len(code_values) != len(codes) or any(
        ERROR_CODE.fullmatch(code) is None for code in code_values
    ):
        _fail()

    try:
        ZoneInfo(_text(document["default_business_timezone"]))
    except ZoneInfoNotFoundError:
        _fail(TIME_TIMEZONE_INVALID)

    return TimePolicy(
        policy_version=_text(document["policy_version"]),
        default_business_timezone=_text(document["default_business_timezone"]),
        max_fractional_digits=_integer(profile["max_fractional_digits"]),
        warning_offset_seconds=_number(health["warning_offset_seconds"]),
        critical_offset_seconds=_number(health["critical_offset_seconds"]),
        future_tolerance_seconds=_number(event["future_tolerance_seconds"]),
        replay_window_seconds=_number(event["replay_window_seconds"]),
        nonce_retention_seconds=_number(event["nonce_retention_seconds"]),
        stable_error_codes=code_values,
    )


def clock_health_state(offset_seconds: object, policy: TimePolicy) -> str:
    offset = abs(_number(offset_seconds))
    if offset <= policy.warning_offset_seconds:
        return "healthy"
    if offset <= policy.critical_offset_seconds:
        return "warning"
    return "critical"


def evaluate_event_case(case: dict[str, object], policy: TimePolicy) -> tuple[str, str]:
    try:
        event_time = parse_rfc3339(case.get("vendor_event_time"), policy.max_fractional_digits)
        receipt_time = parse_rfc3339(case.get("server_received_at"), policy.max_fractional_digits)
    except TimePolicyError as error:
        return "reject", error.code
    delta = (event_time - receipt_time).total_seconds()
    if delta > policy.future_tolerance_seconds:
        return "reject", TIME_EVENT_FUTURE
    if delta < -policy.replay_window_seconds:
        return "reject", TIME_REPLAY_WINDOW_EXCEEDED
    return "accept", canonical_utc(event_time)


def _zone(value: object) -> ZoneInfo:
    try:
        return ZoneInfo(_text(value))
    except ZoneInfoNotFoundError:
        _fail(TIME_TIMEZONE_INVALID)


def _local_candidates(local_time: datetime, zone: ZoneInfo) -> list[datetime]:
    candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = local_time.replace(tzinfo=zone, fold=fold)
        round_trip = candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if round_trip == local_time and all(
            candidate.utcoffset() != existing.utcoffset() for existing in candidates
        ):
            candidates.append(candidate)
    return candidates


def evaluate_timezone_case(case: dict[str, object], policy: TimePolicy) -> tuple[str, str]:
    try:
        zone = _zone(case.get("timezone"))
        operation = _text(case.get("operation"))
        if operation == "utc_to_business":
            instant = parse_rfc3339(case.get("input_utc"), policy.max_fractional_digits)
            return "accept", instant.astimezone(zone).isoformat(timespec="microseconds")
        if operation != "local_to_utc":
            _fail()
        raw_local = _text(case.get("local_time"))
        if LOCAL_WALL_TIME.fullmatch(raw_local) is None:
            _fail(TIME_TIMESTAMP_INVALID)
        local_time = datetime.fromisoformat(raw_local)
        candidates = _local_candidates(local_time, zone)
        if not candidates:
            _fail(TIME_LOCAL_NONEXISTENT)
        if len(candidates) == 1:
            return "accept", canonical_utc(candidates[0])
        disambiguation = case.get("disambiguation")
        if disambiguation not in {"earlier_instant", "later_instant"}:
            _fail(TIME_LOCAL_AMBIGUOUS)
        ordered = sorted(candidates, key=lambda item: item.astimezone(UTC))
        selected = ordered[0] if disambiguation == "earlier_instant" else ordered[-1]
        return "accept", canonical_utc(selected)
    except TimePolicyError as error:
        return "reject", error.code


def _validate_expected(case: dict[str, object], actual: tuple[str, str]) -> None:
    case_code = _text(case.get("case_code"))
    if STABLE_CODE.fullmatch(case_code) is None:
        _fail()
    expected_result = _text(case.get("expected_result"))
    if expected_result not in {"accept", "reject"} or actual[0] != expected_result:
        _fail()
    expected_value = case.get("expected_utc", case.get("expected_local"))
    if expected_result == "accept":
        if not isinstance(expected_value, str) or actual[1] != expected_value:
            _fail()
    elif actual[1] != _text(case.get("expected_error_code")):
        _fail()


def validate_fixture(document: dict[str, object], policy: TimePolicy) -> int:
    if document.get("_fixture") != SYNTHETIC_MARKER:
        _fail()
    if document.get("policy_version") != policy.policy_version:
        _fail()
    event_cases = _list(document.get("event_timestamp_cases"))
    timezone_cases = _list(document.get("timezone_cases"))
    health_cases = _list(document.get("clock_health_cases"))
    if len(event_cases) < 10 or len(timezone_cases) < 5 or len(health_cases) < 5:
        _fail()
    for item in event_cases:
        case = _mapping(item)
        _validate_expected(case, evaluate_event_case(case, policy))
    for item in timezone_cases:
        case = _mapping(item)
        _validate_expected(case, evaluate_timezone_case(case, policy))
    for item in health_cases:
        case = _mapping(item)
        case_code = _text(case.get("case_code"))
        if STABLE_CODE.fullmatch(case_code) is None:
            _fail()
        actual = clock_health_state(case.get("absolute_offset_seconds"), policy)
        if actual != _text(case.get("expected_state")):
            _fail()
    return len(event_cases) + len(timezone_cases) + len(health_cases)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        policy = validate_policy(_load_json(repo_root / POLICY_PATH))
        case_count = validate_fixture(_load_json(repo_root / FIXTURE_PATH), policy)
    except TimePolicyError as error:
        print(f"time_policy=FAIL code={error.code}", file=sys.stderr)
        return 1
    print("time_policy=PASS")
    print(f"policy_version={policy.policy_version}")
    print(f"synthetic_cases_checked={case_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
