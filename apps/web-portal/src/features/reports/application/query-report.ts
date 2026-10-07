import { validateAuthenticatedSessionSnapshot } from "@/features/auth/domain/route-access";
import {
  parseReportQuery,
  type ReportPage,
  type ReportQuery,
  type ReportSummary,
} from "@/features/reports/domain/report-view";
import { isRecord } from "@/shared/validation/type-guards";

export interface ReportRuntimeCapabilities {
  readonly readActive: boolean;
  readonly exportActive: boolean;
}

export interface ReportProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type ReportListProviderResult =
  | { readonly kind: "success"; readonly page: ReportPage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "REPORT_RUNTIME_INACTIVE" | "REPORT_UPSTREAM_UNAVAILABLE";
    };

export interface ReportReadProvider {
  readList(
    input: Readonly<{
      query: ReportQuery;
      scope: ReportProviderScope;
    }>,
  ): Promise<ReportListProviderResult>;
}

export type ReportListViewState =
  | { readonly kind: "denied" }
  | {
      readonly kind: "unavailable";
      readonly query: ReportQuery;
      readonly canExport: boolean;
    }
  | {
      readonly kind: "validation";
      readonly errorCode: "REPORT_FILTER_INVALID";
    }
  | {
      readonly kind: "empty";
      readonly query: ReportQuery;
      readonly canExport: boolean;
    }
  | {
      readonly kind: "success";
      readonly query: ReportQuery;
      readonly page: ReportPage;
      readonly canExport: boolean;
    };

export interface QueryReportListViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: ReportReadProvider;
  readonly capabilities: ReportRuntimeCapabilities;
  readonly now: Date;
}

/** Narrowed active session; owned here, consumed by export gating. */
export type AuthorizedReportSession = NonNullable<
  ReturnType<typeof validateAuthenticatedSessionSnapshot>
>;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

export async function queryReportListView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryReportListViewInput): Promise<ReportListViewState> {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !authenticatedSession.authorization.permissions.includes(
      "report.view_metadata",
    )
  ) {
    return { kind: "denied" };
  }

  const queryValidation = parseReportQuery(rawQuery, now);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  const canExport =
    capabilities.exportActive === true &&
    authenticatedSession.authorization.permissions.includes("report.export");

  if (capabilities.readActive !== true) {
    return unavailableState(queryValidation.query, canExport);
  }

  let result: ReportListProviderResult;
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
    return unavailableState(queryValidation.query, canExport);
  }

  if (!isValidProviderResult(result)) {
    return unavailableState(queryValidation.query, canExport);
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return unavailableState(queryValidation.query, canExport);
  }

  const page = readSafeReportPage(result.page, queryValidation.query);
  if (!page) {
    return unavailableState(queryValidation.query, canExport);
  }

  if (page.items.length === 0) {
    return {
      kind: "empty",
      query: queryValidation.query,
      canExport,
    };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
    canExport,
  };
}

function unavailableState(
  query: ReportQuery,
  canExport: boolean,
): ReportListViewState {
  return { kind: "unavailable", query, canExport };
}

function isValidProviderResult(
  value: unknown,
): value is ReportListProviderResult {
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
    (value.errorCode === "REPORT_RUNTIME_INACTIVE" ||
      value.errorCode === "REPORT_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeReportPage(
  value: unknown,
  query: ReportQuery,
): ReportPage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > query.limit ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const items: ReportSummary[] = [];
  const reportIds = new Set<string>();
  for (const item of value.items) {
    if (!isSafeReportSummary(item, query, reportIds)) {
      return null;
    }
    reportIds.add(item.reportId);
    items.push(item);
  }

  return { items, nextCursor: value.nextCursor };
}

function isSafeReportSummary(
  value: unknown,
  query: ReportQuery,
  reportIds: ReadonlySet<string>,
): value is ReportSummary {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "day",
      "displayLabel",
      "reportId",
      "status",
      "updatedAt",
    ])
  ) {
    return false;
  }

  return (
    typeof value.reportId === "string" &&
    UUID_PATTERN.test(value.reportId) &&
    !reportIds.has(value.reportId) &&
    isSafeLabel(value.displayLabel, 160) &&
    typeof value.day === "string" &&
    value.day === query.day &&
    typeof value.status === "string" &&
    isSafeStatus(value.status) &&
    typeof value.updatedAt === "string" &&
    isUtcInstant(value.updatedAt)
  );
}

function isSafeStatus(value: string): boolean {
  return /^[a-z][a-z0-9_]{0,47}$/u.test(value);
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
