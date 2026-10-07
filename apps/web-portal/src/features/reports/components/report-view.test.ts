import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ReportListViewState } from "@/features/reports/application/query-report";
import type {
  ReportQuery,
  ReportSummary,
} from "@/features/reports/domain/report-view";

import { ReportView } from "./report-view";

const CLASS_ID = "00000000-0000-4000-8000-000000000074";
const QUERY: ReportQuery = {
  day: "2026-08-22",
  classId: CLASS_ID,
  cursor: null,
  limit: 25,
};

function syntheticSummary(
  overrides: Partial<ReportSummary> = {},
): ReportSummary {
  return {
    reportId: "00000000-0000-4000-8000-000000000075",
    displayLabel: "Báo cáo thử nghiệm ngày 22/08",
    day: "2026-08-22",
    status: "available",
    updatedAt: "2026-08-22T10:00:00.000Z",
    ...overrides,
  };
}

function render(state: ReportListViewState): string {
  return renderToStaticMarkup(createElement(ReportView, { state }));
}

const NO_EXPORT = { canExport: false } as const;

describe("ReportView", () => {
  it("renders a bounded GET filter form without authorization scope fields", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_EXPORT,
    });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/reports"');
    expect(html).toContain('name="day"');
    expect(html).toContain('name="classId"');
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="format');
    expect(html).not.toContain('name="reason');
    expect(html).not.toContain('name="permission');
  });

  it("explains cohort suppression instead of showing zero", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_EXPORT,
    });

    expect(html).toContain("dưới ngưỡng đoàn thể tối thiểu");
  });

  it.each([
    {
      state: {
        kind: "unavailable",
        query: QUERY,
        ...NO_EXPORT,
      } as const,
      copy: "Dữ liệu báo cáo tạm thời chưa khả dụng.",
    },
    {
      state: {
        kind: "validation",
        errorCode: "REPORT_FILTER_INVALID",
      } as const,
      copy: "Bộ lọc báo cáo không hợp lệ.",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Báo cáo không tồn tại hoặc bạn không có quyền xem.",
    },
    {
      state: { kind: "empty", query: QUERY, ...NO_EXPORT } as const,
      copy: "Không có báo cáo phù hợp.",
    },
  ])("renders stable $state.kind state", ({ state, copy }) => {
    const html = render(state);

    expect(html).toContain(copy);
    expect(html).not.toContain("credentialed upstream");
    expect(html).not.toContain("SENSITIVE_CANARY_DO_NOT_RENDER");
  });

  it("keeps export affordance hidden without granted capability", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticSummary()], nextCursor: null },
      ...NO_EXPORT,
    });

    expect(html).not.toContain("Xuất dữ liệu cần phê duyệt kép");
    expect(html).toContain("—");
  });

  it("marks export as unavailable even when gated on, never a download link", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticSummary()], nextCursor: null },
      canExport: true,
    });

    expect(html).toContain("chưa khả dụng");
    expect(html).not.toContain("download");
    expect(html).not.toContain("https://");
  });

  it("keeps pagination narrow without scope params", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticSummary()], nextCursor: "cursor_fake_00001" },
      ...NO_EXPORT,
    });

    expect(html).toContain("/app/reports?");
    expect(html).not.toContain("schoolId");
    expect(html).not.toContain("tenantId");
  });
});
