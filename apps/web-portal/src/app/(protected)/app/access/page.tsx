import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryAccessListView } from "@/features/access/application/query-access";
import { AccessView } from "@/features/access/components/access-view";
import { getAccessServerBoundary } from "@/features/access/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type AccessSearchParams = Record<string, string | string[] | undefined>;

export default async function AccessPage({
  searchParams,
}: Readonly<{ searchParams: Promise<AccessSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getAccessServerBoundary();
  const state = await queryAccessListView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showAccessNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "role_assignment.view_metadata",
    now,
  });

  return (
    <AppShell showAccessNavigation={showAccessNavigation}>
      <AccessView state={state} />
    </AppShell>
  );
}
