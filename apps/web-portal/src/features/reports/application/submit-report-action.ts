import type {
  ReportFormat,
  ReportJobState,
} from "@/features/reports/domain/report-view";

export interface ReportExportRequest {
  readonly reportId: string;
  readonly format: ReportFormat;
  readonly reason: string;
}

export type ReportExportSubmitResult =
  | { readonly kind: "denied" }
  | { readonly kind: "validation" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "REPORT_EXPORT_INACTIVE" | "REPORT_EXPORT_UPSTREAM_UNAVAILABLE";
    }
  | {
      readonly kind: "accepted";
      readonly job: {
        readonly exportRef: string;
        readonly state: Extract<ReportJobState, "requested" | "processing">;
        readonly retryAfterSeconds: number | null;
      };
    };

export interface ReportExportSubmitProvider {
  submit(
    input: Readonly<{
      request: ReportExportRequest;
      scope: Readonly<{
        tenantId: string;
        schoolId: string;
        actorId: string;
      }>;
    }>,
  ): Promise<ReportExportSubmitResult>;
}

/**
 * Issue #74 ships the export action fail-closed. The approved contract only
 * defines `POST /api/v1/report-exports` with `report.export` under dual
 * control; no approved runtime activation exists in this composition, so the
 * checked-in provider denies every submission and no signed URL, artifact
 * reference, or download state is ever produced here.
 */
export const inactiveReportExportProvider: ReportExportSubmitProvider = {
  submit: async () => ({
    kind: "unavailable",
    errorCode: "REPORT_EXPORT_INACTIVE",
  }),
};
