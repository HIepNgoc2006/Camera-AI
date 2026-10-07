import { validateAuthenticatedSessionSnapshot } from "@/features/auth/domain/route-access";
import {
  isConsentState,
  isWithdrawalState,
  isValidConsentId,
  isValidConsentVersion,
  isValidOpaqueRef,
  isValidPolicyVersionCode,
  parseConsentQuery,
  type ConsentQuery,
  type ConsentRecordView,
} from "@/features/consent/domain/consent-view";
import { isRecord } from "@/shared/validation/type-guards";

export interface ConsentRuntimeCapabilities {
  readonly readActive: boolean;
  readonly mutationActive: boolean;
}

export interface ConsentProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type ConsentReadProviderResult =
  | { readonly kind: "success"; readonly page: ConsentPage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "CONSENT_RUNTIME_INACTIVE" | "CONSENT_UPSTREAM_UNAVAILABLE";
    };

export interface ConsentReadProvider {
  readList(
    input: Readonly<{
      query: ConsentQuery;
      scope: ConsentProviderScope;
    }>,
  ): Promise<ConsentReadProviderResult>;
}

export interface ConsentPage {
  readonly items: readonly ConsentRecordView[];
  readonly nextCursor: string | null;
}

export type ConsentListViewState =
  | { readonly kind: "denied" }
  | {
      readonly kind: "unavailable";
      readonly query: ConsentQuery;
      readonly canRecordDecision: boolean;
    }
  | {
      readonly kind: "validation";
      readonly errorCode: "CONSENT_FILTER_INVALID";
    }
  | {
      readonly kind: "empty";
      readonly query: ConsentQuery;
      readonly canRecordDecision: boolean;
    }
  | {
      readonly kind: "success";
      readonly query: ConsentQuery;
      readonly page: ConsentPage;
      readonly canRecordDecision: boolean;
    };

export interface QueryConsentListViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: ConsentReadProvider;
  readonly capabilities: ConsentRuntimeCapabilities;
  readonly now: Date;
}

/**
 * The session is revalidated before every provider call; client-supplied
 * tenant/school/actor/permission values are never accepted as scope.
 * Guardian/delegation authority is resolved by the backend — holding an
 * admin or privacy role never widens the readable consent set.
 */
export async function queryConsentListView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryConsentListViewInput): Promise<ConsentListViewState> {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !authenticatedSession.authorization.permissions.includes(
      "consent.view_metadata",
    )
  ) {
    return { kind: "denied" };
  }

  const queryValidation = parseConsentQuery(rawQuery);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  const canRecordDecision =
    capabilities.mutationActive === true &&
    authenticatedSession.authorization.permissions.includes("consent.correct");

  if (capabilities.readActive !== true) {
    return unavailableState(queryValidation.query, canRecordDecision);
  }

  let result: ConsentReadProviderResult;
  try {
    result = await provider.readList({
      query: queryValidation.query,
      scope: {
        tenantId: authenticatedSession.tenantId,
        schoolId: authenticatedSession.schoolId,
        actorId: authenticatedSession.actorId,
      },
    });
  } catch {
    return unavailableState(queryValidation.query, canRecordDecision);
  }

  if (!isValidProviderResult(result)) {
    return unavailableState(queryValidation.query, canRecordDecision);
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return unavailableState(queryValidation.query, canRecordDecision);
  }

  const page = readSafeConsentPage(
    result.page,
    queryValidation.query,
    authenticatedSession.schoolId,
  );
  if (!page) {
    return unavailableState(queryValidation.query, canRecordDecision);
  }

  if (page.items.length === 0) {
    return {
      kind: "empty",
      query: queryValidation.query,
      canRecordDecision,
    };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
    canRecordDecision,
  };
}

function unavailableState(
  query: ConsentQuery,
  canRecordDecision: boolean,
): ConsentListViewState {
  return { kind: "unavailable", query, canRecordDecision };
}

function isValidProviderResult(
  value: unknown,
): value is ConsentReadProviderResult {
  if (!isRecord(value) || typeof value.kind !== "string") {
    return false;
  }
  if (value.kind === "success") {
    return hasExactKeys(value, ["kind", "page"]);
  }
  if (value.kind === "denied_or_not_found") {
    return hasExactKeys(value, ["kind"]);
  }
  return (
    value.kind === "unavailable" &&
    hasExactKeys(value, ["errorCode", "kind"]) &&
    (value.errorCode === "CONSENT_RUNTIME_INACTIVE" ||
      value.errorCode === "CONSENT_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeConsentPage(
  value: unknown,
  query: ConsentQuery,
  sessionSchoolId: string,
): ConsentPage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > query.limit ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const items: ConsentRecordView[] = [];
  const consentIds = new Set<string>();
  for (const item of value.items) {
    if (!isSafeConsentRecord(item, consentIds, sessionSchoolId)) {
      return null;
    }
    consentIds.add(item.consentId);
    items.push(item);
  }

  return { items, nextCursor: value.nextCursor };
}

function isSafeConsentRecord(
  value: unknown,
  consentIds: ReadonlySet<string>,
  sessionSchoolId: string,
): value is ConsentRecordView {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "consentId",
      "displayLabel",
      "policyVersion",
      "purposeCode",
      "scopeSchoolId",
      "status",
      "subjectActorRef",
      "validFrom",
      "validUntil",
      "version",
      "withdrawalState",
    ])
  ) {
    return false;
  }

  if (
    typeof value.consentId !== "string" ||
    !isValidConsentId(value.consentId) ||
    consentIds.has(value.consentId) ||
    !isValidOpaqueRef(value.subjectActorRef) ||
    !isValidPolicyVersionCode(value.policyVersion) ||
    typeof value.purposeCode !== "string" ||
    !isApprovedPurposeCode(value.purposeCode)
  ) {
    return false;
  }

  if (
    typeof value.scopeSchoolId !== "string" ||
    !isValidOpaqueRef(value.scopeSchoolId) ||
    value.scopeSchoolId !== sessionSchoolId
  ) {
    return false;
  }

  if (
    typeof value.displayLabel !== "string" ||
    !isSafeLabel(value.displayLabel) ||
    typeof value.version !== "number" ||
    !isValidConsentVersion(value.version) ||
    !isConsentState(value.status)
  ) {
    return false;
  }

  if (
    value.withdrawalState !== null &&
    !isWithdrawalState(value.withdrawalState)
  ) {
    return false;
  }

  if (!isSafeInstantOrNull(value.validFrom) || value.validFrom === null) {
    return false;
  }

  return (
    value.validUntil === null ||
    (typeof value.validUntil === "string" &&
      isSafeInstantOrNull(value.validUntil))
  );
}

function isApprovedPurposeCode(value: string): boolean {
  return (
    value === "attendance" || value === "timekeeping" || value === "emotion"
  );
}

function isSafeLabel(value: unknown, maxLength = 160): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maxLength &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function isSafeInstantOrNull(value: unknown): value is string | null {
  if (value === null) {
    return true;
  }
  if (typeof value !== "string") {
    return false;
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
}

function isValidCursorOrNull(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value.length >= 16 &&
      value.length <= 512 &&
      value.trim() === value &&
      !/[\u0000-\u001f\u007f]/u.test(value))
  );
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    keys.length === sortedExpected.length &&
    keys.every((key, index) => key === sortedExpected[index])
  );
}
