import { validateAuthenticatedSessionSnapshot } from "@/features/auth/domain/route-access";
import {
  VIOLATION_CASE_STATUSES,
  parseViolationQuery,
  type ViolationActions,
  type ViolationDetail,
  type ViolationLegalHoldState,
  type ViolationListItem,
  type ViolationPage,
  type ViolationQuery,
} from "@/features/violations/domain/violation-view";
import { resolveViolationActionVisibilityForSession } from "@/features/violations/infrastructure/action-visibility";
import { isRecord } from "@/shared/validation/type-guards";

export interface ViolationRuntimeCapabilities {
  readonly readActive: boolean;
  readonly reviewActive: boolean;
  readonly correctionActive: boolean;
  readonly exportActive: boolean;
}

export interface ViolationProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type ViolationListProviderResult =
  | { readonly kind: "success"; readonly page: ViolationPage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "VIOLATION_RUNTIME_INACTIVE" | "VIOLATION_UPSTREAM_UNAVAILABLE";
    };

export type ViolationDetailProviderResult =
  | { readonly kind: "success"; readonly detail: ViolationDetail }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "VIOLATION_RUNTIME_INACTIVE" | "VIOLATION_UPSTREAM_UNAVAILABLE";
    };

export interface ViolationReadProvider {
  readList(
    input: Readonly<{
      query: ViolationQuery;
      scope: ViolationProviderScope;
    }>,
  ): Promise<ViolationListProviderResult>;
  readDetail(
    input: Readonly<{
      caseId: string;
      scope: ViolationProviderScope;
    }>,
  ): Promise<ViolationDetailProviderResult>;
}

export type ViolationListViewState =
  | { readonly kind: "denied" }
  | {
      readonly kind: "unavailable";
      readonly query: ViolationQuery;
      readonly actions: ViolationActions;
    }
  | {
      readonly kind: "validation";
      readonly errorCode: "VIOLATION_FILTER_INVALID";
    }
  | {
      readonly kind: "empty";
      readonly query: ViolationQuery;
      readonly actions: ViolationActions;
    }
  | {
      readonly kind: "success";
      readonly query: ViolationQuery;
      readonly page: ViolationPage;
      readonly actions: ViolationActions;
    };

export type ViolationDetailViewInput = Readonly<{
  caseId: string;
}>;

export type ViolationDetailViewResult =
  | { readonly kind: "denied" }
  | { readonly kind: "not_found" }
  | { readonly kind: "unavailable" }
  | { readonly kind: "success"; readonly detail: ViolationDetail };

export interface QueryViolationListViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: ViolationReadProvider;
  readonly capabilities: ViolationRuntimeCapabilities;
  readonly now: Date;
}

export interface QueryViolationDetailViewInput {
  readonly session: unknown;
  readonly caseId: string;
  readonly provider: ViolationReadProvider;
  readonly capabilities: ViolationRuntimeCapabilities;
  readonly now: Date;
}

/** Narrowed active session; owned here, consumed by action resolution. */
export type AuthorizedViolationSession = NonNullable<
  ReturnType<typeof validateAuthenticatedSessionSnapshot>
>;

const VIOLATION_CASE_STATUS_LOOKUP: Record<string, true> = Object.fromEntries(
  VIOLATION_CASE_STATUSES.map((status) => [status, true as const]),
);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

export async function queryViolationListView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryViolationListViewInput): Promise<ViolationListViewState> {
  const authenticatedSession = requireViolationViewSession(session, now);
  if (!authenticatedSession) {
    return { kind: "denied" };
  }

  const queryValidation = parseViolationQuery(rawQuery, now);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  const actions = resolveViolationActions(
    authenticatedSession,
    capabilities,
    now,
  );

  if (capabilities.readActive !== true) {
    return unavailableListState(queryValidation.query, actions);
  }

  let result: ViolationListProviderResult;
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
    return unavailableListState(queryValidation.query, actions);
  }

  if (!isValidListProviderResult(result)) {
    return unavailableListState(queryValidation.query, actions);
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return unavailableListState(queryValidation.query, actions);
  }

  const page = readSafeViolationPage(result.page, queryValidation.query);
  if (!page) {
    return unavailableListState(queryValidation.query, actions);
  }

  if (page.items.length === 0) {
    return {
      kind: "empty",
      query: queryValidation.query,
      actions,
    };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
    actions,
  };
}

export async function queryViolationDetailView({
  session,
  caseId,
  provider,
  capabilities,
  now,
}: QueryViolationDetailViewInput): Promise<ViolationDetailViewResult> {
  const authenticatedSession = requireViolationViewSession(session, now);
  if (!authenticatedSession) {
    return { kind: "denied" };
  }

  if (typeof caseId !== "string" || !UUID_PATTERN.test(caseId)) {
    return { kind: "not_found" };
  }

  if (capabilities.readActive !== true) {
    return { kind: "unavailable" };
  }

  let result: ViolationDetailProviderResult;
  try {
    result = await provider.readDetail({
      caseId,
      scope: {
        tenantId: authenticatedSession.tenantId,
        schoolId: authenticatedSession.schoolId,
        actorId: authenticatedSession.actorId,
      },
    });
  } catch {
    return { kind: "unavailable" };
  }

  if (!isValidDetailProviderResult(result)) {
    return { kind: "unavailable" };
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "not_found" };
  }
  if (result.kind === "unavailable") {
    return { kind: "unavailable" };
  }

  const detail = readSafeViolationDetail(result.detail, caseId);
  return detail ? { kind: "success", detail } : { kind: "unavailable" };
}

function requireViolationViewSession(session: unknown, now: Date) {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !authenticatedSession.authorization.permissions.includes(
      "violation.view_metadata",
    )
  ) {
    return null;
  }
  return authenticatedSession;
}

function resolveViolationActions(
  session: AuthorizedViolationSession,
  capabilities: ViolationRuntimeCapabilities,
  now: Date,
): ViolationActions {
  return resolveViolationActionVisibilityForSession(session, capabilities, now);
}

function unavailableListState(
  query: ViolationQuery,
  actions: ViolationActions,
): ViolationListViewState {
  return {
    kind: "unavailable",
    query,
    actions,
  };
}

function isValidListProviderResult(
  value: unknown,
): value is ViolationListProviderResult {
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
    (value.errorCode === "VIOLATION_RUNTIME_INACTIVE" ||
      value.errorCode === "VIOLATION_UPSTREAM_UNAVAILABLE")
  );
}

function isValidDetailProviderResult(
  value: unknown,
): value is ViolationDetailProviderResult {
  if (!isRecord(value) || typeof value.kind !== "string") {
    return false;
  }
  if (value.kind === "success") {
    return hasExactKeys(value, ["kind", "detail"]);
  }
  if (value.kind === "denied_or_not_found") {
    return hasExactKeys(value, ["kind"]);
  }
  return (
    value.kind === "unavailable" &&
    hasExactKeys(value, ["errorCode", "kind"]) &&
    (value.errorCode === "VIOLATION_RUNTIME_INACTIVE" ||
      value.errorCode === "VIOLATION_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeViolationPage(
  value: unknown,
  query: ViolationQuery,
): ViolationPage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > query.limit ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const items: ViolationListItem[] = [];
  const caseIds = new Set<string>();
  for (const item of value.items) {
    if (!isSafeViolationListItem(item, query, caseIds)) {
      return null;
    }
    caseIds.add(item.caseId);
    items.push(item);
  }

  return { items, nextCursor: value.nextCursor };
}

function isSafeViolationListItem(
  value: unknown,
  query: ViolationQuery,
  caseIds: ReadonlySet<string>,
): value is ViolationListItem {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "appealState",
      "caseId",
      "caseRef",
      "category",
      "correctionState",
      "legalHoldState",
      "occurredAt",
      "reviewStatus",
    ])
  ) {
    return false;
  }

  return isSafeViolationCaseFields(value, query, caseIds);
}

function isSafeViolationCaseFields(
  value: Record<string, unknown>,
  query: ViolationQuery,
  caseIds: ReadonlySet<string>,
): boolean {
  return (
    typeof value.caseId === "string" &&
    UUID_PATTERN.test(value.caseId) &&
    !caseIds.has(value.caseId) &&
    typeof value.caseRef === "string" &&
    isSafeOpaqueRef(value.caseRef, 64) &&
    typeof value.category === "string" &&
    isKnownViolationCategory(value.category) &&
    typeof value.occurredAt === "string" &&
    isUtcInstant(value.occurredAt) &&
    occurredWithinWindow(value.occurredAt, query) &&
    typeof value.reviewStatus === "string" &&
    Object.hasOwn(VIOLATION_CASE_STATUS_LOOKUP, value.reviewStatus) &&
    (query.status === null || value.reviewStatus === query.status) &&
    value.reviewStatus !== "appealed" &&
    value.reviewStatus !== "corrected" &&
    typeof value.appealState === "string" &&
    (value.appealState === "appealed" ||
      value.appealState === "not_appealed") &&
    typeof value.correctionState === "string" &&
    (value.correctionState === "corrected" ||
      value.correctionState === "not_corrected") &&
    isSafeLegalHoldState(value.legalHoldState)
  );
}

function readSafeViolationDetail(
  value: unknown,
  requestedCaseId: string,
): ViolationDetail | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "appealState",
      "caseId",
      "caseRef",
      "category",
      "correctionState",
      "legalHoldState",
      "occurredAt",
      "reviewStatus",
      "updatedAt",
    ])
  ) {
    return null;
  }

  const queryScoped =
    value.caseId === requestedCaseId &&
    isSafeViolationCaseFields(
      value,
      {
        occurredFrom: "0000-01-01",
        occurredTo: "9999-12-31",
        status: null,
        cursor: null,
        limit: Number.MAX_SAFE_INTEGER,
      },
      new Set<string>(),
    ) &&
    typeof value.updatedAt === "string" &&
    typeof value.occurredAt === "string";
  if (!queryScoped) {
    return null;
  }
  const updatedAt: string = value.updatedAt as string;
  const occurredAt: string = value.occurredAt as string;
  if (!isUtcInstant(updatedAt) || updatedAt < occurredAt) {
    return null;
  }

  const detail: ViolationDetail = {
    caseId: value.caseId as string,
    caseRef: value.caseRef as string,
    category: value.category as ViolationDetail["category"],
    occurredAt,
    reviewStatus: value.reviewStatus as ViolationDetail["reviewStatus"],
    appealState: value.appealState as ViolationDetail["appealState"],
    correctionState:
      value.correctionState as ViolationDetail["correctionState"],
    legalHoldState: value.legalHoldState as ViolationDetail["legalHoldState"],
    updatedAt,
  };
  return isSafeViolationCaseFields(
    detail as unknown as Record<string, unknown>,
    {
      occurredFrom: "0000-01-01",
      occurredTo: "9999-12-31",
      status: null,
      cursor: null,
      limit: Number.MAX_SAFE_INTEGER,
    },
    new Set<string>(),
  )
    ? detail
    : null;
}

function isSafeLegalHoldState(
  value: unknown,
): value is ViolationLegalHoldState {
  return (
    value === "none" ||
    value === "active" ||
    value === "released" ||
    value === "unavailable"
  );
}

function isKnownViolationCategory(value: string): boolean {
  return (
    value === "suspected_littering" ||
    value === "suspected_smoking" ||
    value === "suspected_uniform_noncompliance" ||
    value === "suspected_ppe_noncompliance" ||
    value === "facial_recognition_match"
  );
}

function isSafeOpaqueRef(value: string, maxLength: number): boolean {
  return (
    value.length > 0 &&
    value.length <= maxLength &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value) &&
    !/^(?:https?:|data:|file:|\/\/)/iu.test(value) &&
    !/[\\/]|\.\./u.test(value)
  );
}

function occurredWithinWindow(
  occurredAt: string,
  query: ViolationQuery,
): boolean {
  const day = occurredAt.slice(0, 10);
  return day >= query.occurredFrom && day <= query.occurredTo;
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

function isUtcInstant(value: string): boolean {
  if (!UTC_INSTANT_PATTERN.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
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
