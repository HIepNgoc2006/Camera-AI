import { ReportLoading } from "@/features/reports/components/report-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showReportNavigation>
      <ReportLoading />
    </AppShell>
  );
}
