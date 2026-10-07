import "server-only";

import type {
  ReportReadProvider,
  ReportRuntimeCapabilities,
} from "@/features/reports/application/query-report";

export const inactiveReportCapabilities: ReportRuntimeCapabilities = {
  readActive: false,
  exportActive: false,
};

/**
 * Issue #74 ships without an active API Gateway report read contract. The
 * approved baseline defines only `GET /api/v1/reports/{report_id}` with
 * opaque envelopes and no list operation; synthetic success providers belong
 * in tests only. Export submission is likewise denied until `report.export`
 * has an approved dual-control runtime.
 */
export const inactiveReportReadProvider: ReportReadProvider = {
  readList: async () => ({
    kind: "unavailable",
    errorCode: "REPORT_RUNTIME_INACTIVE",
  }),
};

export function getReportServerBoundary(): {
  readonly provider: ReportReadProvider;
  readonly capabilities: ReportRuntimeCapabilities;
} {
  return {
    provider: inactiveReportReadProvider,
    capabilities: inactiveReportCapabilities,
  };
}
