import { isRecord } from "@/shared/validation/type-guards";

export const VIOLATION_CASE_STATUSES = [
  "suspected",
  "pending_review",
  "needs_evidence",
  "confirmed",
  "rejected",
  "closed",
] as const;

export type ViolationCaseStatus = (typeof VIOLATION_CASE_STATUSES)[number];

/**
 * Presentation-only lifecycle overlays. The backend owns separate appeal,
 * correction and legal-hold lifecycles; these are surfaced independently and
 * never replace the canonical case status above.
 */
export const VIOLATION_APPEAL_STATES = ["appealed", "not_appealed"] as const;

export type ViolationAppealState = (typeof VIOLATION_APPEAL_STATES)[number];

export const VIOLATION_CORRECTION_STATES = [
  "corrected",
  "not_corrected",
] as const;

export type ViolationCorrectionState =
  (typeof VIOLATION_CORRECTION_STATES)[number];

export const VIOLATION_LEGAL_HOLD_STATES = [
  "none",
  "active",
  "released",
  "unavailable",
] as const;

export type ViolationLegalHoldState =
  (typeof VIOLATION_LEGAL_HOLD_STATES)[number];

/** Canonical AI-output wording before human review; never a final conclusion. */
export const VIOLATION_CATEGORIES = [
  "suspected_littering",
  "suspected_smoking",
  "suspected_uniform_noncompliance",
  "suspected_ppe_noncompliance",
  "facial_recognition_match",
] as const;

export type ViolationCategory = (typeof VIOLATION_CATEGORIES)[number];

export interface ViolationListItem {
  readonly caseId: string;
  readonly caseRef: string;
  readonly category: ViolationCategory;
  readonly occurredAt: string;
  readonly reviewStatus: ViolationCaseStatus;
  readonly appealState: ViolationAppealState;
  readonly correctionState: ViolationCorrectionState;
  readonly legalHoldState: ViolationLegalHoldState;
}

export interface ViolationDetail extends ViolationListItem {
  readonly updatedAt: string;
}

/**
 * View-model actions computed in the application layer from the authoritative
 * session permissions plus active runtime capabilities. Never trusted from a
 * provider payload.
 */
export interface ViolationActions {
  readonly canReview: boolean;
  readonly canCorrect: boolean;
  readonly canExport: boolean;
}

export interface ViolationPage {
  readonly items: readonly ViolationListItem[];
  readonly nextCursor: string | null;
}

export interface ViolationQuery {
  readonly occurredFrom: string;
  readonly occurredTo: string;
  readonly status: ViolationCaseStatus | null;
  readonly cursor: string | null;
  readonly limit: number;
}

export type ViolationQueryValidation =
  | { readonly kind: "valid"; readonly query: ViolationQuery }
  | {
      readonly kind: "invalid";
      readonly errorCode: "VIOLATION_FILTER_INVALID";
    };

export type ViolationActionPermissionCode =
  "violation.review" | "violation.correct" | "violation.export";

export interface OpaqueViolationSummary {
  readonly resourceId: string;
  readonly resourceType: string;
  readonly updatedAt: string;
}

export interface OpaqueViolationEnvelope {
  readonly items: readonly OpaqueViolationSummary[];
  readonly nextCursor: string | null;
  readonly requestId: string;
}

export type OpaqueViolationEnvelopeValidation =
  | { readonly kind: "valid"; readonly value: OpaqueViolationEnvelope }
  | {
      readonly kind: "invalid";
      readonly errorCode: "VIOLATION_RESPONSE_INVALID";
    };

const ALLOWED_QUERY_KEYS = new Set([
  "occurredFrom",
  "occurredTo",
  "status",
  "cursor",
  "limit",
]);
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const MAX_GATEWAY_ITEMS = 200;
const MAX_RANGE_DAYS = 31;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const RESOURCE_TYPE_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,120}$/u;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

export function parseViolationQuery(
  input: unknown,
  today: Date,
): ViolationQueryValidation {
  if (!isRecord(input) || !Number.isFinite(today.getTime())) {
    return invalidQuery();
  }

  const keys = Object.keys(input);
  if (keys.some((key) => !ALLOWED_QUERY_KEYS.has(key))) {
    return invalidQuery();
  }

  const todayDay = today.toISOString().slice(0, 10);
  const occurredFrom = readOptionalString(input, "occurredFrom") ?? todayDay;
  const occurredTo = readOptionalString(input, "occurredTo") ?? todayDay;
  const status = readOptionalString(input, "status");
  const cursor = readOptionalString(input, "cursor");
  const limitValue = readOptionalString(input, "limit");

  if (
    occurredFrom === INVALID_STRING ||
    occurredTo === INVALID_STRING ||
    status === INVALID_STRING ||
    cursor === INVALID_STRING ||
    limitValue === INVALID_STRING
  ) {
    return invalidQuery();
  }
  if (
    occurredFrom === null ||
    occurredTo === null ||
    !isCanonicalDay(occurredFrom) ||
    !isCanonicalDay(occurredTo) ||
    occurredFrom > occurredTo ||
    occurredTo > todayDay
  ) {
    return invalidQuery();
  }
  if (diffInDays(occurredFrom, occurredTo) >= MAX_RANGE_DAYS) {
    return invalidQuery();
  }
  if (status !== null && !(status in VIOLATION_CASE_STATUS_LOOKUP)) {
    return invalidQuery();
  }
  if (cursor !== null && !isValidCursor(cursor)) {
    return invalidQuery();
  }

  const limit = limitValue === null ? DEFAULT_LIMIT : parseLimit(limitValue);
  if (limit === null) {
    return invalidQuery();
  }

  return {
    kind: "valid",
    query: {
      occurredFrom,
      occurredTo,
      status: status as ViolationCaseStatus | null,
      cursor,
      limit,
    },
  };
}

export function parseOpaqueViolationEnvelope(
  input: unknown,
): OpaqueViolationEnvelopeValidation {
  if (
    !isRecord(input) ||
    !hasExactKeys(input, ["items", "next_cursor", "request_id"]) ||
    !Array.isArray(input.items) ||
    input.items.length > MAX_GATEWAY_ITEMS ||
    !isValidCursorOrNull(input.next_cursor) ||
    typeof input.request_id !== "string" ||
    !REQUEST_ID_PATTERN.test(input.request_id)
  ) {
    return invalidEnvelope();
  }

  const items: OpaqueViolationSummary[] = [];
  for (const item of input.items) {
    if (
      !isRecord(item) ||
      !hasExactKeys(item, ["resource_id", "resource_type", "updated_at"]) ||
      typeof item.resource_id !== "string" ||
      !UUID_PATTERN.test(item.resource_id) ||
      typeof item.resource_type !== "string" ||
      !RESOURCE_TYPE_PATTERN.test(item.resource_type) ||
      typeof item.updated_at !== "string" ||
      !isUtcInstant(item.updated_at)
    ) {
      return invalidEnvelope();
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

const VIOLATION_CASE_STATUS_LOOKUP: Record<ViolationCaseStatus, true> = {
  suspected: true,
  pending_review: true,
  needs_evidence: true,
  confirmed: true,
  rejected: true,
  closed: true,
};
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

function isCanonicalDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) {
    return false;
  }
  const parsed = Date.parse(`${value}T00:00:00.000Z`);
  return (
    Number.isFinite(parsed) &&
    new Date(parsed).toISOString().slice(0, 10) === value
  );
}

function diffInDays(from: string, to: string): number {
  const fromMs = Date.parse(`${from}T00:00:00.000Z`);
  const toMs = Date.parse(`${to}T00:00:00.000Z`);
  return Math.round((toMs - fromMs) / 86_400_000);
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

function invalidQuery(): ViolationQueryValidation {
  return { kind: "invalid", errorCode: "VIOLATION_FILTER_INVALID" };
}

function invalidEnvelope(): OpaqueViolationEnvelopeValidation {
  return { kind: "invalid", errorCode: "VIOLATION_RESPONSE_INVALID" };
}
