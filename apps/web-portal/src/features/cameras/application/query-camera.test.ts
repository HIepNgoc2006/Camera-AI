import { describe, expect, it, vi } from "vitest";

import {
  AUTHORIZATION_POLICY_VERSION,
  WEB_BFF_SESSION_POLICY_VERSION,
  type PermissionCode,
  type SessionSnapshot,
} from "@/features/auth/domain/route-access";
import type { CameraHealthQuery } from "@/features/cameras/domain/camera-view";
import type { CameraHealthView } from "@/features/cameras/domain/camera-view";
import type {
  CameraHealthPage,
  CameraHealthProvider,
  CameraHealthProviderResult,
} from "./query-camera";
import {
  queryCameraHealthListView,
  summarizeCameraHealth,
} from "./query-camera";

const NOW = new Date("2026-10-07T12:00:00.000Z");
const CAMERA_ID = "00000000-0000-4000-8000-00000000007d";

function fakeSession(
  permissions: readonly PermissionCode[],
  overrides: Partial<SessionSnapshot> = {},
): SessionSnapshot {
  return {
    policyVersion: WEB_BFF_SESSION_POLICY_VERSION,
    status: "authenticated",
    actorId: "actor_test_001",
    tenantId: "tenant_test_001",
    schoolId: "school_test_001",
    mfaState: "verified",
    issuedAt: "2026-10-07T00:00:00.000Z",
    warningStartsAt: "2026-10-07T11:30:00.000Z",
    inactivityExpiresAt: "2026-10-07T18:00:00.000Z",
    absoluteExpiresAt: "2026-10-08T00:00:00.000Z",
    authorization: {
      policyVersion: AUTHORIZATION_POLICY_VERSION,
      permissions,
    },
    ...overrides,
  };
}

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

function syntheticPage(): CameraHealthPage {
  return { items: [syntheticView()], nextCursor: null };
}

function providerReturning(
  result: CameraHealthProviderResult,
): CameraHealthProvider {
  return { readList: vi.fn().mockResolvedValue(result) };
}

const VIEW_ONLY: readonly PermissionCode[] = ["camera_status.view_metadata"];

describe("session gate", () => {
  it.each([null, undefined, {}, { status: "unknown" }, "session"])(
    "denies without a valid session (%j)",
    async (session) => {
      const provider = providerReturning({
        kind: "success",
        page: syntheticPage(),
      });
      expect(
        await queryCameraHealthListView({
          session,
          rawQuery: {},
          provider,
          capabilities: { readActive: true },
          now: NOW,
        }),
      ).toEqual({ kind: "denied" });
      expect(provider.readList).not.toHaveBeenCalled();
    },
  );

  it("denies an expired session before any provider call", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: { readActive: true },
        now: new Date("2026-10-09T00:00:00.000Z"),
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("denies an unrelated permission set before any provider call", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryCameraHealthListView({
        session: fakeSession(["report.view_metadata"]),
        rawQuery: {},
        provider,
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "denied" });
    expect(provider.readList).not.toHaveBeenCalled();
  });
});

describe("query validation", () => {
  it("reports deterministic validation failure for forged scope keys", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { zoneId: "zone_evil" },
        provider,
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "CAMERA_FILTER_INVALID" });
    expect(provider.readList).not.toHaveBeenCalled();
  });

  it("reports validation failure for a malformed limit", async () => {
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { limit: "1000" },
        provider: providerReturning({ kind: "success", page: syntheticPage() }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "validation", errorCode: "CAMERA_FILTER_INVALID" });
  });
});

describe("runtime capabilities", () => {
  it("returns unavailable without any provider call when read is inactive", async () => {
    const provider = providerReturning({
      kind: "success",
      page: syntheticPage(),
    });
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider,
        capabilities: { readActive: false },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
    });
    expect(provider.readList).not.toHaveBeenCalled();
  });
});

describe("authorized provider reads", () => {
  it("narrows the authoritative scope from the server session only", async () => {
    const readList = vi
      .fn()
      .mockResolvedValue({ kind: "success", page: syntheticPage() });
    await queryCameraHealthListView({
      session: fakeSession(VIEW_ONLY),
      rawQuery: { limit: "50" },
      provider: { readList },
      capabilities: { readActive: true },
      now: NOW,
    });

    expect(readList).toHaveBeenCalledWith({
      query: { cursor: null, limit: 50 } satisfies CameraHealthQuery,
      scope: {
        tenantId: "tenant_test_001",
        schoolId: "school_test_001",
        actorId: "actor_test_001",
      },
    });
  });

  it("maps provider denial to the public denied state", async () => {
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({ kind: "denied_or_not_found" }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "denied" });
  });

  it("maps an upstream exception to sanitized unavailable", async () => {
    const readList = vi.fn().mockRejectedValue(new Error("internal detail"));
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: { readList },
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
    });
  });

  it("maps a metrics outage to unavailable, not all-cameras-offline", async () => {
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "unavailable",
          errorCode: "CAMERA_UPSTREAM_UNAVAILABLE",
        }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 25 },
    });
  });

  it("returns empty for a page with no rows", async () => {
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: { items: [], nextCursor: null },
        }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({ kind: "empty", query: { cursor: null, limit: 25 } });
  });

  it("returns the decoded page for an authorized actor", async () => {
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: {},
        provider: providerReturning({
          kind: "success",
          page: syntheticPage(),
        }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "success",
      query: { cursor: null, limit: 25 },
      page: syntheticPage(),
    });
  });
});

describe("provider payload safety", () => {
  it.each([
    {
      case: "credential canary",
      override: {},
      extra: { rtsp_url: "SENSITIVE_CANARY_DO_NOT_RENDER" },
    },
    {
      case: "duplicate camera id",
      override: {},
      duplicate: true,
    },
    {
      case: "invented connectivity state",
      override: { connectivity: "degraded" },
    },
    {
      case: "invented task state",
      override: { taskState: "restarting" },
    },
    {
      case: "future sample time",
      override: { lastObservedAt: "2099-01-01T00:00:00.000Z" },
    },
    {
      case: "malformed sample time",
      override: { lastObservedAt: "2026-10-07" },
    },
    {
      case: "unsafe label",
      override: { displayLabel: "x".repeat(200) },
    },
  ] as ReadonlyArray<{
    case: string;
    override?: Partial<CameraHealthView>;
    extra?: Record<string, unknown>;
    duplicate?: boolean;
  }>)(
    "rejects unsafe payload: $case",
    async ({ override, extra, duplicate }) => {
      const row: CameraHealthView = {
        cameraId: CAMERA_ID,
        displayLabel: "Camera cổng — thử nghiệm",
        zoneLabel: "Khu vực cổng",
        connectivity: "online",
        taskState: "running",
        eventDelay: "flowing",
        lastObservedAt: "2026-10-07T11:59:00.000Z",
        collection: "available",
        ...override,
        ...(extra ?? {}),
      } as CameraHealthView;
      const items = duplicate ? [row, row] : [row];
      const result: CameraHealthProviderResult = {
        kind: "success",
        page: { items, nextCursor: null },
      };

      expect(
        await queryCameraHealthListView({
          session: fakeSession(VIEW_ONLY),
          rawQuery: {},
          provider: providerReturning(result),
          capabilities: { readActive: true },
          now: NOW,
        }),
      ).toEqual({
        kind: "unavailable",
        query: { cursor: null, limit: 25 },
      });
    },
  );

  it("rejects page rows above the query limit", async () => {
    const row: CameraHealthView = syntheticView();
    expect(
      await queryCameraHealthListView({
        session: fakeSession(VIEW_ONLY),
        rawQuery: { limit: "1" },
        provider: providerReturning({
          kind: "success",
          page: { items: [row, row], nextCursor: null },
        }),
        capabilities: { readActive: true },
        now: NOW,
      }),
    ).toEqual({
      kind: "unavailable",
      query: { cursor: null, limit: 1 },
    });
  });
});

describe("summarizeCameraHealth", () => {
  it("maps offline connectivity to an offline verdict", () => {
    expect(
      summarizeCameraHealth(
        syntheticView({ connectivity: "offline", taskState: "running" }),
      ),
    ).toEqual({ headline: "Mất kết nối camera", reasonCode: "camera_offline" });
  });

  it("maps a stopped task without claiming AI-quality conclusions", () => {
    expect(
      summarizeCameraHealth(syntheticView({ taskState: "stopped" })),
    ).toEqual({ headline: "Task ANSVIS đã dừng", reasonCode: "task_stopped" });
  });

  it("maps a collector outage to its own verdict", () => {
    expect(
      summarizeCameraHealth(syntheticView({ collection: "unavailable" })),
    ).toEqual({
      headline: "Bộ thu thập không khả dụng",
      reasonCode: "collector_unavailable",
    });
  });

  it("maps no-recent-event and delayed separately", () => {
    expect(
      summarizeCameraHealth(syntheticView({ eventDelay: "no_recent_event" })),
    ).toEqual({
      headline: "Không có sự kiện gần đây",
      reasonCode: "no_recent_event",
    });
    expect(
      summarizeCameraHealth(syntheticView({ eventDelay: "delayed" })),
    ).toEqual({ headline: "Sự kiện bị trễ", reasonCode: "event_delayed" });
  });

  it("renders unknown for unknown inputs instead of inventing offline", () => {
    expect(
      summarizeCameraHealth(
        syntheticView({
          connectivity: "unknown",
          taskState: "unknown",
          eventDelay: "unknown",
          collection: "unknown",
        }),
      ),
    ).toEqual({ headline: "Chưa xác định", reasonCode: "health_unknown" });
  });

  it("renders a healthy camera without implying AI validity", () => {
    expect(summarizeCameraHealth(syntheticView())).toEqual({
      headline: "Đang hoạt động",
      reasonCode: "health_ok",
    });
  });

  it("prioritizes concrete failure reasons over the generic unknown", () => {
    expect(
      summarizeCameraHealth(
        syntheticView({ connectivity: "offline", taskState: "unknown" }),
      ).reasonCode,
    ).toBe("camera_offline");
  });
});
