import {
  isUiActionVisible,
  validateAuthenticatedSessionSnapshot,
} from "@/features/auth/domain/route-access";
import {
  ATTENDANCE_STATUSES,
  parseAttendanceQuery,
  type AttendancePage,
  type AttendanceQuery,
  type AttendanceRecord,
} from "@/features/attendance/domain/attendance-view";

export interface AttendanceRuntimeCapabilities {
  readonly readActive: boolean;
  readonly correctionActive: boolean;
  readonly linkedChildScopeActive: boolean;
}

export interface AttendanceProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type AttendanceProviderResult =
  | { readonly kind: "success"; readonly page: AttendancePage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "ATTENDANCE_RUNTIME_INACTIVE" | "ATTENDANCE_UPSTREAM_UNAVAILABLE";
    };

export interface AttendanceReadProvider {
  read(
    input: Readonly<{
      query: AttendanceQuery;
      scope: AttendanceProviderScope;
    }>,
  ): Promise<AttendanceProviderResult>;
}

export type AttendanceViewState =
  | { readonly kind: "denied" }
  | { readonly kind: "unavailable" }
  | {
      readonly kind: "validation";
      readonly errorCode: "ATTENDANCE_FILTER_INVALID";
    }
  | {
      readonly kind: "empty";
      readonly query: AttendanceQuery;
      readonly canCorrect: boolean;
    }
  | {
      readonly kind: "success";
      readonly query: AttendanceQuery;
      readonly page: AttendancePage;
      readonly canCorrect: boolean;
    };

export interface QueryAttendanceViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: AttendanceReadProvider;
  readonly capabilities: AttendanceRuntimeCapabilities;
  readonly now: Date;
}

const ATTENDANCE_STATUS_SET = new Set<string>(ATTENDANCE_STATUSES);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

export async function queryAttendanceView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryAttendanceViewInput): Promise<AttendanceViewState> {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !authenticatedSession.authorization.permissions.includes(
      "attendance.view_metadata",
    )
  ) {
    return { kind: "denied" };
  }

  const queryValidation = parseAttendanceQuery(rawQuery, now);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  if (capabilities.readActive !== true) {
    return { kind: "unavailable" };
  }

  let result: AttendanceProviderResult;
  try {
    result = await provider.read({
      query: queryValidation.query,
      scope: {
        tenantId: authenticatedSession.tenantId,
        schoolId: authenticatedSession.schoolId,
        actorId: authenticatedSession.actorId,
      },
    });
  } catch {
    return { kind: "unavailable" };
  }

  if (!isValidProviderResult(result)) {
    return { kind: "unavailable" };
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return { kind: "unavailable" };
  }

  const page = readSafeAttendancePage(result.page, queryValidation.query);
  if (!page) {
    return { kind: "unavailable" };
  }

  const canCorrect =
    capabilities.correctionActive === true &&
    isUiActionVisible({
      session: authenticatedSession,
      requiredPermission: "attendance.correct",
      now,
    });

  if (page.records.length === 0) {
    return { kind: "empty", query: queryValidation.query, canCorrect };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
    canCorrect,
  };
}

function isValidProviderResult(
  value: unknown,
): value is AttendanceProviderResult {
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
    (value.errorCode === "ATTENDANCE_RUNTIME_INACTIVE" ||
      value.errorCode === "ATTENDANCE_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeAttendancePage(
  value: unknown,
  query: AttendanceQuery,
): AttendancePage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "records"]) ||
    !Array.isArray(value.records) ||
    value.records.length > query.limit ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const records: AttendanceRecord[] = [];
  const recordIds = new Set<string>();
  for (const record of value.records) {
    if (!isSafeAttendanceRecord(record, query, recordIds)) {
      return null;
    }
    recordIds.add(record.recordId);
    records.push(record);
  }

  return { records, nextCursor: value.nextCursor };
}

function isSafeAttendanceRecord(
  value: unknown,
  query: AttendanceQuery,
  recordIds: ReadonlySet<string>,
): value is AttendanceRecord {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "classId",
      "classLabel",
      "day",
      "displayLabel",
      "recordId",
      "status",
      "updatedAt",
    ])
  ) {
    return false;
  }

  return (
    typeof value.recordId === "string" &&
    UUID_PATTERN.test(value.recordId) &&
    !recordIds.has(value.recordId) &&
    isSafeLabel(value.displayLabel, 160) &&
    typeof value.classId === "string" &&
    UUID_PATTERN.test(value.classId) &&
    (query.classId === null || value.classId === query.classId) &&
    isSafeLabel(value.classLabel, 120) &&
    value.day === query.day &&
    typeof value.status === "string" &&
    ATTENDANCE_STATUS_SET.has(value.status) &&
    typeof value.updatedAt === "string" &&
    isUtcInstant(value.updatedAt)
  );
}

function isSafeLabel(value: unknown, maxLength: number): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maxLength &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
