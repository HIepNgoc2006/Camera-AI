import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { AttendanceViewState } from "@/features/attendance/application/query-attendance";

import { AttendanceView } from "./attendance-view";

const CLASS_ID = "00000000-0000-4000-8000-000000000072";
const QUERY = {
  day: "2026-08-22",
  classId: CLASS_ID,
  cursor: null,
  limit: 25,
} as const;

function render(state: AttendanceViewState): string {
  return renderToStaticMarkup(createElement(AttendanceView, { state }));
}

describe("AttendanceView", () => {
  it("renders a bounded GET filter form without authorization scope fields", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      canCorrect: false,
    });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/attendance"');
    expect(html).toContain('name="day"');
    expect(html).toContain('name="classId"');
    expect(html).toContain(`value="${CLASS_ID}"`);
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="guardian');
    expect(html).not.toContain('name="permission');
  });

  it.each([
    {
      state: {
        kind: "unavailable",
        query: QUERY,
        canCorrect: false,
      } as const,
      copy: "Dữ liệu điểm danh tạm thời chưa khả dụng.",
      code: "ATTENDANCE_UNAVAILABLE",
    },
    {
      state: {
        kind: "validation",
        errorCode: "ATTENDANCE_FILTER_INVALID",
      } as const,
      copy: "Bộ lọc điểm danh không hợp lệ.",
      code: "ATTENDANCE_FILTER_INVALID",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Bản ghi không tồn tại hoặc bạn không có quyền xem.",
      code: "ATTENDANCE_RECORD_UNAVAILABLE",
    },
  ])(
    "renders stable $state.kind state without upstream details",
    ({ state, copy, code }) => {
      const html = render(state);

      expect(html).toContain(copy);
      expect(html).toContain(code);
      expect(html).not.toContain("credentialed upstream");
    },
  );

  it("renders a meaningful empty state and keeps correction hidden", () => {
    const html = render({
      kind: "empty",
      query: QUERY,
      canCorrect: false,
    });

    expect(html).toContain("Không có bản ghi điểm danh phù hợp.");
    expect(html).not.toContain("Hiệu chỉnh");
  });

  it("renders all approved statuses, summaries, and sanitized records", () => {
    const state: AttendanceViewState = {
      kind: "success",
      query: QUERY,
      canCorrect: false,
      page: {
        records: [
          {
            recordId: "00000000-0000-4000-8000-000000000073",
            displayLabel: "Học sinh thử nghiệm 01",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "present",
            updatedAt: "2026-08-22T10:00:00.000Z",
          },
          {
            recordId: "00000000-0000-4000-8000-000000000074",
            displayLabel: "Học sinh thử nghiệm 02",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "late",
            updatedAt: "2026-08-22T10:01:00.000Z",
          },
          {
            recordId: "00000000-0000-4000-8000-000000000075",
            displayLabel: "Học sinh thử nghiệm 03",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "absent",
            updatedAt: "2026-08-22T10:02:00.000Z",
          },
          {
            recordId: "00000000-0000-4000-8000-000000000076",
            displayLabel: "Học sinh thử nghiệm 04",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "pending_review",
            updatedAt: "2026-08-22T10:03:00.000Z",
          },
        ],
        nextCursor: "cursor_fake_00002",
      },
    };
    const html = render(state);

    expect(html).toContain("Có mặt");
    expect(html).toContain("Đi muộn");
    expect(html).toContain("Vắng");
    expect(html).toContain("Chờ duyệt");
    expect(html).toContain("Học sinh thử nghiệm 01");
    expect(html).toContain("Lớp thử nghiệm 10A");
    expect(html).toContain("cursor_fake_00002");
    expect(html).not.toContain("Hiệu chỉnh");
  });

  it("lets React escape an untrusted sanitized display label", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      canCorrect: false,
      page: {
        records: [
          {
            recordId: "00000000-0000-4000-8000-000000000073",
            displayLabel: "<script>alert(1)</script>",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "present",
            updatedAt: "2026-08-22T10:00:00.000Z",
          },
        ],
        nextCursor: null,
      },
    });

    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
  });

  it("renders the correction entry point only for an approved active state", () => {
    const baseState: AttendanceViewState = {
      kind: "success",
      query: QUERY,
      canCorrect: true,
      page: {
        records: [
          {
            recordId: "00000000-0000-4000-8000-000000000073",
            displayLabel: "Học sinh thử nghiệm 01",
            classId: CLASS_ID,
            classLabel: "Lớp thử nghiệm 10A",
            day: "2026-08-22",
            status: "present",
            updatedAt: "2026-08-22T10:00:00.000Z",
          },
        ],
        nextCursor: null,
      },
    };

    expect(render(baseState)).toContain("Hiệu chỉnh");
    expect(render({ ...baseState, canCorrect: false })).not.toContain(
      "Hiệu chỉnh",
    );
  });
});
