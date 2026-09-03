import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({
  children,
  showAttendanceNavigation = false,
}: Readonly<{
  children: ReactNode;
  showAttendanceNavigation?: boolean;
}>) {
  return (
    <div className="shell">
      <header className="shell-header">
        <strong>AI Camera School</strong>
        {showAttendanceNavigation ? (
          <nav className="shell-nav" aria-label="Điều hướng ứng dụng">
            <Link href="/app">Tổng quan</Link>
            <Link href="/app/attendance" aria-current="page">
              Điểm danh
            </Link>
          </nav>
        ) : null}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
