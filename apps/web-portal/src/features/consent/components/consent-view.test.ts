import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ConsentListViewState } from "@/features/consent/application/query-consent";
import type {
  ConsentQuery,
  ConsentRecordView,
} from "@/features/consent/domain/consent-view";

import { ConsentView } from "./consent-view";

const CONSENT_ID = "00000000-0000-4000-8000-00000000007c";
const QUERY: ConsentQuery = { cursor: null, limit: 25 };

function syntheticRecord(
  overrides: Partial<ConsentRecordView> = {},
): ConsentRecordView {
  return {
    consentId: CONSENT_ID,
    subjectActorRef: "student_test_002",
    displayLabel: "Đồng ý điểm danh — thử nghiệm",
    purposeCode: "attendance",
    policyVersion: "consent_gate_v1",
    status: "granted",
    scopeSchoolId: "school_test_001",
    validFrom: "2026-09-01T00:00:00.000Z",
    validUntil: null,
    withdrawalState: null,
    version: 2,
    ...overrides,
  };
}

function render(state: ConsentListViewState): string {
  return renderToStaticMarkup(createElement(ConsentView, { state }));
}

const NO_MUTATION = { canRecordDecision: false } as const;

describe("ConsentView", () => {
  it("renders a bounded GET filter form without authorization scope fields", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_MUTATION,
    });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/consent"');
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="guardian');
    expect(html).not.toContain('name="permission');
    expect(html).not.toContain('name="purpose');
  });

  it("explains effective-before-deleted instead of promising instant erasure", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_MUTATION,
    });

    expect(html).toContain("chặn xử lý mới ngay lập tức");
    expect(html).toContain("không phải xóa ngay lập tức");
  });

  it.each([
    {
      state: {
        kind: "unavailable",
        query: QUERY,
        ...NO_MUTATION,
      } as const,
      copy: "Dữ liệu đồng ý tạm thời chưa khả dụng.",
    },
    {
      state: {
        kind: "validation",
        errorCode: "CONSENT_FILTER_INVALID",
      } as const,
      copy: "Tham số truy vấn không hợp lệ.",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Danh sách đồng ý không tồn tại hoặc bạn không có quyền xem.",
    },
    {
      state: { kind: "empty", query: QUERY, ...NO_MUTATION } as const,
      copy: "Không có bản ghi đồng ý phù hợp.",
    },
  ])("renders stable $state.kind state", ({ state, copy }) => {
    const html = render(state);

    expect(html).toContain(copy);
    expect(html).not.toContain("SENSITIVE_CANARY_DO_NOT_RENDER");
    expect(html).not.toContain("identity_document");
  });

  it("keeps the decision affordance hidden without granted capability", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticRecord()], nextCursor: null },
      ...NO_MUTATION,
    });

    expect(html).not.toContain("Ghi nhận quyết định cần quyền");
    expect(html).toContain("—");
  });

  it("marks decisions unavailable even when gated on, never a mutation form", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticRecord()], nextCursor: null },
      canRecordDecision: true,
    });

    expect(html).toContain("hiện chưa khả dụng");
    expect(html).not.toContain('method="post"');
    expect(html).not.toContain('type="password"');
  });

  it("does not render the decision affordance for terminal rows", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticRecord({ status: "withdrawn" })],
        nextCursor: null,
      },
      canRecordDecision: true,
    });

    expect(html).not.toContain("Ghi nhận quyết định cần quyền");
    expect(html).toContain("Đã thu hồi");
  });

  it("renders withdrawal progress separately from consent status", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticRecord({
            status: "withdrawn",
            withdrawalState: "partially_completed",
          }),
        ],
        nextCursor: null,
      },
      ...NO_MUTATION,
    });

    expect(html).toContain("Đã thu hồi");
    expect(html).toContain("Hoàn thành một phần");
  });

  it.each([
    { status: "pending", label: "Chờ xác nhận" },
    { status: "granted", label: "Đã đồng ý" },
    { status: "denied", label: "Đã từ chối" },
    { status: "expired", label: "Hết hạn" },
    { status: "restricted", label: "Bị hạn chế" },
  ])("renders distinct $status label", ({ status, label }) => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticRecord({ status: status as ConsentRecordView["status"] }),
        ],
        nextCursor: null,
      },
      ...NO_MUTATION,
    });

    expect(html).toContain(label);
  });

  it("keeps pagination narrow without scope params", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticRecord()],
        nextCursor: "cursor_fake_00001",
      },
      ...NO_MUTATION,
    });

    expect(html).toContain("/app/consent?");
    expect(html).not.toContain("schoolId");
    expect(html).not.toContain("tenantId");
    expect(html).not.toContain("student_test_002");
  });
});
