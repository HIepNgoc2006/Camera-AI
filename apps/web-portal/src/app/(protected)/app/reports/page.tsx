import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryReportListView } from "@/features/reports/application/query-report";
import { ReportView } from "@/features/reports/components/report-view";
import { getReportServerBoundary } from "@/features/reports/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type ReportSearchParams = Record<string, string | string[] | undefined>;

export default async function ReportsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<ReportSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getReportServerBoundary();
  const state = await queryReportListView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showReportNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "report.view_metadata",
    now,
  });

  return (
    <AppShell showReportNavigation={showReportNavigation}>
      <ReportView state={state} />
    </AppShell>
  );
}
