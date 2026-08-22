import { describe, expect, it } from "vitest";

import {
  parseAttendanceQuery,
  parseOpaqueAttendanceEnvelope,
} from "./attendance-view";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CLASS_ID = "00000000-0000-4000-8000-000000000072";
const RECORD_ID = "00000000-0000-4000-8000-000000000073";
const CURSOR = "cursor_fake_00001";

describe("parseAttendanceQuery", () => {
  it("defaults to the current UTC day and a bounded page size", () => {
    expect(parseAttendanceQuery({}, NOW)).toEqual({
      kind: "valid",
      query: {
        day: "2026-08-22",
        classId: null,
        cursor: null,
        limit: 25,
      },
    });
  });

  it("accepts only canonical narrowing filters", () => {
    expect(
      parseAttendanceQuery(
        {
          day: "2026-08-21",
          classId: CLASS_ID,
          cursor: CURSOR,
          limit: "100",
        },
        NOW,
      ),
    ).toEqual({
      kind: "valid",
      query: {
        day: "2026-08-21",
        classId: CLASS_ID,
        cursor: CURSOR,
        limit: 100,
      },
    });
  });

  it.each([
    { school_id: CLASS_ID },
    { schoolId: CLASS_ID },
    { tenantId: "tenant_forged" },
    { actorId: "actor_forged" },
    { guardianSubjectRef: "guardian_forged" },
    { permission: "attendance.correct" },
  ])("rejects client-controlled authorization scope %j", (rawQuery) => {
    expect(parseAttendanceQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_FILTER_INVALID",
    });
  });

  it.each([
    { day: "2026-02-30" },
    { day: "2026-08-23" },
    { day: "22-08-2026" },
    { classId: "class-not-a-uuid" },
    { classId: ` ${CLASS_ID}` },
    { cursor: "short" },
    { cursor: `${CURSOR}\n` },
    { limit: "0" },
    { limit: "101" },
    { limit: "01" },
    { limit: "1.5" },
    { limit: ["25", "50"] },
  ])("rejects malformed or out-of-range filter %j", (rawQuery) => {
    expect(parseAttendanceQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_FILTER_INVALID",
    });
  });

  it("fails closed when the current time is invalid", () => {
    expect(parseAttendanceQuery({}, new Date("invalid"))).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_FILTER_INVALID",
    });
  });
});

describe("parseOpaqueAttendanceEnvelope", () => {
  it("accepts the exact approved opaque cursor-page contract", () => {
    expect(
      parseOpaqueAttendanceEnvelope({
        items: [
          {
            resource_id: RECORD_ID,
            resource_type: "attendance",
            updated_at: "2026-08-22T01:02:03.000Z",
          },
        ],
        next_cursor: CURSOR,
        request_id: "req_synthetic_0072",
      }),
    ).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: RECORD_ID,
            resourceType: "attendance",
            updatedAt: "2026-08-22T01:02:03.000Z",
          },
        ],
        nextCursor: CURSOR,
        requestId: "req_synthetic_0072",
      },
    });
  });

  it("does not infer attendance business fields from opaque summaries", () => {
    expect(
      parseOpaqueAttendanceEnvelope({
        items: [
          {
            resource_id: RECORD_ID,
            resource_type: "attendance",
            updated_at: "2026-08-22T01:02:03.000Z",
            status: "present",
          },
        ],
        next_cursor: null,
        request_id: "req_synthetic_0072",
      }),
    ).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_RESPONSE_INVALID",
    });
  });

  it.each([
    null,
    [],
    { items: [], next_cursor: null },
    {
      items: [],
      next_cursor: null,
      request_id: "req_short",
      secret: "not-allowed",
    },
    {
      items: [
        {
          resource_id: "not-a-uuid",
          resource_type: "attendance",
          updated_at: "2026-08-22T01:02:03.000Z",
        },
      ],
      next_cursor: null,
      request_id: "req_synthetic_0072",
    },
    {
      items: [
        {
          resource_id: RECORD_ID,
          resource_type: "Attendance",
          updated_at: "2026-08-22T01:02:03.000Z",
        },
      ],
      next_cursor: null,
      request_id: "req_synthetic_0072",
    },
    {
      items: [
        {
          resource_id: RECORD_ID,
          resource_type: "attendance",
          updated_at: "not-an-instant",
        },
      ],
      next_cursor: null,
      request_id: "req_synthetic_0072",
    },
  ])("fails malformed gateway envelope closed %#", (input) => {
    expect(parseOpaqueAttendanceEnvelope(input)).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_RESPONSE_INVALID",
    });
  });

  it("rejects a gateway page larger than the approved contract", () => {
    const item = {
      resource_id: RECORD_ID,
      resource_type: "attendance",
      updated_at: "2026-08-22T01:02:03.000Z",
    };

    expect(
      parseOpaqueAttendanceEnvelope({
        items: Array.from({ length: 201 }, () => item),
        next_cursor: null,
        request_id: "req_synthetic_0072",
      }),
    ).toEqual({
      kind: "invalid",
      errorCode: "ATTENDANCE_RESPONSE_INVALID",
    });
  });
});
