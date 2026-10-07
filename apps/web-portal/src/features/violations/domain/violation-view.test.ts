import { describe, expect, it } from "vitest";

import {
  parseOpaqueViolationEnvelope,
  parseViolationQuery,
} from "./violation-view";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CASE_ID = "00000000-0000-4000-8000-000000000073";
const CURSOR = "cursor_fake_00001";

describe("parseViolationQuery", () => {
  it("accepts resetting a native GET status select to all", () => {
    const query = Object.fromEntries(
      new URLSearchParams(
        "occurredFrom=2026-08-20&occurredTo=2026-08-21&status=",
      ),
    );
    expect(parseViolationQuery(query, NOW)).toEqual(
      parseViolationQuery(
        { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        NOW,
      ),
    );
  });

  it.each(["constructor", "toString", "__proto__", "hasOwnProperty"])(
    "rejects inherited status %s",
    (status) => {
      expect(parseViolationQuery({ status }, NOW).kind).toBe("invalid");
    },
  );
  it("requires a bounded occurred window and defaults page size", () => {
    expect(
      parseViolationQuery(
        { occurredFrom: "2026-08-20", occurredTo: "2026-08-21" },
        NOW,
      ),
    ).toEqual({
      kind: "valid",
      query: {
        occurredFrom: "2026-08-20",
        occurredTo: "2026-08-21",
        status: null,
        cursor: null,
        limit: 25,
      },
    });
  });

  it("accepts only canonical narrowing filters", () => {
    expect(
      parseViolationQuery(
        {
          occurredFrom: "2026-08-20",
          occurredTo: "2026-08-21",
          status: "pending_review",
          cursor: CURSOR,
          limit: "100",
        },
        NOW,
      ),
    ).toEqual({
      kind: "valid",
      query: {
        occurredFrom: "2026-08-20",
        occurredTo: "2026-08-21",
        status: "pending_review",
        cursor: CURSOR,
        limit: 100,
      },
    });
  });

  it.each([
    { occurredFrom: "2026-08-20", occurredTo: "2026-08-21", schoolId: CASE_ID },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      tenantId: "tenant_forged",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      actorId: "actor_forged",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      guardianSubjectRef: "guardian_forged",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      permission: "violation.review",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      classId: CASE_ID,
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      kitchenZoneId: "zone_forged",
    },
  ])("rejects client-controlled authorization scope %j", (rawQuery) => {
    expect(parseViolationQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "VIOLATION_FILTER_INVALID",
    });
  });

  it.each([
    { occurredFrom: "", occurredTo: "2026-08-21" },
    { occurredFrom: "2026-08-20", occurredTo: "" },
    { occurredFrom: "2026-02-30", occurredTo: "2026-03-01" },
    { occurredFrom: "2026-08-21", occurredTo: "2026-08-20" },
    { occurredFrom: "2026-08-20", occurredTo: "2026-08-23" },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      status: "confirmed_by_ai",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      status: "legal_hold",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      status: ["", "confirmed"],
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      cursor: "short",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      limit: "0",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      limit: "101",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      limit: "-5",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-21",
      limit: "abc",
    },
    {
      occurredFrom: "2026-08-20",
      occurredTo: "2026-08-22",
      limit: "1.5",
    },
  ])("rejects malformed or out-of-range filter %j", (rawQuery) => {
    expect(parseViolationQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "VIOLATION_FILTER_INVALID",
    });
  });

  it("rejects future windows beyond today", () => {
    expect(
      parseViolationQuery(
        { occurredFrom: "2026-08-23", occurredTo: "2026-08-24" },
        NOW,
      ),
    ).toEqual({ kind: "invalid", errorCode: "VIOLATION_FILTER_INVALID" });
  });

  it("rejects non-object input", () => {
    expect(parseViolationQuery(null, NOW)).toEqual({
      kind: "invalid",
      errorCode: "VIOLATION_FILTER_INVALID",
    });
    expect(parseViolationQuery(["x"], NOW)).toEqual({
      kind: "invalid",
      errorCode: "VIOLATION_FILTER_INVALID",
    });
  });

  it("rejects array-typed filter values", () => {
    expect(
      parseViolationQuery(
        {
          occurredFrom: ["2026-08-20"],
          occurredTo: "2026-08-21",
        },
        NOW,
      ),
    ).toEqual({ kind: "invalid", errorCode: "VIOLATION_FILTER_INVALID" });
  });
});

describe("parseOpaqueViolationEnvelope", () => {
  const VALID_ITEM = {
    resource_id: CASE_ID,
    resource_type: "violation_case",
    updated_at: "2026-08-22T01:02:03.000Z",
  };
  const VALID_ENVELOPE = {
    items: [VALID_ITEM],
    next_cursor: null,
    request_id: "req_synthetic_0001",
  };

  it("parses a bounded opaque summary envelope", () => {
    expect(parseOpaqueViolationEnvelope(VALID_ENVELOPE)).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: CASE_ID,
            resourceType: "violation_case",
            updatedAt: "2026-08-22T01:02:03.000Z",
          },
        ],
        nextCursor: null,
        requestId: "req_synthetic_0001",
      },
    });
  });

  it("preserves a valid opaque next cursor", () => {
    expect(
      parseOpaqueViolationEnvelope({
        ...VALID_ENVELOPE,
        next_cursor: CURSOR,
      }),
    ).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: CASE_ID,
            resourceType: "violation_case",
            updatedAt: "2026-08-22T01:02:03.000Z",
          },
        ],
        nextCursor: CURSOR,
        requestId: "req_synthetic_0001",
      },
    });
  });

  it("rejects sensitive fields that are not in the opaque contract", () => {
    expect(
      parseOpaqueViolationEnvelope({
        ...VALID_ENVELOPE,
        items: [
          {
            ...VALID_ITEM,
            face_embedding: Array(512).fill(0.01),
          },
        ],
      }),
    ).toEqual({ kind: "invalid", errorCode: "VIOLATION_RESPONSE_INVALID" });
    expect(
      parseOpaqueViolationEnvelope({
        ...VALID_ENVELOPE,
        items: [{ ...VALID_ITEM, evidence_url: "https://s3.example/object" }],
      }),
    ).toEqual({ kind: "invalid", errorCode: "VIOLATION_RESPONSE_INVALID" });
  });

  it.each([
    undefined,
    null,
    "envelope",
    [],
    {},
    { ...VALID_ENVELOPE, extra: 1 },
    { items: [], next_cursor: null },
    { ...VALID_ENVELOPE, request_id: "short" },
    { ...VALID_ENVELOPE, request_id: 42 },
    { ...VALID_ENVELOPE, next_cursor: "   padded" },
    { ...VALID_ENVELOPE, next_cursor: 7 },
    { ...VALID_ENVELOPE, items: "two" },
    { ...VALID_ENVELOPE, items: Array(201).fill(VALID_ITEM) },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, resource_id: "opaque" }] },
    {
      ...VALID_ENVELOPE,
      items: [
        { ...VALID_ITEM, resource_id: "00000000-0000-4000-8000-0000000000" },
      ],
    },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, resource_type: "Case" }] },
    {
      ...VALID_ENVELOPE,
      items: [{ ...VALID_ITEM, updated_at: "2026-08-22T01:02:03Z" }],
    },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, extra_field: 1 }] },
    { ...VALID_ENVELOPE, items: [[VALID_ITEM]] },
  ])("rejects malformed or oversized envelope %j", (rawEnvelope) => {
    expect(parseOpaqueViolationEnvelope(rawEnvelope)).toEqual({
      kind: "invalid",
      errorCode: "VIOLATION_RESPONSE_INVALID",
    });
  });
});
