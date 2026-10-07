import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { CameraHealthListViewState } from "@/features/cameras/application/query-camera";
import type {
  CameraHealthQuery,
  CameraHealthView,
} from "@/features/cameras/domain/camera-view";

import { CameraView } from "./camera-view";

const CAMERA_ID = "00000000-0000-4000-8000-00000000007d";
const QUERY: CameraHealthQuery = { cursor: null, limit: 25 };

function syntheticView(
  overrides: Partial<CameraHealthView> = {},
): CameraHealthView {
  return {
    cameraId: CAMERA_ID,
    displayLabel: "Camera cổng — thử nghiệm",
    zoneLabel: "Khu vực cổng",
    connectivity: "online",
    taskState: "running",
    eventDelay: "flowing",
    lastObservedAt: "2026-10-07T11:59:00.000Z",
    collection: "available",
    ...overrides,
  };
}

function render(state: CameraHealthListViewState): string {
  return renderToStaticMarkup(createElement(CameraView, { state }));
}

describe("CameraView", () => {
  it("renders a bounded GET refresh form without authorization scope fields", () => {
    const html = render({ kind: "unavailable", query: QUERY });

    expect(html).toContain('method="get"');
    expect(html).toContain('action="/app/cameras"');
    expect(html).toContain('name="limit"');
    expect(html).not.toContain('name="school');
    expect(html).not.toContain('name="tenant');
    expect(html).not.toContain('name="zone');
    expect(html).not.toContain('name="cameraId');
    expect(html).not.toContain('name="permission');
  });

  it("does not offer live stream or control affordances", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: { items: [syntheticView()], nextCursor: null },
    });

    expect(html).not.toContain("rtsp");
    expect(html).not.toContain('type="password"');
    expect(html).not.toContain("Bật camera");
    expect(html).not.toContain("Tắt camera");
    expect(html).not.toContain("Start task");
  });

  it("states unavailable is not an all-offline verdict", () => {
    const html = render({ kind: "unavailable", query: QUERY });

    expect(html).toContain("Không thể kết luận mọi camera đang mất kết nối");
  });

  it.each([
    {
      state: { kind: "unavailable", query: QUERY } as const,
      copy: "Dữ liệu trạng thái tạm thời chưa khả dụng.",
    },
    {
      state: {
        kind: "validation",
        errorCode: "CAMERA_FILTER_INVALID",
      } as const,
      copy: "Tham số truy vấn không hợp lệ.",
    },
    {
      state: { kind: "denied" } as const,
      copy: "Trạng thái camera không tồn tại hoặc bạn không có quyền xem.",
    },
    {
      state: { kind: "empty", query: QUERY } as const,
      copy: "Không có camera nào trong phạm vi phân quyền.",
    },
  ])("renders stable $state.kind state", ({ state, copy }) => {
    const html = render(state);

    expect(html).toContain(copy);
    expect(html).not.toContain("SENSITIVE_CANARY_DO_NOT_RENDER");
    expect(html).not.toContain("rtsp://");
  });

  it("renders state labels outside color-only cues", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticView(),
          syntheticView({
            cameraId: "00000000-0000-4000-8000-00000000007e",
            connectivity: "offline",
            taskState: "stopped",
            eventDelay: "no_recent_event",
            collection: "unavailable",
          }),
        ],
        nextCursor: null,
      },
    });

    expect(html).toContain("Kết nối tốt");
    expect(html).toContain("Mất kết nối");
    expect(html).toContain("Task đang chạy");
    expect(html).toContain("Task đã dừng");
    expect(html).toContain("Không có sự kiện gần đây");
    expect(html).toContain("Thu thập gián đoạn");
  });

  it("renders diagnosis text instead of raw errors", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [
          syntheticView({ connectivity: "offline", taskState: "stopped" }),
        ],
        nextCursor: null,
      },
    });

    expect(html).toContain("Mất kết nối camera");
    expect(html).not.toContain("Error:");
    expect(html).not.toContain("stack");
  });

  it("marks missing sample time as unknown instead of inventing staleness", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticView({ lastObservedAt: null })],
        nextCursor: null,
      },
    });

    expect(html).toContain("chưa có mẫu");
    expect(html).not.toContain("Quá hạn");
  });

  it("keeps pagination narrow without scope params", () => {
    const html = render({
      kind: "success",
      query: QUERY,
      page: {
        items: [syntheticView()],
        nextCursor: "cursor_fake_00001",
      },
    });

    expect(html).toContain("/app/cameras?");
    expect(html).not.toContain("schoolId");
    expect(html).not.toContain("tenantId");
  });
});
