import { describe, expect, it } from "vitest";

import {
  ANSVIS_TASK_STATES,
  CAMERA_CONNECTIVITY_STATES,
  COLLECTION_AVAILABILITY_STATES,
  EVENT_DELAY_STATES,
  isAnsvisTaskState,
  isCameraConnectivityState,
  isCollectionAvailabilityState,
  isEventDelayState,
  isValidCameraId,
  isValidOpaqueRef,
  isValidStateCode,
  parseCameraHealthQuery,
  parseOpaqueCameraHealthEnvelope,
} from "./camera-view";

const CAMERA_ID = "00000000-0000-4000-8000-00000000007d";

describe("health state matrix", () => {
  it("keeps connectivity closed and separates unknown from offline", () => {
    expect([...CAMERA_CONNECTIVITY_STATES]).toEqual([
      "online",
      "offline",
      "unknown",
    ]);
  });

  it("keeps task states closed with unknown distinct from stopped", () => {
    expect([...ANSVIS_TASK_STATES]).toEqual(["running", "stopped", "unknown"]);
  });

  it("keeps event delay states closed with no-recent-event distinct", () => {
    expect([...EVENT_DELAY_STATES]).toEqual([
      "flowing",
      "delayed",
      "no_recent_event",
      "unknown",
    ]);
  });

  it("keeps collection availability closed", () => {
    expect([...COLLECTION_AVAILABILITY_STATES]).toEqual([
      "available",
      "unavailable",
      "unknown",
    ]);
  });

  it.each(["online", "offline", "unknown"])(
    "accepts connectivity state %s",
    (value) => {
      expect(isCameraConnectivityState(value)).toBe(true);
    },
  );

  it.each(["", "Online", "streaming"])(
    "rejects connectivity state %j",
    (value) => {
      expect(isCameraConnectivityState(value)).toBe(false);
    },
  );

  it.each(["running", "stopped", "unknown"])(
    "accepts task state %s",
    (value) => {
      expect(isAnsvisTaskState(value)).toBe(true);
    },
  );

  it.each(["", "Stopped", "restarting"])("rejects task state %j", (value) => {
    expect(isAnsvisTaskState(value)).toBe(false);
  });

  it.each(["flowing", "delayed", "no_recent_event", "unknown"])(
    "accepts event delay state %s",
    (value) => {
      expect(isEventDelayState(value)).toBe(true);
    },
  );

  it.each(["", "Flowing", "broken"])(
    "rejects event delay state %j",
    (value) => {
      expect(isEventDelayState(value)).toBe(false);
    },
  );

  it.each(["available", "unavailable", "unknown"])(
    "accepts collection state %s",
    (value) => {
      expect(isCollectionAvailabilityState(value)).toBe(true);
    },
  );

  it.each(["", "Available", "degraded"])(
    "rejects collection state %j",
    (value) => {
      expect(isCollectionAvailabilityState(value)).toBe(false);
    },
  );
});

describe("parseCameraHealthQuery", () => {
  it("defaults to a bounded page with no cursor", () => {
    expect(parseCameraHealthQuery({})).toEqual({
      kind: "valid",
      query: { cursor: null, limit: 25 },
    });
  });

  it.each([
    undefined,
    null,
    "string",
    42,
    ["cursor_fake_00001"],
    { cursor: null },
  ])("rejects malformed input %j", (input) => {
    expect(parseCameraHealthQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "CAMERA_FILTER_INVALID",
    });
  });

  it.each(["0", "101", "007", "-5", "1.5", "1e2"])(
    "rejects out-of-bounds limit %s",
    (limit) => {
      expect(parseCameraHealthQuery({ limit })).toEqual({
        kind: "invalid",
        errorCode: "CAMERA_FILTER_INVALID",
      });
    },
  );

  it.each([
    { tenantId: "tenant_test_001" },
    { schoolId: "school_test_001" },
    { zoneId: "zone_test_001" },
    { cameraId: CAMERA_ID },
    { permissions: "camera_status.view_metadata" },
    { cursor: "cursor_fake_00001", unknown: "x" },
  ])("rejects forged scope keys %j", (input) => {
    expect(parseCameraHealthQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "CAMERA_FILTER_INVALID",
    });
  });
});

describe("parseOpaqueCameraHealthEnvelope", () => {
  const validItem = {
    resource_id: CAMERA_ID,
    resource_type: "camera",
    updated_at: "2026-10-07T11:00:00.000Z",
  };

  it("accepts a bounded opaque envelope", () => {
    expect(
      parseOpaqueCameraHealthEnvelope({
        items: [validItem],
        next_cursor: null,
        request_id: "req_0000000077",
      }),
    ).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: CAMERA_ID,
            resourceType: "camera",
            updatedAt: "2026-10-07T11:00:00.000Z",
          },
        ],
        nextCursor: null,
        requestId: "req_0000000077",
      },
    });
  });

  it.each([
    undefined,
    null,
    "envelope",
    [],
    { items: [validItem], next_cursor: null },
    {
      items: [validItem],
      next_cursor: null,
      request_id: "req_0000000077",
      school_id: "school_test_001",
    },
  ])("rejects malformed envelope %j", (input) => {
    expect(parseOpaqueCameraHealthEnvelope(input)).toEqual({
      kind: "invalid",
      errorCode: "CAMERA_RESPONSE_INVALID",
    });
  });

  it("rejects sensitive extra fields on items", () => {
    expect(
      parseOpaqueCameraHealthEnvelope({
        items: [
          {
            ...validItem,
            rtsp_endpoint_canary: "SENSITIVE_CANARY_DO_NOT_RENDER",
          },
        ],
        next_cursor: null,
        request_id: "req_0000000077",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" });
  });

  it.each([
    { ...validItem, resource_type: "camera_probe" },
    { ...validItem, resource_type: "ansvis_task" },
    { ...validItem, resource_id: "not-a-uuid" },
  ])("rejects unsafe item %j", (item) => {
    expect(
      parseOpaqueCameraHealthEnvelope({
        items: [item],
        next_cursor: null,
        request_id: "req_0000000077",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" });
  });

  it("rejects a future sample timestamp", () => {
    expect(
      parseOpaqueCameraHealthEnvelope({
        items: [
          {
            ...validItem,
            updated_at: "2099-01-01T00:00:00.000Z",
          },
        ],
        next_cursor: null,
        request_id: "req_0000000077",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" });
  });

  it("rejects item counts above the gateway bound", () => {
    const items = Array.from({ length: 201 }, (_, index) => ({
      ...validItem,
      resource_id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    }));
    expect(
      parseOpaqueCameraHealthEnvelope({
        items,
        next_cursor: null,
        request_id: "req_0000000077",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" });
  });
});

describe("validator helpers", () => {
  it.each([CAMERA_ID])("accepts camera id %s", (value) => {
    expect(isValidCameraId(value)).toBe(true);
  });

  it.each(["", "short", "00000000-0000-4000-8000-0000000000"])(
    "rejects camera id %j",
    (value) => {
      expect(isValidCameraId(value)).toBe(false);
    },
  );

  it.each(["camera_test_001", "zone:kitchen-1", "cam.abc"])(
    "accepts opaque ref %s",
    (value) => {
      expect(isValidOpaqueRef(value)).toBe(true);
    },
  );

  it.each(["", "has space", "new\nline"])("rejects opaque ref %j", (value) => {
    expect(isValidOpaqueRef(value)).toBe(false);
  });

  it.each(["camera_status", "v2"])("accepts state code %s", (value) => {
    expect(isValidStateCode(value)).toBe(true);
  });

  it.each(["", "Camera_Status", "v1;drop"])(
    "rejects state code %j",
    (value) => {
      expect(isValidStateCode(value)).toBe(false);
    },
  );
});
