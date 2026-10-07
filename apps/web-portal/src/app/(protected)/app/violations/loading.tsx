import { ViolationLoading } from "@/features/violations/components/violation-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showViolationNavigation>
      <ViolationLoading />
    </AppShell>
  );
}
