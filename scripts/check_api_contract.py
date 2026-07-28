"""Validate the versioned protected API contract and run a client-generation smoke check."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Never

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "audit-log-service" / "src"))

from audit_log_service.domain.policies import APPROVED_ACTIONS  # noqa: E402

type JsonValue = object
type JsonObject = dict[str, object]

OPENAPI_PATH = Path("packages/api-contract/openapi-v1.json")
POLICY_PATH = Path("packages/api-contract/api-contract-policy-v1.json")
ERROR_REGISTRY_PATH = Path("packages/api-contract/error-codes-v1.json")
REVIEW_RECORD_PATH = Path("packages/api-contract/review-record-v1.json")
AUTHORIZATION_CATALOG_PATH = Path("packages/authorization-policy/permission-catalog-v1.json")

API_CONTRACT_INVALID = "API_CONTRACT_INVALID"
API_ERROR_REGISTRY_INVALID = "API_ERROR_REGISTRY_INVALID"
API_CLIENT_SMOKE_FAILED = "API_CLIENT_SMOKE_FAILED"

_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,95}$")
_VERSION = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_OPERATION_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9_-]{8,120}$")
_PATH_VARIABLE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
_SEEDED_CODE = re.compile(r"^(?:ENCRYPTION|LOOKUP|AUTHZ|EVENT|AUDIT|TIME)_[A-Z0-9_]+$")

_REQUIRED_STATUSES = frozenset({"400", "401", "404", "409", "422", "429", "503"})
_LIST_OPERATIONS = frozenset({"attendance.list", "timekeeping.list", "audit.read", "camera.status"})
_GENERIC_PUBLIC_CODES = frozenset(
    {
        "BAD_REQUEST",
        "AUTHENTICATION_REQUIRED",
        "AUTHZ_DENIED",
        "RESOURCE_NOT_FOUND",
        "METHOD_NOT_ALLOWED",
        "IDEMPOTENCY_CONFLICT",
        "VALIDATION_FAILED",
        "RATE_LIMITED",
        "INTERNAL_SERVER_ERROR",
        "SERVICE_UNAVAILABLE",
    }
)
_FORBIDDEN_PROPERTY_NAMES = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "token_hash",
        "secret",
        "api_key",
        "private_key",
        "rtsp_url",
        "face_image",
        "face_crop",
        "face_embedding",
        "embedding",
        "biometric_identifier",
        "raw_payload",
        "payload_raw",
        "raw_ansvis_payload",
        "vendor_payload",
        "storage_key",
        "secret_reference",
        "credential_reference",
        "signed_url",
    }
)
_SEED_SOURCES = (
    Path("packages/crypto-runtime/src/camera_ai_crypto/errors.py"),
    Path("packages/authorization-runtime/src/camera_ai_authorization/models.py"),
    Path("packages/authorization-runtime/src/camera_ai_authorization/catalog.py"),
    Path("packages/authorization-runtime/src/camera_ai_authorization/decision.py"),
    Path("packages/authorization-runtime/src/camera_ai_authorization/audit.py"),
    Path("services/ansvis-adapter/src/ansvis_adapter/api/errors.py"),
    Path("services/audit-log-service/src/audit_log_service/domain/errors.py"),
)


class ApiContractError(ValueError):
    def __init__(self, code: str = API_CONTRACT_INVALID) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RateBucket:
    sustained_rps: int
    burst: int
    retry_after_required: bool


@dataclass(frozen=True, slots=True)
class ContractPolicy:
    policy_version: str
    openapi_version: str
    authorization_policy_version: str
    error_registry_version: str
    required_operation_controls: frozenset[str]
    rate_limit_buckets: dict[str, RateBucket]


@dataclass(frozen=True, slots=True)
class ErrorDefinition:
    code: str
    http_status: int
    retryable: bool
    exposure: str
    redaction_rule: str
    safe_message: str


@dataclass(frozen=True, slots=True)
class ContractSummary:
    policy_version: str
    openapi_version: str
    error_registry_version: str
    operation_count: int
    error_code_count: int
    client_operation_count: int
    client_sha256: str


def _fail(code: str = API_CONTRACT_INVALID) -> Never:
    raise ApiContractError(code)


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def load_json(path: Path) -> JsonObject:
    try:
        value: JsonValue = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: _fail(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail()
    return _mapping(value)


def _mapping(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(code)
    return value


def _list(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> list[JsonValue]:
    if not isinstance(value, list):
        _fail(code)
    return value


def _text(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> str:
    if not isinstance(value, str):
        _fail(code)
    return value


def _integer(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> int:
    if type(value) is not int:
        _fail(code)
    return value


def _boolean(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> bool:
    if type(value) is not bool:
        _fail(code)
    return value


def _texts(value: JsonValue | object, code: str = API_CONTRACT_INVALID) -> tuple[str, ...]:
    values = tuple(_text(item, code) for item in _list(value, code))
    if len(values) != len(set(values)):
        _fail(code)
    return values


def _exact_keys(value: JsonObject, expected: frozenset[str], code: str) -> None:
    if frozenset(value) != expected:
        _fail(code)


def _assert_no_forbidden_properties(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.lower().replace("-", "_") in _FORBIDDEN_PROPERTY_NAMES:
                _fail()
            _assert_no_forbidden_properties(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_properties(child)


def validate_policy(document: JsonObject) -> ContractPolicy:
    expected = frozenset(
        {
            "policy_schema_version",
            "policy_version",
            "status",
            "openapi_version",
            "authorization_policy_version",
            "error_registry_version",
            "base_path",
            "required_operation_controls",
            "versioning",
            "route_naming",
            "pagination",
            "filtering",
            "idempotency",
            "request_id",
            "deprecation",
            "compatibility",
            "rate_limit_buckets",
        }
    )
    _exact_keys(document, expected, API_CONTRACT_INVALID)
    if (
        _integer(document["policy_schema_version"]) != 1
        or _text(document["status"]) != "implementation_baseline_inactive"
        or _text(document["base_path"]) != "/api/v1"
    ):
        _fail()
    policy_version = _text(document["policy_version"])
    error_registry_version = _text(document["error_registry_version"])
    authorization_policy_version = _text(document["authorization_policy_version"])
    if any(
        _VERSION.fullmatch(value) is None
        for value in (policy_version, error_registry_version, authorization_policy_version)
    ):
        _fail()
    openapi_version = _text(document["openapi_version"])
    if openapi_version != "1.0.0":
        _fail()

    required_controls = frozenset(_texts(document["required_operation_controls"]))
    if required_controls != {
        "x-auth-scheme",
        "x-required-permission",
        "x-object-scope",
        "x-audit-action",
        "x-rate-limit-bucket",
    }:
        _fail()

    versioning = _mapping(document["versioning"])
    if versioning != {
        "strategy": "major_path",
        "breaking_change_requires_new_major_path": True,
        "additive_change_requires_compatibility_review": True,
    }:
        _fail()
    route_naming = _mapping(document["route_naming"])
    if route_naming != {
        "resource_names": "lowercase_plural_kebab_case",
        "operation_id": "authorization_catalog_operation_id",
        "verbs_allowed_only_for_commands": True,
    }:
        _fail()
    pagination = _mapping(document["pagination"])
    if pagination != {
        "strategy": "opaque_cursor",
        "cursor_parameter": "cursor",
        "limit_parameter": "limit",
        "default_limit": 50,
        "maximum_limit": 200,
        "total_count_default": "omitted",
    }:
        _fail()
    filtering = _mapping(document["filtering"])
    if filtering != {
        "allowlisted_only": True,
        "unknown_filter": "reject_400",
        "scope_filters_never_expand_authorization": True,
    }:
        _fail()
    idempotency = _mapping(document["idempotency"])
    if idempotency != {
        "mutation_header": "Idempotency-Key",
        "required_for_post": True,
        "minimum_length": 16,
        "maximum_length": 128,
        "conflict_error_code": "IDEMPOTENCY_CONFLICT",
    }:
        _fail()
    request_id = _mapping(document["request_id"])
    if request_id != {
        "request_header": "X-Request-ID",
        "response_header": "X-Request-ID",
        "generated_when_missing_or_invalid": True,
        "never_echo_unvalidated_input": True,
    }:
        _fail()
    deprecation = _mapping(document["deprecation"])
    if deprecation != {
        "openapi_deprecated_flag_required": True,
        "sunset_header_required_when_deprecated": True,
        "minimum_notice_days": 90,
        "removal_requires_breaking_change_review": True,
    }:
        _fail()
    compatibility = _mapping(document["compatibility"])
    if compatibility != {
        "published_v1_immutable": True,
        "breaking_review_roles": ["security", "backend", "web", "mobile"],
        "client_smoke_required": True,
        "sanitized_examples_required": True,
    }:
        _fail()

    bucket_documents = _mapping(document["rate_limit_buckets"])
    buckets: dict[str, RateBucket] = {}
    for name, raw_bucket in bucket_documents.items():
        if _VERSION.fullmatch(name) is None:
            _fail()
        bucket = _mapping(raw_bucket)
        _exact_keys(
            bucket,
            frozenset({"sustained_rps", "burst", "retry_after_required"}),
            API_CONTRACT_INVALID,
        )
        sustained = _integer(bucket["sustained_rps"])
        burst = _integer(bucket["burst"])
        retry_after = _boolean(bucket["retry_after_required"])
        if sustained < 1 or burst < sustained or not retry_after:
            _fail()
        buckets[name] = RateBucket(sustained, burst, retry_after)
    required_buckets = {
        "ansvis_ingestion",
        "login",
        "standard_read",
        "sensitive_write",
        "signed_access",
        "export",
        "destructive_request",
        "admin_read",
        "admin_write",
        "report_read",
        "audit_read",
        "operations_read",
    }
    if set(buckets) != required_buckets:
        _fail()
    if buckets["ansvis_ingestion"] != RateBucket(50, 200, True):
        _fail()
    if buckets["login"] != RateBucket(5, 10, True):
        _fail()
    if buckets["export"] != RateBucket(1, 3, True):
        _fail()
    return ContractPolicy(
        policy_version=policy_version,
        openapi_version=openapi_version,
        authorization_policy_version=authorization_policy_version,
        error_registry_version=error_registry_version,
        required_operation_controls=required_controls,
        rate_limit_buckets=buckets,
    )


def discover_seeded_error_codes(repo_root: Path) -> frozenset[str]:
    codes: set[str] = set()
    for relative_path in _SEED_SOURCES:
        try:
            tree = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            _fail(API_ERROR_REGISTRY_INVALID)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _SEEDED_CODE.fullmatch(node.value) is not None
                and node.value != "AUTHZ_ALLOWED"
            ):
                codes.add(node.value)
    if not codes:
        _fail(API_ERROR_REGISTRY_INVALID)
    return frozenset(codes)


def validate_error_registry(
    document: JsonObject,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, ErrorDefinition]:
    _exact_keys(
        document,
        frozenset(
            {
                "registry_schema_version",
                "registry_version",
                "status",
                "default_redaction_rule",
                "codes",
            }
        ),
        API_ERROR_REGISTRY_INVALID,
    )
    if (
        _integer(document["registry_schema_version"], API_ERROR_REGISTRY_INVALID) != 1
        or _text(document["registry_version"], API_ERROR_REGISTRY_INVALID) != "error_registry_v1"
        or _text(document["status"], API_ERROR_REGISTRY_INVALID)
        != "implementation_baseline_inactive"
        or _text(document["default_redaction_rule"], API_ERROR_REGISTRY_INVALID)
        != "fixed_message_no_reflection"
    ):
        _fail(API_ERROR_REGISTRY_INVALID)
    definitions: dict[str, ErrorDefinition] = {}
    for raw_item in _list(document["codes"], API_ERROR_REGISTRY_INVALID):
        item = _mapping(raw_item, API_ERROR_REGISTRY_INVALID)
        _exact_keys(
            item,
            frozenset(
                {
                    "code",
                    "http_status",
                    "retryable",
                    "exposure",
                    "redaction_rule",
                    "safe_message",
                }
            ),
            API_ERROR_REGISTRY_INVALID,
        )
        code = _text(item["code"], API_ERROR_REGISTRY_INVALID)
        status = _integer(item["http_status"], API_ERROR_REGISTRY_INVALID)
        retryable = _boolean(item["retryable"], API_ERROR_REGISTRY_INVALID)
        exposure = _text(item["exposure"], API_ERROR_REGISTRY_INVALID)
        redaction = _text(item["redaction_rule"], API_ERROR_REGISTRY_INVALID)
        message = _text(item["safe_message"], API_ERROR_REGISTRY_INVALID)
        if (
            _CODE.fullmatch(code) is None
            or code in definitions
            or status < 400
            or status > 599
            or exposure not in {"public", "service", "internal_audit"}
            or redaction
            not in {
                "fixed_message_no_reflection",
                "indistinguishable_protected_resource",
                "internal_audit_only",
            }
            or not 1 <= len(message) <= 160
            or any(
                term in message.lower()
                for term in (
                    "password",
                    "token value",
                    "secret value",
                    "stack trace",
                    "storage key",
                )
            )
        ):
            _fail(API_ERROR_REGISTRY_INVALID)
        if exposure == "internal_audit" and redaction != "internal_audit_only":
            _fail(API_ERROR_REGISTRY_INVALID)
        definitions[code] = ErrorDefinition(
            code=code,
            http_status=status,
            retryable=retryable,
            exposure=exposure,
            redaction_rule=redaction,
            safe_message=message,
        )
    required = discover_seeded_error_codes(repo_root) | _GENERIC_PUBLIC_CODES
    if not required <= definitions.keys():
        _fail(API_ERROR_REGISTRY_INVALID)
    if definitions["AUTHZ_DENIED"].redaction_rule != "indistinguishable_protected_resource":
        _fail(API_ERROR_REGISTRY_INVALID)
    return definitions


def validate_review_record(document: JsonObject, openapi_version: str) -> None:
    _exact_keys(
        document,
        frozenset(
            {
                "review_schema_version",
                "contract_version",
                "reviewed_at",
                "review_method",
                "review_lanes",
                "limitations",
            }
        ),
        API_CONTRACT_INVALID,
    )
    if (
        _integer(document["review_schema_version"]) != 1
        or _text(document["contract_version"]) != openapi_version
        or _text(document["review_method"]) != "single_developer_cross_discipline_contract_review"
    ):
        _fail()
    lanes: dict[str, str] = {}
    for raw_lane in _list(document["review_lanes"]):
        lane = _mapping(raw_lane)
        _exact_keys(lane, frozenset({"role", "result", "evidence"}), API_CONTRACT_INVALID)
        role = _text(lane["role"])
        if role in lanes or _text(lane["result"]) != "pass" or not _text(lane["evidence"]):
            _fail()
        lanes[role] = _text(lane["evidence"])
    if set(lanes) != {"security", "backend", "web", "mobile"}:
        _fail()
    limitations = frozenset(_texts(document["limitations"]))
    if (
        not {
            "implementation_baseline_inactive",
            "no_business_endpoint_implementation",
            "no_production_activation",
            "human_uat_review_still_required_before_release",
        }
        <= limitations
    ):
        _fail()


def _parameter_names(operation: JsonObject, parameters: JsonObject) -> frozenset[str]:
    names: set[str] = set()
    for raw_parameter in _list(operation.get("parameters")):
        reference = _text(_mapping(raw_parameter).get("$ref"))
        prefix = "#/components/parameters/"
        if not reference.startswith(prefix):
            _fail()
        component_name = reference.removeprefix(prefix)
        parameter = _mapping(parameters.get(component_name))
        names.add(_text(parameter.get("name")))
    return frozenset(names)


def _validate_error_response_examples(
    components: JsonObject,
    definitions: dict[str, ErrorDefinition],
) -> None:
    responses = _mapping(components.get("responses"))
    for name in (
        "BadRequest",
        "Unauthorized",
        "ProtectedDenied",
        "Conflict",
        "ValidationFailed",
        "RateLimited",
        "Unavailable",
    ):
        response = _mapping(responses.get(name))
        headers = _mapping(response.get("headers"))
        if "X-Request-ID" not in headers:
            _fail()
        content = _mapping(response.get("content"))
        media = _mapping(content.get("application/json"))
        schema = _mapping(media.get("schema"))
        if schema.get("$ref") != "#/components/schemas/ErrorResponse":
            _fail()
        example = _mapping(media.get("example"))
        _exact_keys(
            example,
            frozenset({"error_code", "message", "request_id"}),
            API_CONTRACT_INVALID,
        )
        code = _text(example["error_code"])
        definition = definitions.get(code)
        if (
            definition is None
            or definition.exposure != "public"
            or _text(example["message"]) != definition.safe_message
            or _REQUEST_ID.fullmatch(_text(example["request_id"])) is None
        ):
            _fail()
    rate_headers = _mapping(_mapping(responses["RateLimited"]).get("headers"))
    if rate_headers.get("Retry-After") != {"$ref": "#/components/headers/RetryAfter"}:
        _fail()


def validate_openapi(
    document: JsonObject,
    *,
    policy: ContractPolicy,
    definitions: dict[str, ErrorDefinition],
    authorization_catalog: JsonObject,
) -> int:
    expected_root = frozenset(
        {
            "openapi",
            "jsonSchemaDialect",
            "info",
            "servers",
            "tags",
            "x-contract-policy-version",
            "x-error-registry-version",
            "x-authorization-policy-version",
            "paths",
            "components",
        }
    )
    _exact_keys(document, expected_root, API_CONTRACT_INVALID)
    info = _mapping(document["info"])
    if (
        document["openapi"] != "3.1.0"
        or info.get("version") != policy.openapi_version
        or document["x-contract-policy-version"] != policy.policy_version
        or document["x-error-registry-version"] != policy.error_registry_version
        or document["x-authorization-policy-version"] != policy.authorization_policy_version
    ):
        _fail()
    _assert_no_forbidden_properties(document)

    catalog_items = _list(authorization_catalog.get("api_operations"))
    catalog_operations: dict[str, JsonObject] = {}
    route_keys: set[tuple[str, str]] = set()
    for raw_item in catalog_items:
        item = _mapping(raw_item)
        operation_id = _text(item.get("operation_id"))
        route_key = (_text(item.get("method")).lower(), _text(item.get("path_template")))
        if operation_id in catalog_operations or route_key in route_keys:
            _fail()
        catalog_operations[operation_id] = item
        route_keys.add(route_key)
    if len(catalog_operations) != 34:
        _fail()

    components = _mapping(document["components"])
    security_schemes = _mapping(components.get("securitySchemes"))
    if set(security_schemes) != {"BearerAuth", "BearerMfaAuth"}:
        _fail()
    parameters = _mapping(components.get("parameters"))
    schemas = _mapping(components.get("schemas"))
    error_schema = _mapping(schemas.get("ErrorResponse"))
    if (
        error_schema.get("type") != "object"
        or error_schema.get("additionalProperties") is not False
        or frozenset(_texts(error_schema.get("required")))
        != {"error_code", "message", "request_id"}
        or set(_mapping(error_schema.get("properties"))) != {"error_code", "message", "request_id"}
    ):
        _fail()
    _validate_error_response_examples(components, definitions)

    paths = _mapping(document["paths"])
    if len(paths) != len(catalog_operations):
        _fail()
    seen: set[str] = set()
    for path, raw_path_item in paths.items():
        if not path.startswith("/api/v1/"):
            _fail()
        path_item = _mapping(raw_path_item)
        if len(path_item) != 1:
            _fail()
        method, raw_operation = next(iter(path_item.items()))
        if method not in {"get", "post"}:
            _fail()
        operation = _mapping(raw_operation)
        operation_id = _text(operation.get("operationId"))
        if _OPERATION_ID.fullmatch(operation_id) is None or operation_id in seen:
            _fail()
        catalog = catalog_operations.get(operation_id)
        if catalog is None:
            _fail()
        seen.add(operation_id)
        if (
            method != _text(catalog.get("method")).lower()
            or path != _text(catalog.get("path_template"))
            or operation.get("deprecated") is not False
            or operation.get("x-auth-scheme") != catalog.get("auth_scheme")
            or operation.get("x-required-permission") != catalog.get("permission_code")
            or tuple(_texts(operation.get("x-object-scope")))
            != tuple(_texts(catalog.get("object_scope_attributes")))
            or operation.get("x-audit-action") != catalog.get("audit_action")
            or operation.get("x-rate-limit-bucket") != catalog.get("rate_limit_bucket")
            or operation.get("x-error-contract") != policy.error_registry_version
        ):
            _fail()
        if not policy.required_operation_controls <= operation.keys():
            _fail()
        audit_action = _text(operation["x-audit-action"])
        rate_bucket = _text(operation["x-rate-limit-bucket"])
        if audit_action not in APPROVED_ACTIONS or rate_bucket not in policy.rate_limit_buckets:
            _fail()
        auth_scheme = _text(operation["x-auth-scheme"])
        expected_security: list[dict[str, list[object]]] = (
            [{"BearerMfaAuth": []}] if auth_scheme == "bearer_mfa" else [{"BearerAuth": []}]
        )
        if operation.get("security") != expected_security:
            _fail()

        parameter_names = _parameter_names(operation, parameters)
        if "X-Request-ID" not in parameter_names:
            _fail()
        path_variables = frozenset(_PATH_VARIABLE.findall(path))
        if not path_variables <= parameter_names:
            _fail()
        if method == "post":
            if (
                operation.get("x-idempotency") != "required"
                or "Idempotency-Key" not in parameter_names
            ):
                _fail()
        elif operation.get("x-idempotency") != "not_applicable":
            _fail()
        if operation_id in _LIST_OPERATIONS and not {"cursor", "limit"} <= parameter_names:
            _fail()

        responses = _mapping(operation.get("responses"))
        if not responses.keys() >= _REQUIRED_STATUSES:
            _fail()
        if (method == "get" and "200" not in responses) or (
            method == "post" and "202" not in responses
        ):
            _fail()
        for status, raw_response in responses.items():
            reference = _text(_mapping(raw_response).get("$ref"))
            if not reference.startswith("#/components/responses/"):
                _fail()
            if status == "404" and reference != "#/components/responses/ProtectedDenied":
                _fail()
            if status == "429" and reference != "#/components/responses/RateLimited":
                _fail()
    if seen != catalog_operations.keys():
        _fail()
    return len(seen)


def generate_typescript_client_smoke(document: JsonObject) -> tuple[str, int, str]:
    operations: list[str] = []
    for raw_path_item in _mapping(document.get("paths")).values():
        for raw_operation in _mapping(raw_path_item).values():
            operation_id = _text(
                _mapping(raw_operation).get("operationId"), API_CLIENT_SMOKE_FAILED
            )
            operations.append(operation_id)
    if len(operations) != len(set(operations)) or not operations:
        _fail(API_CLIENT_SMOKE_FAILED)
    lines = [
        "export type RequestId = string;",
        "export interface ApiRequest { readonly requestId?: RequestId; }",
        "export interface ApiResponse { readonly requestId: RequestId; }",
        "export interface CameraAiApiV1Client {",
    ]
    lines.extend(
        f'  readonly "{operation_id}": (request: ApiRequest) => Promise<ApiResponse>;'
        for operation_id in sorted(operations)
    )
    lines.append("}")
    generated = "\n".join(lines) + "\n"
    if "password" in generated.lower() or "token" in generated.lower():
        _fail(API_CLIENT_SMOKE_FAILED)
    digest = hashlib.sha256(generated.encode("utf-8")).hexdigest()
    return generated, len(operations), digest


def validate_contract(repo_root: Path = REPO_ROOT) -> ContractSummary:
    policy = validate_policy(load_json(repo_root / POLICY_PATH))
    definitions = validate_error_registry(
        load_json(repo_root / ERROR_REGISTRY_PATH), repo_root=repo_root
    )
    openapi = load_json(repo_root / OPENAPI_PATH)
    operation_count = validate_openapi(
        openapi,
        policy=policy,
        definitions=definitions,
        authorization_catalog=load_json(repo_root / AUTHORIZATION_CATALOG_PATH),
    )
    validate_review_record(load_json(repo_root / REVIEW_RECORD_PATH), policy.openapi_version)
    _, client_count, client_digest = generate_typescript_client_smoke(openapi)
    if client_count != operation_count:
        _fail(API_CLIENT_SMOKE_FAILED)
    return ContractSummary(
        policy_version=policy.policy_version,
        openapi_version=policy.openapi_version,
        error_registry_version=policy.error_registry_version,
        operation_count=operation_count,
        error_code_count=len(definitions),
        client_operation_count=client_count,
        client_sha256=client_digest,
    )


def main() -> int:
    try:
        summary = validate_contract()
    except ApiContractError as error:
        print(f"api_contract=FAIL code={error.code}", file=sys.stderr)
        return 1
    print("api_contract=PASS")
    print(f"policy_version={summary.policy_version}")
    print(f"openapi_version={summary.openapi_version}")
    print(f"error_registry_version={summary.error_registry_version}")
    print(f"operations_checked={summary.operation_count}")
    print(f"error_codes_checked={summary.error_code_count}")
    print(f"client_generation_smoke_operations={summary.client_operation_count}")
    print(f"client_generation_smoke_sha256={summary.client_sha256}")
    print("runtime_activation=INACTIVE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
