import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryConsentListView } from "@/features/consent/application/query-consent";
import { ConsentView } from "@/features/consent/components/consent-view";
import { getConsentServerBoundary } from "@/features/consent/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type ConsentSearchParams = Record<string, string | string[] | undefined>;

export default async function ConsentPage({
  searchParams,
}: Readonly<{ searchParams: Promise<ConsentSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getConsentServerBoundary();
  const state = await queryConsentListView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showConsentNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "consent.view_metadata",
    now,
  });

  return (
    <AppShell showConsentNavigation={showConsentNavigation}>
      <ConsentView state={state} />
    </AppShell>
  );
}
