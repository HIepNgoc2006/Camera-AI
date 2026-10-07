import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({
  children,
  showAttendanceNavigation = false,
  showViolationNavigation = false,
  showReportNavigation = false,
  showAccessNavigation = false,
  showConsentNavigation = false,
  showCameraNavigation = false,
}: Readonly<{
  children: ReactNode;
  showAttendanceNavigation?: boolean;
  showViolationNavigation?: boolean;
  showReportNavigation?: boolean;
  showAccessNavigation?: boolean;
  showConsentNavigation?: boolean;
  showCameraNavigation?: boolean;
}>) {
  const showNavigation =
    showAttendanceNavigation ||
    showViolationNavigation ||
    showReportNavigation ||
    showAccessNavigation ||
    showConsentNavigation ||
    showCameraNavigation;

  return (
    <div className="shell">
      <header className="shell-header">
        <strong>AI Camera School</strong>
        {showNavigation ? (
          <nav className="shell-nav" aria-label="Điều hướng ứng dụng">
            <Link href="/app">Tổng quan</Link>
            {showAttendanceNavigation ? (
              <Link href="/app/attendance">Điểm danh</Link>
            ) : null}
            {showViolationNavigation ? (
              <Link href="/app/violations">Vi phạm</Link>
            ) : null}
            {showReportNavigation ? (
              <Link href="/app/reports" aria-current="page">
                Báo cáo
              </Link>
            ) : null}
            {showAccessNavigation ? (
              <Link href="/app/access" aria-current="page">
                Phân quyền
              </Link>
            ) : null}
            {showConsentNavigation ? (
              <Link href="/app/consent" aria-current="page">
                Đồng ý
              </Link>
            ) : null}
            {showCameraNavigation ? (
              <Link href="/app/cameras" aria-current="page">
                Camera
              </Link>
            ) : null}
          </nav>
        ) : null}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
