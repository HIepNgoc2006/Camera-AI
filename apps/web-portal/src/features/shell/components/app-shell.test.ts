import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  it("hides attendance navigation unless the server-authorized caller opts in", () => {
    const html = renderToStaticMarkup(
      AppShell({
        children: createElement("p", null, "Nội dung"),
      }),
    );

    expect(html).not.toContain("/app/attendance");
    expect(html).not.toContain("Điểm danh");
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
  });
});
