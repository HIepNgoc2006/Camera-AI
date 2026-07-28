"""The protected API contract checker rejects security and compatibility drift."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from scripts.check_api_contract import (
    API_CLIENT_SMOKE_FAILED,
    API_CONTRACT_INVALID,
    API_ERROR_REGISTRY_INVALID,
    AUTHORIZATION_CATALOG_PATH,
    ERROR_REGISTRY_PATH,
    OPENAPI_PATH,
    POLICY_PATH,
    REPO_ROOT,
    ApiContractError,
    ContractPolicy,
    ErrorDefinition,
    generate_typescript_client_smoke,
    load_json,
    validate_contract,
    validate_error_registry,
    validate_openapi,
    validate_policy,
)

JsonObject = dict[str, object]


def _first_operation(document: JsonObject) -> JsonObject:
    paths = cast(JsonObject, document["paths"])
    path_item = cast(JsonObject, next(iter(paths.values())))
    return cast(JsonObject, next(iter(path_item.values())))


def _openapi_inputs() -> tuple[
    JsonObject,
    ContractPolicy,
    dict[str, ErrorDefinition],
    JsonObject,
]:
    document = load_json(REPO_ROOT / OPENAPI_PATH)
    policy = validate_policy(load_json(REPO_ROOT / POLICY_PATH))
    definitions = validate_error_registry(
        load_json(REPO_ROOT / ERROR_REGISTRY_PATH),
        repo_root=REPO_ROOT,
    )
    catalog = load_json(REPO_ROOT / AUTHORIZATION_CATALOG_PATH)
    return document, policy, definitions, catalog


def test_committed_contract_and_client_smoke_pass() -> None:
    summary = validate_contract()
    document = load_json(REPO_ROOT / OPENAPI_PATH)
    generated, operation_count, digest = generate_typescript_client_smoke(document)

    assert summary.operation_count == 34
    assert summary.error_code_count == 61
    assert summary.client_operation_count == 34
    assert operation_count == 34
    assert len(digest) == 64
    assert '"attendance.list"' in generated
    assert "password" not in generated.lower()


def test_missing_required_operation_control_is_rejected() -> None:
    document, policy, definitions, catalog = _openapi_inputs()
    invalid = deepcopy(document)
    _first_operation(invalid).pop("x-object-scope")

    with pytest.raises(ApiContractError, match=API_CONTRACT_INVALID):
        validate_openapi(
            invalid,
            policy=policy,
            definitions=definitions,
            authorization_catalog=catalog,
        )


def test_authorization_catalog_drift_is_rejected() -> None:
    document, policy, definitions, catalog = _openapi_inputs()
    invalid = deepcopy(document)
    _first_operation(invalid)["x-required-permission"] = "unknown.permission"

    with pytest.raises(ApiContractError, match=API_CONTRACT_INVALID):
        validate_openapi(
            invalid,
            policy=policy,
            definitions=definitions,
            authorization_catalog=catalog,
        )


def test_missing_seeded_error_code_is_rejected() -> None:
    registry = deepcopy(load_json(REPO_ROOT / ERROR_REGISTRY_PATH))
    codes = cast(list[object], registry["codes"])
    registry["codes"] = [
        entry for entry in codes if cast(JsonObject, entry).get("code") != "AUTHZ_DENIED"
    ]

    with pytest.raises(ApiContractError, match=API_ERROR_REGISTRY_INVALID):
        validate_error_registry(registry, repo_root=REPO_ROOT)


def test_sensitive_response_property_is_rejected() -> None:
    document, policy, definitions, catalog = _openapi_inputs()
    invalid = deepcopy(document)
    components = cast(JsonObject, invalid["components"])
    schemas = cast(JsonObject, components["schemas"])
    error_response = cast(JsonObject, schemas["ErrorResponse"])
    properties = cast(JsonObject, error_response["properties"])
    properties["access_token"] = {"type": "string"}

    with pytest.raises(ApiContractError, match=API_CONTRACT_INVALID):
        validate_openapi(
            invalid,
            policy=policy,
            definitions=definitions,
            authorization_catalog=catalog,
        )


def test_rate_limit_baselines_are_normative() -> None:
    policy = validate_policy(load_json(REPO_ROOT / POLICY_PATH))

    assert (
        policy.rate_limit_buckets["ansvis_ingestion"].sustained_rps,
        policy.rate_limit_buckets["ansvis_ingestion"].burst,
    ) == (50, 200)
    assert (
        policy.rate_limit_buckets["login"].sustained_rps,
        policy.rate_limit_buckets["login"].burst,
    ) == (5, 10)
    assert (
        policy.rate_limit_buckets["export"].sustained_rps,
        policy.rate_limit_buckets["export"].burst,
    ) == (1, 3)


def test_normative_policy_drift_is_rejected() -> None:
    invalid = deepcopy(load_json(REPO_ROOT / POLICY_PATH))
    filtering = cast(JsonObject, invalid["filtering"])
    filtering["unknown_filter"] = "ignore"

    with pytest.raises(ApiContractError, match=API_CONTRACT_INVALID):
        validate_policy(invalid)


def test_client_smoke_rejects_duplicate_operations() -> None:
    document = deepcopy(load_json(REPO_ROOT / OPENAPI_PATH))
    paths = cast(JsonObject, document["paths"])
    operations = [
        cast(JsonObject, next(iter(cast(JsonObject, item).values()))) for item in paths.values()
    ]
    operations[1]["operationId"] = operations[0]["operationId"]

    with pytest.raises(ApiContractError, match=API_CLIENT_SMOKE_FAILED):
        generate_typescript_client_smoke(document)
