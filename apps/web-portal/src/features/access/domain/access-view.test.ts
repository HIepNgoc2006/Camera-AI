import { describe, expect, it } from "vitest";

import {
  ACCESS_ASSIGNMENT_STATES,
  ACCESS_MUTATION_KINDS,
  isOwnRoleAssignment,
  isValidAssignmentId,
  isValidAssignmentVersion,
  isValidOpaqueRef,
  isValidRoleCode,
  MUTATION_PERMISSION_BY_KIND,
  parseAccessQuery,
  parseOpaqueAccessEnvelope,
  type RoleAssignmentView,
} from "./access-view";

const ASSIGNMENT_ID = "00000000-0000-4000-8000-00000000007a";

function syntheticAssignment(
  overrides: Partial<RoleAssignmentView> = {},
): RoleAssignmentView {
  return {
    assignmentId: ASSIGNMENT_ID,
    subjectActorRef: "actor_test_001",
    displayLabel: "Gán vai trò thử nghiệm",
    roleCode: "school_admin",
    scopeSchoolId: "school_test_001",
    validFrom: "2026-09-01T00:00:00.000Z",
    validUntil: "2027-09-01T00:00:00.000Z",
    revokedAt: null,
    status: "active",
    version: 3,
    ...overrides,
  };
}

describe("mutation permission mapping", () => {
  it("maps every mutation kind to a permission or structural denial", () => {
    expect(new Set(ACCESS_MUTATION_KINDS)).toEqual(
      new Set(Object.keys(MUTATION_PERMISSION_BY_KIND)),
    );
    expect(MUTATION_PERMISSION_BY_KIND.propose_change).toBe(
      "role_assignment.correct",
    );
    expect(MUTATION_PERMISSION_BY_KIND.approve_change).toBeNull();
    expect(MUTATION_PERMISSION_BY_KIND.revoke_assignment).toBeNull();
  });

  it("never maps approve or revoke to an invented permission code", () => {
    const values = Object.values(MUTATION_PERMISSION_BY_KIND);
    for (const permission of values) {
      if (permission !== null) {
        expect(permission).toBe("role_assignment.correct");
      }
    }
  });
});

describe("own-role guard", () => {
  it("flags an assignment whose subject is the current actor", () => {
    const view = syntheticAssignment({ subjectActorRef: "actor_me_001" });
    expect(isOwnRoleAssignment(view, { actorId: "actor_me_001" })).toBe(true);
  });

  it("keeps other subjects eligible", () => {
    const view = syntheticAssignment();
    expect(isOwnRoleAssignment(view, { actorId: "actor_other_999" })).toBe(
      false,
    );
  });
});

describe("parseAccessQuery", () => {
  it("defaults to a bounded page with no cursor", () => {
    expect(parseAccessQuery({})).toEqual({
      kind: "valid",
      query: { cursor: null, limit: 25 },
    });
  });

  it("accepts an explicit bounded limit", () => {
    expect(parseAccessQuery({ limit: "100" })).toEqual({
      kind: "valid",
      query: { cursor: null, limit: 100 },
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
    expect(parseAccessQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "ACCESS_FILTER_INVALID",
    });
  });

  it.each(["0", "101", "007", "-5", "1.5", "1e2"])(
    "rejects out-of-bounds limit %s",
    (limit) => {
      expect(parseAccessQuery({ limit })).toEqual({
        kind: "invalid",
        errorCode: "ACCESS_FILTER_INVALID",
      });
    },
  );

  it.each(["short", "x".repeat(513), " padded ", "line\nbreak"])(
    "rejects malformed cursor %j",
    (cursor) => {
      expect(parseAccessQuery({ cursor })).toEqual({
        kind: "invalid",
        errorCode: "ACCESS_FILTER_INVALID",
      });
    },
  );

  it.each([
    { tenantId: "tenant_test_001" },
    { schoolId: "school_test_001" },
    { actorId: "actor_test_001" },
    { permissions: "role_assignment.view_metadata" },
    { classId: "00000000-0000-4000-8000-000000000001" },
    { cursor: "cursor_fake_00001", unknown: "x" },
  ])("rejects forged scope keys %j", (input) => {
    expect(parseAccessQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "ACCESS_FILTER_INVALID",
    });
  });
});

describe("parseOpaqueAccessEnvelope", () => {
  const validItem = {
    resource_id: ASSIGNMENT_ID,
    resource_type: "role_assignment",
    updated_at: "2026-10-01T00:00:00.000Z",
  };

  it("accepts a bounded opaque envelope", () => {
    expect(
      parseOpaqueAccessEnvelope({
        items: [validItem],
        next_cursor: null,
        request_id: "req_0000000075",
      }),
    ).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: ASSIGNMENT_ID,
            resourceType: "role_assignment",
            updatedAt: "2026-10-01T00:00:00.000Z",
          },
        ],
        nextCursor: null,
        requestId: "req_0000000075",
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
      request_id: "req_0000000075",
      school_id: "school_test_001",
    },
  ])("rejects malformed envelope %j", (input) => {
    expect(parseOpaqueAccessEnvelope(input)).toEqual({
      kind: "invalid",
      errorCode: "ACCESS_RESPONSE_INVALID",
    });
  });

  it("rejects sensitive extra fields on items", () => {
    expect(
      parseOpaqueAccessEnvelope({
        items: [
          {
            ...validItem,
            password_hash: "argon2$leaked",
          },
        ],
        next_cursor: null,
        request_id: "req_0000000075",
      }),
    ).toEqual({ kind: "invalid", errorCode: "ACCESS_RESPONSE_INVALID" });
  });

  it("rejects item counts above the gateway bound", () => {
    const items = Array.from({ length: 201 }, (_, index) => ({
      ...validItem,
      resource_id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    }));
    expect(
      parseOpaqueAccessEnvelope({
        items,
        next_cursor: null,
        request_id: "req_0000000075",
      }),
    ).toEqual({ kind: "invalid", errorCode: "ACCESS_RESPONSE_INVALID" });
  });

  it.each([
    { ...validItem, resource_type: "RoleAssignment" },
    { ...validItem, resource_type: "user_credential" },
    { ...validItem, resource_id: "not-a-uuid" },
    { ...validItem, updated_at: "2026-10-01" },
  ])("rejects unsafe item %j", (item) => {
    expect(
      parseOpaqueAccessEnvelope({
        items: [item],
        next_cursor: null,
        request_id: "req_0000000075",
      }),
    ).toEqual({ kind: "invalid", errorCode: "ACCESS_RESPONSE_INVALID" });
  });
});

describe("validator helpers", () => {
  it.each([ASSIGNMENT_ID, "ffffffff-ffff-4fff-8fff-ffffffffffff"])(
    "accepts assignment id %s",
    (value) => {
      expect(isValidAssignmentId(value)).toBe(true);
    },
  );

  it.each([
    "",
    "short",
    "00000000-0000-4000-8000-0000000000",
    "000000000000400080000000000007a0",
  ])("rejects assignment id %j", (value) => {
    expect(isValidAssignmentId(value)).toBe(false);
  });

  it.each([0, 1.5, -1, 2_147_483_648, "3", null])(
    "rejects assignment version %j",
    (value) => {
      expect(isValidAssignmentVersion(value)).toBe(false);
    },
  );

  it("accepts a positive integer assignment version", () => {
    expect(isValidAssignmentVersion(1)).toBe(true);
  });

  it.each(["school_admin", "bgh"])("accepts role code %s", (value) => {
    expect(isValidRoleCode(value)).toBe(true);
  });

  it.each(["School_Admin", "school admin", "", "role;drop"])(
    "rejects role code %j",
    (value) => {
      expect(isValidRoleCode(value)).toBe(false);
    },
  );

  it.each(["actor_test_001", "user_abc.123", "sub:xyz-1"])(
    "accepts opaque ref %s",
    (value) => {
      expect(isValidOpaqueRef(value)).toBe(true);
    },
  );

  it.each(["", "has space", "new\nline", `${"a".repeat(129)}`])(
    "rejects opaque ref %j",
    (value) => {
      expect(isValidOpaqueRef(value)).toBe(false);
    },
  );

  it("keeps assignment states closed", () => {
    expect([...ACCESS_ASSIGNMENT_STATES]).toEqual([
      "active",
      "expired",
      "revoked",
    ]);
  });
});
