import { describe, expect, it } from "vitest";

import {
  CONSENT_MUTATION_KINDS,
  CONSENT_PURPOSES,
  CONSENT_STATES,
  isConsentPurpose,
  isConsentState,
  isTerminalConsentState,
  isWithdrawalState,
  isValidConsentId,
  isValidConsentVersion,
  isValidOpaqueRef,
  isValidPolicyVersionCode,
  MUTATION_PERMISSION_BY_KIND,
  parseConsentQuery,
  parseOpaqueConsentEnvelope,
  WITHDRAWAL_STATES,
} from "./consent-view";

const CONSENT_ID = "00000000-0000-4000-8000-00000000007c";

describe("state and permission matrix", () => {
  it("keeps the consent state machine closed to the policy baseline", () => {
    expect([...CONSENT_STATES]).toEqual([
      "pending",
      "granted",
      "denied",
      "withdrawn",
      "restricted",
      "expired",
    ]);
  });

  it("marks denied, withdrawn, restricted and expired terminal", () => {
    expect(isTerminalConsentState("denied")).toBe(true);
    expect(isTerminalConsentState("withdrawn")).toBe(true);
    expect(isTerminalConsentState("restricted")).toBe(true);
    expect(isTerminalConsentState("expired")).toBe(true);
    expect(isTerminalConsentState("pending")).toBe(false);
    expect(isTerminalConsentState("granted")).toBe(false);
  });

  it("keeps the withdrawal lifecycle closed to policy v1", () => {
    expect([...WITHDRAWAL_STATES]).toEqual([
      "requested",
      "identity_verified",
      "effective",
      "propagating",
      "partially_completed",
      "completed",
      "rejected",
      "superseded",
    ]);
  });

  it("maps record_decision to consent.correct and withdrawal to nothing", () => {
    expect(new Set(CONSENT_MUTATION_KINDS)).toEqual(
      new Set(Object.keys(MUTATION_PERMISSION_BY_KIND)),
    );
    expect(MUTATION_PERMISSION_BY_KIND.record_decision).toBe("consent.correct");
    expect(MUTATION_PERMISSION_BY_KIND.request_withdrawal).toBeNull();
  });

  it("pins the approved purpose codes only", () => {
    expect([...CONSENT_PURPOSES]).toEqual([
      "attendance",
      "timekeeping",
      "emotion",
    ]);
    expect(isConsentPurpose("marketing")).toBe(false);
    expect(isConsentPurpose("attendance")).toBe(true);
  });
});

describe("terminal consent guard", () => {
  it("keeps a withdrawn record outside every regrant path", () => {
    const terminalStates = CONSENT_STATES.filter(isTerminalConsentState);
    expect(terminalStates).toEqual([
      "denied",
      "withdrawn",
      "restricted",
      "expired",
    ]);
  });
});

describe("parseConsentQuery", () => {
  it("defaults to a bounded page with no cursor", () => {
    expect(parseConsentQuery({})).toEqual({
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
    expect(parseConsentQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "CONSENT_FILTER_INVALID",
    });
  });

  it.each(["0", "101", "007", "-5", "1.5", "1e2"])(
    "rejects out-of-bounds limit %s",
    (limit) => {
      expect(parseConsentQuery({ limit })).toEqual({
        kind: "invalid",
        errorCode: "CONSENT_FILTER_INVALID",
      });
    },
  );

  it.each([
    { tenantId: "tenant_test_001" },
    { schoolId: "school_test_001" },
    { actorId: "actor_test_001" },
    { permissions: "consent.view_metadata" },
    { purposeCode: "attendance" },
    { cursor: "cursor_fake_00001", unknown: "x" },
  ])("rejects forged scope keys %j", (input) => {
    expect(parseConsentQuery(input)).toEqual({
      kind: "invalid",
      errorCode: "CONSENT_FILTER_INVALID",
    });
  });
});

describe("parseOpaqueConsentEnvelope", () => {
  const validItem = {
    resource_id: CONSENT_ID,
    resource_type: "consent_record",
    updated_at: "2026-10-01T00:00:00.000Z",
  };

  it("accepts a bounded opaque envelope", () => {
    expect(
      parseOpaqueConsentEnvelope({
        items: [validItem],
        next_cursor: null,
        request_id: "req_0000000076",
      }),
    ).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: CONSENT_ID,
            resourceType: "consent_record",
            updatedAt: "2026-10-01T00:00:00.000Z",
          },
        ],
        nextCursor: null,
        requestId: "req_0000000076",
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
      request_id: "req_0000000076",
      school_id: "school_test_001",
    },
  ])("rejects malformed envelope %j", (input) => {
    expect(parseOpaqueConsentEnvelope(input)).toEqual({
      kind: "invalid",
      errorCode: "CONSENT_RESPONSE_INVALID",
    });
  });

  it("rejects sensitive extra fields on items", () => {
    expect(
      parseOpaqueConsentEnvelope({
        items: [
          {
            ...validItem,
            identity_document: "canary",
          },
        ],
        next_cursor: null,
        request_id: "req_0000000076",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CONSENT_RESPONSE_INVALID" });
  });

  it.each([
    { ...validItem, resource_type: "consent" },
    { ...validItem, resource_type: "identity_proof" },
    { ...validItem, resource_id: "not-a-uuid" },
    { ...validItem, updated_at: "2026-10-01" },
  ])("rejects unsafe item %j", (item) => {
    expect(
      parseOpaqueConsentEnvelope({
        items: [item],
        next_cursor: null,
        request_id: "req_0000000076",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CONSENT_RESPONSE_INVALID" });
  });

  it("rejects item counts above the gateway bound", () => {
    const items = Array.from({ length: 201 }, (_, index) => ({
      ...validItem,
      resource_id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    }));
    expect(
      parseOpaqueConsentEnvelope({
        items,
        next_cursor: null,
        request_id: "req_0000000076",
      }),
    ).toEqual({ kind: "invalid", errorCode: "CONSENT_RESPONSE_INVALID" });
  });
});

describe("validator helpers", () => {
  it.each(["pending", "granted", "withdrawn"])(
    "accepts consent state %s",
    (value) => {
      expect(isConsentState(value)).toBe(true);
    },
  );

  it.each(["", "Granted", "revoked", "superuser"])(
    "rejects consent state %j",
    (value) => {
      expect(isConsentState(value)).toBe(false);
    },
  );

  it.each(["requested", "effective", "partially_completed"])(
    "accepts withdrawal state %s",
    (value) => {
      expect(isWithdrawalState(value)).toBe(true);
    },
  );

  it.each(["", "Completed", "deleted"])(
    "rejects withdrawal state %j",
    (value) => {
      expect(isWithdrawalState(value)).toBe(false);
    },
  );

  it.each([0, 1.5, -1, 2_147_483_648, "3", null])(
    "rejects consent version %j",
    (value) => {
      expect(isValidConsentVersion(value)).toBe(false);
    },
  );

  it("accepts a positive integer consent version", () => {
    expect(isValidConsentVersion(4)).toBe(true);
  });

  it.each([CONSENT_ID])("accepts consent id %s", (value) => {
    expect(isValidConsentId(value)).toBe(true);
  });

  it.each(["", "short", "00000000-0000-4000-8000-0000000000"])(
    "rejects consent id %j",
    (value) => {
      expect(isValidConsentId(value)).toBe(false);
    },
  );

  it.each(["actor_test_001", "guardian:xyz-1", "sub.abc"])(
    "accepts opaque ref %s",
    (value) => {
      expect(isValidOpaqueRef(value)).toBe(true);
    },
  );

  it.each(["", "has space", "new\nline"])("rejects opaque ref %j", (value) => {
    expect(isValidOpaqueRef(value)).toBe(false);
  });

  it.each(["consent_gate_v1", "v2"])("accepts policy version %s", (value) => {
    expect(isValidPolicyVersionCode(value)).toBe(true);
  });

  it.each(["", "Consent_Gate", "v1;drop"])(
    "rejects policy version %j",
    (value) => {
      expect(isValidPolicyVersionCode(value)).toBe(false);
    },
  );
});
