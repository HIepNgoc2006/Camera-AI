import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryViolationListView } from "@/features/violations/application/query-violation";
import { ViolationView } from "@/features/violations/components/violation-view";
import { getViolationServerBoundary } from "@/features/violations/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type ViolationSearchParams = Record<string, string | string[] | undefined>;

export default async function ViolationsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<ViolationSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getViolationServerBoundary();
  const state = await queryViolationListView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showViolationNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "violation.view_metadata",
    now,
  });

  return (
    <AppShell showViolationNavigation={showViolationNavigation}>
      <ViolationView state={state} />
    </AppShell>
  );
}
