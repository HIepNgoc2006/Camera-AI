import { AttendanceLoading } from "@/features/attendance/components/attendance-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showAttendanceNavigation>
      <AttendanceLoading />
    </AppShell>
  );
}
