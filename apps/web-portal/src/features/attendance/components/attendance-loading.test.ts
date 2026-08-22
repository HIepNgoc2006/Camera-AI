import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AttendanceLoading } from "./attendance-loading";

describe("AttendanceLoading", () => {
  it("renders a polite busy state without placeholder records", () => {
    const html = renderToStaticMarkup(createElement(AttendanceLoading));

    expect(html).toContain('aria-busy="true"');
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain("Đang tải dữ liệu điểm danh");
    expect(html).not.toContain("Học sinh thử nghiệm");
  });
});
