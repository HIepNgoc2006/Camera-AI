import { describe, expect, it } from "vitest";

import {
  inactiveAttendanceCapabilities,
  inactiveAttendanceReadProvider,
} from "./inactive-runtime";

describe("inactive attendance runtime", () => {
  it("keeps read, correction, and linked-child capabilities disabled", () => {
    expect(inactiveAttendanceCapabilities).toEqual({
      readActive: false,
      correctionActive: false,
      linkedChildScopeActive: false,
    });
  });

  it("fails every checked-in attendance read closed", async () => {
    await expect(
      inactiveAttendanceReadProvider.read({
        query: {
          day: "2026-08-22",
          classId: null,
          cursor: null,
          limit: 25,
        },
        scope: {
          tenantId: "tenant_synthetic_0072",
          schoolId: "school_synthetic_0072",
          actorId: "actor_synthetic_0072",
        },
      }),
    ).resolves.toEqual({
      kind: "unavailable",
      errorCode: "ATTENDANCE_RUNTIME_INACTIVE",
    });
  });
});
