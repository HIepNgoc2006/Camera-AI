import { isRecord } from "@/shared/validation/type-guards";

/**
 * Report read/export presentation model. The approved API contract defines
 * `GET /api/v1/reports/{report_id}` and `POST /api/v1/report-exports` with
 * opaque resource summaries only; aggregate cells are suppressed until the
 * backend cohort policy confirms the minimum cohort size.
 */
export const REPORT_JOB_STATES = [
  "requested",
  "processing",
  "failed",
  "completed",
  "expired",
] as const;

export type ReportJobState = (typeof REPORT_JOB_STATES)[number];

export const REPORT_FORMATS = ["csv", "xlsx"] as const;

export type ReportFormat = (typeof REPORT_FORMATS)[number];

export const EXPORT_REASONS = [
  "management_report",
  "attendance_audit",
  "timekeeping_audit",
  "violation_review",
] as const;

export type ExportReason = (typeof EXPORT_REASONS)[number];

export interface ReportSummary {
  readonly reportId: string;
  readonly displayLabel: string;
  readonly day: string;
  readonly status: string;
  readonly updatedAt: string;
}

export interface ReportPage {
  readonly items: readonly ReportSummary[];
  readonly nextCursor: string | null;
}

export interface ReportQuery {
  readonly day: string;
  classId: string | null;
  cursor: string | null;
  limit: number;
}

export type ReportQueryValidation =
  | { readonly kind: "valid"; readonly query: ReportQuery }
  | {
      readonly kind: "invalid";
      readonly errorCode: "REPORT_FILTER_INVALID";
    };

export interface OpaqueReportSummary {
  readonly resourceId: string;
  readonly resourceType: string;
  readonly updatedAt: string;
}

export interface OpaqueReportEnvelope {
  readonly items: readonly OpaqueReportSummary[];
  readonly nextCursor: string | null;
  readonly requestId: string;
}

export type OpaqueReportEnvelopeValidation =
  | { readonly kind: "valid"; readonly value: OpaqueReportEnvelope }
  | {
      readonly kind: "invalid";
      readonly errorCode: "REPORT_RESPONSE_INVALID";
    };

const ALLOWED_QUERY_KEYS = new Set(["day", "classId", "cursor", "limit"]);
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const MAX_GATEWAY_ITEMS = 200;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const RESOURCE_TYPE_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,120}$/u;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

export function parseReportQuery(
  input: unknown,
  today: Date,
): ReportQueryValidation {
  if (!isRecord(input) || !Number.isFinite(today.getTime())) {
    return invalidQuery();
  }

  const keys = Object.keys(input);
  if (keys.some((key) => !ALLOWED_QUERY_KEYS.has(key))) {
    return invalidQuery();
  }

  const day = readOptionalString(input, "day") ?? toUtcDay(today);
  const classId = readOptionalString(input, "classId");
  const cursor = readOptionalString(input, "cursor");
  const limitValue = readOptionalString(input, "limit");
  if (
    day === INVALID_STRING ||
    classId === INVALID_STRING ||
    cursor === INVALID_STRING ||
    limitValue === INVALID_STRING ||
    !isCanonicalDay(day) ||
    day > toUtcDay(today) ||
    (classId !== null && !UUID_PATTERN.test(classId)) ||
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
    query: { day, classId, cursor, limit },
  };
}

export function parseOpaqueReportEnvelope(
  input: unknown,
): OpaqueReportEnvelopeValidation {
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

  const items: OpaqueReportSummary[] = [];
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

function toUtcDay(value: Date): string {
  return value.toISOString().slice(0, 10);
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

function invalidQuery(): ReportQueryValidation {
  return { kind: "invalid", errorCode: "REPORT_FILTER_INVALID" };
}

function invalidEnvelope(): OpaqueReportEnvelopeValidation {
  return { kind: "invalid", errorCode: "REPORT_RESPONSE_INVALID" };
}
