import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { readSessionSnapshot } from "@/features/auth/application/session";
import {
  buildInternalRedirect,
  resolveRouteAccess,
} from "@/features/auth/domain/route-access";

export const dynamic = "force-dynamic";

export default async function AttendanceLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const session = await readSessionSnapshot();
  const decision = resolveRouteAccess({
    pathname: "/app/attendance",
    session,
  });

  if (decision.kind === "redirect") {
    redirect(buildInternalRedirect(decision));
  }

  return children;
}
