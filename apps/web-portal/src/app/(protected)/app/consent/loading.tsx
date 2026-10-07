import { ConsentLoading } from "@/features/consent/components/consent-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showConsentNavigation>
      <ConsentLoading />
    </AppShell>
  );
}
