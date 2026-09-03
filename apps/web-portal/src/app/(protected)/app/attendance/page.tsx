import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryAttendanceView } from "@/features/attendance/application/query-attendance";
import { AttendanceView } from "@/features/attendance/components/attendance-view";
import { getAttendanceServerBoundary } from "@/features/attendance/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type AttendanceSearchParams = Record<string, string | string[] | undefined>;

export default async function AttendancePage({
  searchParams,
}: Readonly<{ searchParams: Promise<AttendanceSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getAttendanceServerBoundary();
  const state = await queryAttendanceView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showAttendanceNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "attendance.view_metadata",
    now,
  });

  return (
    <AppShell showAttendanceNavigation={showAttendanceNavigation}>
      <AttendanceView state={state} />
    </AppShell>
  );
}
