import { validateAuthenticatedSessionSnapshot } from "@/features/auth/domain/route-access";
import {
  isValidAssignmentId,
  isValidAssignmentVersion,
  isValidOpaqueRef,
  isValidRoleCode,
  parseAccessQuery,
  type AccessAssignmentState,
  type AccessQuery,
  type RoleAssignmentView,
} from "@/features/access/domain/access-view";
import { isRecord } from "@/shared/validation/type-guards";

export interface AccessRuntimeCapabilities {
  readonly readActive: boolean;
  readonly mutationActive: boolean;
}

export interface AccessProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type AccessReadProviderResult =
  | { readonly kind: "success"; readonly page: RoleAssignmentPage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "ACCESS_RUNTIME_INACTIVE" | "ACCESS_UPSTREAM_UNAVAILABLE";
    };

export interface AccessReadProvider {
  readList(
    input: Readonly<{
      query: AccessQuery;
      scope: AccessProviderScope;
    }>,
  ): Promise<AccessReadProviderResult>;
}

export interface RoleAssignmentPage {
  readonly items: readonly RoleAssignmentView[];
  readonly nextCursor: string | null;
}

export type AccessListViewState =
  | { readonly kind: "denied" }
  | {
      readonly kind: "unavailable";
      readonly query: AccessQuery;
      readonly canProposeChange: boolean;
    }
  | {
      readonly kind: "validation";
      readonly errorCode: "ACCESS_FILTER_INVALID";
    }
  | {
      readonly kind: "empty";
      readonly query: AccessQuery;
      readonly canProposeChange: boolean;
    }
  | {
      readonly kind: "success";
      readonly query: AccessQuery;
      readonly page: RoleAssignmentPage;
      readonly canProposeChange: boolean;
    };

export interface QueryAccessListViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: AccessReadProvider;
  readonly capabilities: AccessRuntimeCapabilities;
  readonly now: Date;
}

/** Narrowed active session; owned here, consumed by mutation gating. */
export interface AuthorizedAccessSessionSnapshot {
  readonly policyVersion: "web_bff_session_policy_v1";
  readonly status: "authenticated";
  readonly actorId: string;
  readonly tenantId: string;
  readonly schoolId: string;
  readonly mfaState: "verified" | "not_required";
  readonly issuedAt: string;
  readonly absoluteExpiresAt: string;
  readonly inactivityExpiresAt: string;
  readonly warningStartsAt: string;
  readonly authorization: {
    readonly policyVersion: "rbac_policy_v1";
    readonly permissions: readonly string[];
  };
}

const MAX_PAGE_ITEMS = 200;

/**
 * Issue #75 read orchestration. The session is revalidated before every
 * provider call; client-supplied tenant/school/actor/permission values are
 * never accepted as scope. The provider is expected to apply the
 * authoritative school scope server-side. MFA state is enforced here for
 * read access because the approved contract marks the operation
 * `bearer_mfa` — `mfaState: "not_required"` sessions cannot administer
 * access.
 */
export async function queryAccessListView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryAccessListViewInput): Promise<AccessListViewState> {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !hasViewPermission(authenticatedSession) ||
    !isMfaVerified(authenticatedSession)
  ) {
    return { kind: "denied" };
  }

  const queryValidation = parseAccessQuery(rawQuery);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  const canProposeChange =
    capabilities.mutationActive === true &&
    authenticatedSession.authorization.permissions.includes(
      "role_assignment.correct",
    );

  if (capabilities.readActive !== true) {
    return unavailableState(queryValidation.query, canProposeChange);
  }

  let result: AccessReadProviderResult;
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
    return unavailableState(queryValidation.query, canProposeChange);
  }

  if (!isValidProviderResult(result)) {
    return unavailableState(queryValidation.query, canProposeChange);
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return unavailableState(queryValidation.query, canProposeChange);
  }

  const page = readSafeAssignmentPage(
    result.page,
    queryValidation.query,
    authenticatedSession.schoolId,
  );
  if (!page) {
    return unavailableState(queryValidation.query, canProposeChange);
  }

  if (page.items.length === 0) {
    return {
      kind: "empty",
      query: queryValidation.query,
      canProposeChange,
    };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
    canProposeChange,
  };
}

function hasViewPermission(session: AuthorizedAccessSessionSnapshot): boolean {
  return session.authorization.permissions.includes(
    "role_assignment.view_metadata",
  );
}

function isMfaVerified(session: AuthorizedAccessSessionSnapshot): boolean {
  return session.mfaState === "verified";
}

function unavailableState(
  query: AccessQuery,
  canProposeChange: boolean,
): AccessListViewState {
  return { kind: "unavailable", query, canProposeChange };
}

function isValidProviderResult(
  value: unknown,
): value is AccessReadProviderResult {
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
    (value.errorCode === "ACCESS_RUNTIME_INACTIVE" ||
      value.errorCode === "ACCESS_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeAssignmentPage(
  value: unknown,
  query: AccessQuery,
  sessionSchoolId: string,
): RoleAssignmentPage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > Math.min(query.limit, MAX_PAGE_ITEMS) ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const items: RoleAssignmentView[] = [];
  const assignmentIds = new Set<string>();
  for (const item of value.items) {
    if (!isSafeAssignmentView(item, assignmentIds, sessionSchoolId)) {
      return null;
    }
    assignmentIds.add(item.assignmentId);
    items.push(item);
  }

  return { items, nextCursor: value.nextCursor };
}

function isSafeAssignmentView(
  value: unknown,
  assignmentIds: ReadonlySet<string>,
  sessionSchoolId: string,
): value is RoleAssignmentView {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "assignmentId",
      "displayLabel",
      "revokedAt",
      "roleCode",
      "scopeSchoolId",
      "status",
      "subjectActorRef",
      "validFrom",
      "validUntil",
      "version",
    ])
  ) {
    return false;
  }

  if (
    typeof value.assignmentId !== "string" ||
    !isValidAssignmentId(value.assignmentId) ||
    assignmentIds.has(value.assignmentId) ||
    !isValidOpaqueRef(value.subjectActorRef) ||
    !isValidRoleCode(value.roleCode) ||
    typeof value.scopeSchoolId !== "string" ||
    !isValidOpaqueRef(value.scopeSchoolId) ||
    value.scopeSchoolId !== sessionSchoolId ||
    typeof value.displayLabel !== "string" ||
    !isSafeLabel(value.displayLabel) ||
    typeof value.version !== "number" ||
    !isValidAssignmentVersion(value.version)
  ) {
    return false;
  }

  if (!isSafeInstantOrNull(value.validFrom) || value.validFrom === null) {
    return false;
  }

  const validUntilOk =
    value.validUntil === null ||
    (typeof value.validUntil === "string" &&
      isSafeInstantOrNull(value.validUntil));
  if (!validUntilOk) {
    return false;
  }

  if (
    value.revokedAt !== null &&
    !(
      typeof value.revokedAt === "string" &&
      isSafeInstantOrNull(value.revokedAt)
    )
  ) {
    return false;
  }

  if (typeof value.status !== "string" || !isAssignmentState(value.status)) {
    return false;
  }

  return true;
}

function isAssignmentState(value: string): value is AccessAssignmentState {
  return value === "active" || value === "expired" || value === "revoked";
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
