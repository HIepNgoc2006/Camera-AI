import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ViolationListViewState } from "@/features/violations/application/query-violation";
import type {
  ViolationListItem,
  ViolationQuery,
} from "@/features/violations/domain/violation-view";

import { ViolationView } from "./violation-view";

const CASE_ID = "00000000-0000-4000-8000-000000000073";
const QUERY: ViolationQuery = {
  occurredFrom: "2026-08-20",
  occurredTo: "2026-08-21",
  status: null,
  cursor: null,
  limit: 25,
};

function syntheticItem(
  overrides: Partial<ViolationListItem> = {},
): ViolationListItem {
  return {
    caseId: CASE_ID,
    caseRef: "case_fake_0001",
    category: "suspected_littering",
    occurredAt: "2026-08-21T10:00:00.000Z",
    reviewStatus: "pending_review",
    appealState: "not_appealed",
    correctionState: "not_corrected",
    legalHoldState: "none",
    ...overrides,
  };
}

function render(state: ViolationListViewState): string {
  return renderToStaticMarkup(createElement(ViolationView, { state }));
}

const NO_ACTIONS = {
  canReview: false,
  canCorrect: false,
  canExport: false,
} as const;

const REVIEW_ACTIONS = {
  canReview: true,
  canCorrect: false,
  canExport: false,
} as const;

describe("ViolationView", () => {
  it("renders a bounded GET filter form without authorization scope fields", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      actions: NO_ACTIONS,
    });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/violations"');
    expect(html).toContain('name="occurredFrom"');
    expect(html).toContain('name="occurredTo"');
    expect(html).toContain('name="status"');
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="guardian');
    expect(html).not.toContain('name="permission');
    expect(html).not.toContain('name="caseId"');
  });

  it("frames AI output as needing human review, never a final conclusion", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticItem()], nextCursor: null },
      actions: NO_ACTIONS,
    });

    expect(html).toContain("Nghi vấn — cần người xem xét");
    expect(html).toContain("chỉ mang tính nghi vấn");
    expect(html).toContain("Người xem xét mới là người kết luận");
    expect(html).not.toContain("kỷ luật bắt buộc");
  });

  it.each([
    {
      state: {
        kind: "unavailable",
        query: QUERY,
        actions: NO_ACTIONS,
      } as const,
      copy: "Dữ liệu vi phạm tạm thời chưa khả dụng.",
      code: "VIOLATION_UNAVAILABLE",
    },
    {
      state: {
        kind: "validation",
        errorCode: "VIOLATION_FILTER_INVALID",
      } as const,
      copy: "Bộ lọc vi phạm không hợp lệ.",
      code: "VIOLATION_FILTER_INVALID",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Hồ sơ không tồn tại hoặc bạn không có quyền xem.",
      code: "VIOLATION_CASE_UNAVAILABLE",
    },
    {
      state: { kind: "empty", query: QUERY, actions: NO_ACTIONS } as const,
      copy: "Không có hồ sơ vi phạm phù hợp.",
      code: "",
    },
  ])(
    "renders stable $state.kind state without upstream details",
    ({ state, copy, code }) => {
      const html = render(state);

      expect(html).toContain(copy);
      if (state.kind !== "empty") {
        expect(html).toContain(code);
      }
      expect(html).not.toContain("credentialed upstream");
    },
  );

  it("renders the rejected status with explicit false-positive wording", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticItem({ reviewStatus: "rejected" })],
        nextCursor: null,
      },
      actions: NO_ACTIONS,
    });

    expect(html).toContain("Đã loại bỏ (dương tính giả)");
  });

  it("renders legal hold as an independent retention state", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticItem({
            reviewStatus: "pending_review",
            legalHoldState: "active",
          }),
        ],
        nextCursor: null,
      },
      actions: NO_ACTIONS,
    });

    expect(html).toContain("Chờ xem xét");
    expect(html).toContain("Tạm dừng lưu trữ theo yêu cầu pháp lý");
  });

  it("shows review affordance only when the action gate resolves it", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticItem()], nextCursor: null },
      actions: REVIEW_ACTIONS,
    });

    expect(html).toContain("Xem xét");
  });

  it("keeps every action hidden without granted capability", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticItem()], nextCursor: null },
      actions: NO_ACTIONS,
    });

    expect(html).not.toContain("Xem xét");
    expect(html).not.toContain("Xuất báo cáo");
  });

  it("renders appeal and correction overlays independently of status", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticItem({
            appealState: "appealed",
            correctionState: "corrected",
          }),
        ],
        nextCursor: null,
      },
      actions: NO_ACTIONS,
    });

    expect(html).toContain("Đã có yêu cầu phản hồi (appeal)");
    expect(html).toContain("Đã có hiệu chỉnh");
    expect(html).toContain("Chờ xem xét");
  });

  it("does not leak sensitive canary data into markup", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticItem({
            caseRef: "case_fake_0001",
            category: "facial_recognition_match",
          }),
        ],
        nextCursor: "cursor_fake_0000000000001",
      },
      actions: NO_ACTIONS,
    });

    expect(html).not.toContain("SENSITIVE_CANARY_DO_NOT_RENDER");
    expect(html).not.toContain("face_embedding");
    expect(html).not.toContain("https://");
    expect(html).not.toContain("object_key");
  });

  it("keeps pagination link narrow and server-safe", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticItem()], nextCursor: "cursor_fake_0000001" },
      actions: NO_ACTIONS,
    });

    expect(html).toContain("/app/violations?");
    expect(html).toContain("occurredFrom=2026-08-20");
    expect(html).not.toContain("schoolId");
    expect(html).not.toContain("tenantId");
  });
});
