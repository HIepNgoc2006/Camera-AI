import { isRecord } from "@/shared/validation/type-guards";

/**
 * Access administration presentation model. The approved API contract
 * defines `GET /api/v1/role-assignments/{assignment_id}` (bearer + MFA,
 * `role_assignment.view_metadata`) and `POST
 * /api/v1/role-assignments/{assignment_id}/changes` (dual-control
 * `role_assignment.correct`, idempotent) only. There is no list operation
 * and no approved approve/revoke permission, so this model fails closed and
 * the allowed grant set is always resolved by the backend.
 */

export const ACCESS_ASSIGNMENT_STATES = [
  "active",
  "expired",
  "revoked",
] as const;

export type AccessAssignmentState = (typeof ACCESS_ASSIGNMENT_STATES)[number];

/**
 * Mutation affordances the access screen can express. Only proposing a
 * change maps to an approved catalog permission (`role_assignment.correct`,
 * dual control). Approving and revoking have no approved mapping in
 * `rbac_policy_v1` and stay structurally denied until the policy owner
 * decides otherwise — they must never be invented client-side.
 */
export const ACCESS_MUTATION_KINDS = [
  "propose_change",
  "approve_change",
  "revoke_assignment",
] as const;

export type AccessMutationKind = (typeof ACCESS_MUTATION_KINDS)[number];

export type AccessMutationPermissionCode = "role_assignment.correct";

export const MUTATION_PERMISSION_BY_KIND: Readonly<
  Record<AccessMutationKind, AccessMutationPermissionCode | null>
> = {
  propose_change: "role_assignment.correct",
  approve_change: null,
  revoke_assignment: null,
};

export interface RoleAssignmentView {
  readonly assignmentId: string;
  /** Opaque server-provided subject reference; never a name or credential. */
  readonly subjectActorRef: string;
  readonly displayLabel: string;
  readonly roleCode: string;
  readonly scopeSchoolId: string;
  readonly validFrom: string;
  readonly validUntil: string | null;
  readonly revokedAt: string | null;
  readonly status: AccessAssignmentState;
  /** Server-assigned row version for optimistic concurrency on changes. */
  readonly version: number;
}

export interface AccessQuery {
  cursor: string | null;
  limit: number;
}

export type AccessQueryValidation =
  | { readonly kind: "valid"; readonly query: AccessQuery }
  | {
      readonly kind: "invalid";
      readonly errorCode: "ACCESS_FILTER_INVALID";
    };

export interface OpaqueAccessItem {
  readonly resourceId: string;
  readonly resourceType: string;
  readonly updatedAt: string;
}

export interface OpaqueAccessEnvelope {
  readonly items: readonly OpaqueAccessItem[];
  readonly nextCursor: string | null;
  readonly requestId: string;
}

export type OpaqueAccessEnvelopeValidation =
  | { readonly kind: "valid"; readonly value: OpaqueAccessEnvelope }
  | {
      readonly kind: "invalid";
      readonly errorCode: "ACCESS_RESPONSE_INVALID";
    };

const ALLOWED_QUERY_KEYS = new Set(["cursor", "limit"]);
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const MAX_GATEWAY_ITEMS = 200;
const MAX_VERSION = 2_147_483_647;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const ROLE_CODE_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;
const OPAQUE_REF_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/u;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,120}$/u;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;
const ACCESS_RESOURCE_TYPE = "role_assignment";

export function parseAccessQuery(input: unknown): AccessQueryValidation {
  if (!isRecord(input)) {
    return invalidQuery();
  }

  const keys = Object.keys(input);
  if (keys.some((key) => !ALLOWED_QUERY_KEYS.has(key))) {
    return invalidQuery();
  }

  const cursor = readOptionalString(input, "cursor");
  const limitValue = readOptionalString(input, "limit");
  if (
    cursor === INVALID_STRING ||
    limitValue === INVALID_STRING ||
    (cursor !== null && !isValidCursor(cursor))
  ) {
    return invalidQuery();
  }

  const limit = limitValue === null ? DEFAULT_LIMIT : parseLimit(limitValue);
  if (limit === null) {
    return invalidQuery();
  }

  return {
    kind: "valid",
    query: { cursor, limit },
  };
}

export function parseOpaqueAccessEnvelope(
  input: unknown,
): OpaqueAccessEnvelopeValidation {
  if (
    !isRecord(input) ||
    !hasExactKeys(input, ["items", "next_cursor", "request_id"]) ||
    !Array.isArray(input.items) ||
    input.items.length > MAX_GATEWAY_ITEMS ||
    !isValidCursorOrNull(input.next_cursor) ||
    typeof input.request_id !== "string" ||
    !REQUEST_ID_PATTERN.test(input.request_id)
  ) {
    return { kind: "invalid", errorCode: "ACCESS_RESPONSE_INVALID" };
  }

  const items: OpaqueAccessItem[] = [];
  for (const item of input.items) {
    if (
      !isRecord(item) ||
      !hasExactKeys(item, ["resource_id", "resource_type", "updated_at"]) ||
      typeof item.resource_id !== "string" ||
      !UUID_PATTERN.test(item.resource_id) ||
      typeof item.resource_type !== "string" ||
      item.resource_type !== ACCESS_RESOURCE_TYPE ||
      typeof item.updated_at !== "string" ||
      !isUtcInstant(item.updated_at)
    ) {
      return { kind: "invalid", errorCode: "ACCESS_RESPONSE_INVALID" };
    }

    items.push({
      resourceId: item.resource_id,
      resourceType: item.resource_type,
      updatedAt: item.updated_at,
    });
  }

  return {
    kind: "valid",
    value: {
      items,
      nextCursor: input.next_cursor,
      requestId: input.request_id,
    },
  };
}

/**
 * Own-role changes are denied by default: the own-role and
 * last-privileged-account rules have no recorded policy decision, so the
 * client refuses before any provider call and the backend remains the final
 * enforcement.
 */
export function isOwnRoleAssignment(
  view: Pick<RoleAssignmentView, "subjectActorRef">,
  session: Readonly<{ actorId: string }>,
): boolean {
  return view.subjectActorRef === session.actorId;
}

const INVALID_STRING = Symbol("invalid-string");

function readOptionalString(
  input: Record<string, unknown>,
  key: string,
): string | null | typeof INVALID_STRING {
  const value = input[key];
  if (value === undefined) {
    return null;
  }
  return typeof value === "string" && value.length > 0 ? value : INVALID_STRING;
}

function parseLimit(value: string): number | null {
  if (!/^(?:[1-9]|[1-9]\d|100)$/u.test(value)) {
    return null;
  }
  const parsed = Number(value);
  return parsed <= MAX_LIMIT ? parsed : null;
}

function isValidCursor(value: string): boolean {
  return (
    value.length >= 16 &&
    value.length <= 512 &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function isValidCursorOrNull(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && isValidCursor(value));
}

function isUtcInstant(value: string): boolean {
  if (!UTC_INSTANT_PATTERN.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
}

export function isValidAssignmentVersion(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 1 &&
    value <= MAX_VERSION
  );
}

export function isValidRoleCode(value: unknown): value is string {
  return typeof value === "string" && ROLE_CODE_PATTERN.test(value);
}

export function isValidOpaqueRef(value: unknown): value is string {
  return typeof value === "string" && OPAQUE_REF_PATTERN.test(value);
}

export function isValidAssignmentId(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function invalidQuery(): AccessQueryValidation {
  return { kind: "invalid", errorCode: "ACCESS_FILTER_INVALID" };
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
