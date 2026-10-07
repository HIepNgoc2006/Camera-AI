import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  it("hides all navigation unless the server-authorized caller opts in", () => {
    const html = renderToStaticMarkup(
      AppShell({
        children: createElement("p", null, "Nội dung"),
      }),
    );

    expect(html).not.toContain("/app/attendance");
    expect(html).not.toContain("Điểm danh");
    expect(html).not.toContain("/app/violations");
    expect(html).not.toContain("Vi phạm");
  });

  it("renders the attendance navigation for an authorized feature page", () => {
    const html = renderToStaticMarkup(
      AppShell({
        showAttendanceNavigation: true,
        children: createElement("p", null, "Nội dung"),
      }),
    );

    expect(html).toContain('aria-label="Điều hướng ứng dụng"');
    expect(html).toContain('href="/app/attendance"');
    expect(html).toContain("Điểm danh");
    expect(html).not.toContain('href="/app/violations"');
  });

  it("renders the violation navigation only for an authorized feature page", () => {
    const html = renderToStaticMarkup(
      AppShell({
        showViolationNavigation: true,
        children: createElement("p", null, "Nội dung"),
      }),
    );

    expect(html).toContain('aria-label="Điều hướng ứng dụng"');
    expect(html).toContain('href="/app/violations"');
    expect(html).toContain("Vi phạm");
    expect(html).not.toContain('href="/app/attendance"');
  });

  it("keeps each feature link independent when both gates are granted", () => {
    const html = renderToStaticMarkup(
      AppShell({
        showAttendanceNavigation: true,
        showViolationNavigation: true,
        children: createElement("p", null, "Nội dung"),
      }),
    );

    expect(html).toContain('href="/app/attendance"');
    expect(html).toContain('href="/app/violations"');
  });
});
