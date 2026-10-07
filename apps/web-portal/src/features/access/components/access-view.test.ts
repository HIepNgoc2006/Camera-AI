import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { AccessListViewState } from "@/features/access/application/query-access";
import type {
  AccessQuery,
  RoleAssignmentView,
} from "@/features/access/domain/access-view";

import { AccessView } from "./access-view";

const ASSIGNMENT_ID = "00000000-0000-4000-8000-00000000007a";
const QUERY: AccessQuery = { cursor: null, limit: 25 };

function syntheticAssignment(
  overrides: Partial<RoleAssignmentView> = {},
): RoleAssignmentView {
  return {
    assignmentId: ASSIGNMENT_ID,
    subjectActorRef: "actor_test_002",
    displayLabel: "Gán vai trò thử nghiệm",
    roleCode: "school_admin",
    scopeSchoolId: "school_test_001",
    validFrom: "2026-09-01T00:00:00.000Z",
    validUntil: null,
    revokedAt: null,
    status: "active",
    version: 2,
    ...overrides,
  };
}

function render(state: AccessListViewState): string {
  return renderToStaticMarkup(createElement(AccessView, { state }));
}

const NO_MUTATION = { canProposeChange: false } as const;

describe("AccessView", () => {
  it("renders a bounded GET filter form without authorization scope fields", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_MUTATION,
    });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/access"');
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="actor');
    expect(html).not.toContain('name="permission');
    expect(html).not.toContain('name="role');
  });

  it("explains dual-control changes instead of offering instant edits", () => {
    const html = render({
      kind: "unavailable",
      query: QUERY,
      ...NO_MUTATION,
    });

    expect(html).toContain("phê duyệt kép");
  });

  it.each([
    {
      state: {
        kind: "unavailable",
        query: QUERY,
        ...NO_MUTATION,
      } as const,
      copy: "Dữ liệu phân quyền tạm thời chưa khả dụng.",
    },
    {
      state: {
        kind: "validation",
        errorCode: "ACCESS_FILTER_INVALID",
      } as const,
      copy: "Tham số truy vấn không hợp lệ.",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Danh sách phân quyền không tồn tại hoặc bạn không có quyền xem.",
    },
    {
      state: { kind: "empty", query: QUERY, ...NO_MUTATION } as const,
      copy: "Không có gán vai trò phù hợp.",
    },
  ])("renders stable $state.kind state", ({ state, copy }) => {
    const html = render(state);

    expect(html).toContain(copy);
    expect(html).not.toContain("SENSITIVE_CANARY_DO_NOT_RENDER");
    expect(html).not.toContain("argon2$");
  });

  it("keeps the mutation affordance hidden without granted capability", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticAssignment()], nextCursor: null },
      ...NO_MUTATION,
    });

    expect(html).not.toContain("Đề xuất thay đổi cần phê duyệt kép");
    expect(html).toContain("—");
  });

  it("marks the mutation as unavailable even when gated on, never an action form", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticAssignment()], nextCursor: null },
      canProposeChange: true,
    });

    expect(html).toContain("hiện chưa khả dụng");
    expect(html).not.toContain('method="post"');
    expect(html).not.toContain('type="password"');
  });

  it("does not render the mutation affordance for non-active rows", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticAssignment({
            status: "revoked",
            revokedAt: "2026-10-01T00:00:00.000Z",
          }),
        ],
        nextCursor: null,
      },
      canProposeChange: true,
    });

    expect(html).not.toContain("Đề xuất thay đổi cần phê duyệt kép");
    expect(html).toContain("Đã thu hồi");
  });

  it("keeps pagination narrow without scope params", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticAssignment()],
        nextCursor: "cursor_fake_00001",
      },
      ...NO_MUTATION,
    });

    expect(html).toContain("/app/access?");
    expect(html).not.toContain("schoolId");
    expect(html).not.toContain("tenantId");
    expect(html).not.toContain("actor_test_002");
  });

  it("renders distinct status labels instead of color-only cues", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticAssignment({ status: "active" }),
          syntheticAssignment({
            assignmentId: "00000000-0000-4000-8000-00000000007b",
            status: "expired",
            validUntil: "2026-10-01T00:00:00.000Z",
          }),
          syntheticAssignment({
            assignmentId: "00000000-0000-4000-8000-00000000007c",
            status: "revoked",
            revokedAt: "2026-10-01T00:00:00.000Z",
          }),
        ],
        nextCursor: null,
      },
      ...NO_MUTATION,
    });

    expect(html).toContain("Đang hiệu lực");
    expect(html).toContain("Hết hạn");
    expect(html).toContain("Đã thu hồi");
  });
});
