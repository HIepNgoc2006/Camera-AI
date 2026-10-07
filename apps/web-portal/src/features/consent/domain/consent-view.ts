import { isRecord } from "@/shared/validation/type-guards";

/**
 * Consent/privacy presentation model. The approved API contract defines
 * `GET /api/v1/consents/{consent_id}` (`consent.view_metadata`) and `POST
 * /api/v1/consents/{consent_id}/decisions` (`consent.correct`, idempotent)
 * with no list operation. The consent state machine and the withdrawal
 * lifecycle follow the checked-in policy sources; terminal states are never
 * restored client-side and withdrawal-specific permissions are not part of
 * `rbac_policy_v1`, so withdrawal actions stay structurally denied.
 */

export const CONSENT_STATES = [
  "pending",
  "granted",
  "denied",
  "withdrawn",
  "restricted",
  "expired",
] as const;

export type ConsentState = (typeof CONSENT_STATES)[number];

const TERMINAL_CONSENT_STATES: Readonly<Record<string, true>> = {
  denied: true,
  expired: true,
  restricted: true,
  withdrawn: true,
};

export function isTerminalConsentState(state: ConsentState): boolean {
  return TERMINAL_CONSENT_STATES[state] === true;
}

/**
 * Withdrawal lifecycle from `consent-withdrawal-policy-v1`. The UI may
 * render progress, but every lifecycle mutation beyond a request belongs to
 * the backend orchestrator; the effective state denies new processing
 * before disposal happens.
 */
export const WITHDRAWAL_STATES = [
  "requested",
  "identity_verified",
  "effective",
  "propagating",
  "partially_completed",
  "completed",
  "rejected",
  "superseded",
] as const;

export type WithdrawalState = (typeof WITHDRAWAL_STATES)[number];

/**
 * Purposes approved in the consent processing gate contract; anything else
 * fails closed instead of being invented client-side.
 */
export const CONSENT_PURPOSES = [
  "attendance",
  "timekeeping",
  "emotion",
] as const;

export type ConsentPurpose = (typeof CONSENT_PURPOSES)[number];

export type ConsentMutationPermissionCode = "consent.correct";

/**
 * Mutation affordances the consent screen can express. Recording a consent
 * decision maps to the approved `consent.correct` permission; requesting a
 * withdrawal maps to `privacy.withdrawal.request.*` codes that are NOT in
 * `rbac_policy_v1` and therefore have no client-side mapping until the
 * policy owner approves one — they stay structurally denied.
 */
export const CONSENT_MUTATION_KINDS = [
  "record_decision",
  "request_withdrawal",
] as const;

export type ConsentMutationKind = (typeof CONSENT_MUTATION_KINDS)[number];

export const MUTATION_PERMISSION_BY_KIND: Readonly<
  Record<ConsentMutationKind, ConsentMutationPermissionCode | null>
> = {
  record_decision: "consent.correct",
  request_withdrawal: null,
};

export interface ConsentRecordView {
  readonly consentId: string;
  /** Opaque server-provided subject reference; never a name or credential. */
  readonly subjectActorRef: string;
  readonly displayLabel: string;
  readonly purposeCode: string;
  readonly policyVersion: string;
  readonly status: ConsentState;
  readonly scopeSchoolId: string;
  readonly validFrom: string;
  readonly validUntil: string | null;
  readonly withdrawalState: WithdrawalState | null;
  /** Server-assigned row version for optimistic concurrency on decisions. */
  readonly version: number;
}

export interface ConsentQuery {
  cursor: string | null;
  limit: number;
}

export type ConsentQueryValidation =
  | { readonly kind: "valid"; readonly query: ConsentQuery }
  | {
      readonly kind: "invalid";
      readonly errorCode: "CONSENT_FILTER_INVALID";
    };

export interface OpaqueConsentItem {
  readonly resourceId: string;
  readonly resourceType: string;
  readonly updatedAt: string;
}

export interface OpaqueConsentEnvelope {
  readonly items: readonly OpaqueConsentItem[];
  readonly nextCursor: string | null;
  readonly requestId: string;
}

export type OpaqueConsentEnvelopeValidation =
  | { readonly kind: "valid"; readonly value: OpaqueConsentEnvelope }
  | {
      readonly kind: "invalid";
      readonly errorCode: "CONSENT_RESPONSE_INVALID";
    };

const ALLOWED_QUERY_KEYS = new Set(["cursor", "limit"]);
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const MAX_GATEWAY_ITEMS = 200;
const MAX_VERSION = 2_147_483_647;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const OPAQUE_REF_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/u;
const SAFE_CODE_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,120}$/u;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;
const CONSENT_RESOURCE_TYPE = "consent_record";

export function parseConsentQuery(input: unknown): ConsentQueryValidation {
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

export function parseOpaqueConsentEnvelope(
  input: unknown,
): OpaqueConsentEnvelopeValidation {
  if (
    !isRecord(input) ||
    !hasExactKeys(input, ["items", "next_cursor", "request_id"]) ||
    !Array.isArray(input.items) ||
    input.items.length > MAX_GATEWAY_ITEMS ||
    !isValidCursorOrNull(input.next_cursor) ||
    typeof input.request_id !== "string" ||
    !REQUEST_ID_PATTERN.test(input.request_id)
  ) {
    return { kind: "invalid", errorCode: "CONSENT_RESPONSE_INVALID" };
  }

  const items: OpaqueConsentItem[] = [];
  for (const item of input.items) {
    if (
      !isRecord(item) ||
      !hasExactKeys(item, ["resource_id", "resource_type", "updated_at"]) ||
      typeof item.resource_id !== "string" ||
      !UUID_PATTERN.test(item.resource_id) ||
      typeof item.resource_type !== "string" ||
      item.resource_type !== CONSENT_RESOURCE_TYPE ||
      typeof item.updated_at !== "string" ||
      !isUtcInstant(item.updated_at)
    ) {
      return { kind: "invalid", errorCode: "CONSENT_RESPONSE_INVALID" };
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

export function isConsentState(value: unknown): value is ConsentState {
  return (
    typeof value === "string" &&
    (CONSENT_STATES as readonly string[]).includes(value)
  );
}

export function isWithdrawalState(value: unknown): value is WithdrawalState {
  return (
    typeof value === "string" &&
    (WITHDRAWAL_STATES as readonly string[]).includes(value)
  );
}

export function isConsentPurpose(value: unknown): value is ConsentPurpose {
  return (
    typeof value === "string" &&
    (CONSENT_PURPOSES as readonly string[]).includes(value)
  );
}

export function isValidConsentVersion(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= 1 &&
    value <= MAX_VERSION
  );
}

export function isValidConsentId(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

export function isValidOpaqueRef(value: unknown): value is string {
  return typeof value === "string" && OPAQUE_REF_PATTERN.test(value);
}

export function isValidPolicyVersionCode(value: unknown): value is string {
  return typeof value === "string" && SAFE_CODE_PATTERN.test(value);
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

function invalidQuery(): ConsentQueryValidation {
  return { kind: "invalid", errorCode: "CONSENT_FILTER_INVALID" };
}
