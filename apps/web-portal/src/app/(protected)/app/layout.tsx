import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { readServerSession } from "@/features/auth/application/session";
import { SessionControls } from "@/features/auth/components/session-controls";
import {
  buildInternalRedirect,
  resolveRouteAccess,
} from "@/features/auth/domain/route-access";

export const dynamic = "force-dynamic";

export default async function ProtectedLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const serverSession = await readServerSession();
  const session =
    serverSession.session ??
    (serverSession.state.status === "unauthenticated" ||
    serverSession.state.status === "expired" ||
    serverSession.state.status === "revoked" ||
    serverSession.state.status === "mfa_required" ||
    serverSession.state.status === "mfa_failed"
      ? { status: "unauthenticated" as const }
      : { status: "unknown" as const });
  const decision = resolveRouteAccess({
    pathname: "/app",
    session,
  });

  if (decision.kind === "redirect") {
    redirect(buildInternalRedirect(decision));
  }

  const expiresAt = serverSession.session
    ? new Date(
        Math.min(
          Date.parse(serverSession.session.absoluteExpiresAt),
          Date.parse(serverSession.session.inactivityExpiresAt),
        ),
      ).toISOString()
    : null;

  return (
    <>
      <SessionControls
        warningInitially={serverSession.state.sessionWarning === true}
        warningStartsAt={serverSession.session?.warningStartsAt ?? null}
        expiresAt={expiresAt}
      />
      {children}
    </>
  );
}
