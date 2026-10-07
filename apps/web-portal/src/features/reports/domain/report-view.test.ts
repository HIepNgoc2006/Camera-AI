import { describe, expect, it } from "vitest";

import { parseOpaqueReportEnvelope, parseReportQuery } from "./report-view";

const NOW = new Date("2026-08-22T12:00:00.000Z");
const CLASS_ID = "00000000-0000-4000-8000-000000000074";
const REPORT_ID = "00000000-0000-4000-8000-000000000075";
const CURSOR = "cursor_fake_00001";

describe("parseReportQuery", () => {
  it("accepts an unselected class submitted by a native GET form", () => {
    const query = Object.fromEntries(
      new URLSearchParams("day=2026-08-22&classId="),
    );
    expect(parseReportQuery(query, NOW)).toEqual(parseReportQuery({}, NOW));
  });
  it("defaults to the current UTC day and a bounded page size", () => {
    expect(parseReportQuery({}, NOW)).toEqual({
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
      parseReportQuery(
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
    { purposeCode: "management_report" },
    { format: "csv" },
    { reason: "attendance_audit" },
    { permission: "report.export" },
    { cohortSize: 5 },
  ])("rejects client-controlled authorization scope %j", (rawQuery) => {
    expect(parseReportQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "REPORT_FILTER_INVALID",
    });
  });

  it.each([
    { day: "2026-02-30" },
    { day: "2026-08-23" },
    { day: "not-a-day" },
    { day: "" },
    { day: ["2026-08-21"] },
    { classId: "opaque-class" },
    { classId: ["", CLASS_ID] },
    { cursor: "short" },
    { cursor: 12 },
    { limit: "0" },
    { limit: "101" },
    { limit: "-3" },
    { limit: "abc" },
  ])("rejects malformed or out-of-range filter %j", (rawQuery) => {
    expect(parseReportQuery(rawQuery, NOW)).toEqual({
      kind: "invalid",
      errorCode: "REPORT_FILTER_INVALID",
    });
  });

  it("rejects non-object input", () => {
    expect(parseReportQuery(null, NOW)).toEqual({
      kind: "invalid",
      errorCode: "REPORT_FILTER_INVALID",
    });
    expect(parseReportQuery("day", NOW)).toEqual({
      kind: "invalid",
      errorCode: "REPORT_FILTER_INVALID",
    });
  });
});

describe("parseOpaqueReportEnvelope", () => {
  const VALID_ITEM = {
    resource_id: REPORT_ID,
    resource_type: "report_summary",
    updated_at: "2026-08-22T01:02:03.000Z",
  };
  const VALID_ENVELOPE = {
    items: [VALID_ITEM],
    next_cursor: null,
    request_id: "req_synthetic_0001",
  };

  it("parses a bounded opaque summary envelope", () => {
    expect(parseOpaqueReportEnvelope(VALID_ENVELOPE)).toEqual({
      kind: "valid",
      value: {
        items: [
          {
            resourceId: REPORT_ID,
            resourceType: "report_summary",
            updatedAt: "2026-08-22T01:02:03.000Z",
          },
        ],
        nextCursor: null,
        requestId: "req_synthetic_0001",
      },
    });
  });

  it("rejects row-level data that is not in the opaque contract", () => {
    expect(
      parseOpaqueReportEnvelope({
        ...VALID_ENVELOPE,
        items: [{ ...VALID_ITEM, student_name: "Canary" }],
      }),
    ).toEqual({ kind: "invalid", errorCode: "REPORT_RESPONSE_INVALID" });
    expect(
      parseOpaqueReportEnvelope({
        ...VALID_ENVELOPE,
        items: [{ ...VALID_ITEM, artifact_url: "https://s3.example/a" }],
      }),
    ).toEqual({ kind: "invalid", errorCode: "REPORT_RESPONSE_INVALID" });
  });

  it.each([
    undefined,
    null,
    5,
    [],
    {},
    { ...VALID_ENVELOPE, extra: 1 },
    { items: [], next_cursor: null },
    { ...VALID_ENVELOPE, request_id: "req" },
    { ...VALID_ENVELOPE, next_cursor: "short" },
    { ...VALID_ENVELOPE, next_cursor: 9 },
    { ...VALID_ENVELOPE, items: "many" },
    { ...VALID_ENVELOPE, items: Array(201).fill(VALID_ITEM) },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, resource_id: "opaque" }] },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, resource_type: "Report" }] },
    {
      ...VALID_ENVELOPE,
      items: [{ ...VALID_ITEM, updated_at: "2026-08-22T01:02:03Z" }],
    },
    { ...VALID_ENVELOPE, items: [{ ...VALID_ITEM, rows: 5 }] },
  ])("rejects malformed or oversized envelope %j", (rawEnvelope) => {
    expect(parseOpaqueReportEnvelope(rawEnvelope)).toEqual({
      kind: "invalid",
      errorCode: "REPORT_RESPONSE_INVALID",
    });
  });
});
