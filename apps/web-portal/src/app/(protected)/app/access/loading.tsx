import { AccessLoading } from "@/features/access/components/access-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showAccessNavigation>
      <AccessLoading />
    </AppShell>
  );
}
