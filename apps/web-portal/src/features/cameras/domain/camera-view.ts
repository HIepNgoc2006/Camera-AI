import { isRecord } from "@/shared/validation/type-guards";

/**
 * Camera/ANSVIS operational health presentation model. The approved API
 * contract defines only `GET /api/v1/cameras/status` (bearer,
 * `camera_status.view_metadata`, school/zone scope, cursor page). Camera
 * Registry does not write `last_seen_at` and no approved monitoring policy
 * pins a freshness threshold, so staleness is never inferred client-side:
 * a missing or unparseable sample time renders as unknown.
 */
export const CAMERA_CONNECTIVITY_STATES = [
  "online",
  "offline",
  "unknown",
] as const;

export type CameraConnectivityState =
  (typeof CAMERA_CONNECTIVITY_STATES)[number];

export const ANSVIS_TASK_STATES = ["running", "stopped", "unknown"] as const;

export type AnsvisTaskState = (typeof ANSVIS_TASK_STATES)[number];

export const EVENT_DELAY_STATES = [
  "flowing",
  "delayed",
  "no_recent_event",
  "unknown",
] as const;

export type EventDelayState = (typeof EVENT_DELAY_STATES)[number];

export const COLLECTION_AVAILABILITY_STATES = [
  "available",
  "unavailable",
  "unknown",
] as const;

export type CollectionAvailabilityState =
  (typeof COLLECTION_AVAILABILITY_STATES)[number];

export interface CameraHealthView {
  readonly cameraId: string;
  readonly displayLabel: string;
  readonly zoneLabel: string;
  readonly connectivity: CameraConnectivityState;
  readonly taskState: AnsvisTaskState;
  readonly eventDelay: EventDelayState;
  readonly lastObservedAt: string | null;
  readonly collection: CollectionAvailabilityState;
}

export interface CameraHealthQuery {
  cursor: string | null;
  limit: number;
}

export type CameraHealthQueryValidation =
  | { readonly kind: "valid"; readonly query: CameraHealthQuery }
  | {
      readonly kind: "invalid";
      readonly errorCode: "CAMERA_FILTER_INVALID";
    };

export interface OpaqueCameraHealthItem {
  readonly resourceId: string;
  readonly resourceType: string;
  readonly updatedAt: string;
}

export interface OpaqueCameraHealthEnvelope {
  readonly items: readonly OpaqueCameraHealthItem[];
  readonly nextCursor: string | null;
  readonly requestId: string;
}

export type OpaqueCameraHealthEnvelopeValidation =
  | { readonly kind: "valid"; readonly value: OpaqueCameraHealthEnvelope }
  | {
      readonly kind: "invalid";
      readonly errorCode: "CAMERA_RESPONSE_INVALID";
    };

const ALLOWED_QUERY_KEYS = new Set(["cursor", "limit"]);
const DEFAULT_LIMIT = 25;
const MAX_LIMIT = 100;
const MAX_GATEWAY_ITEMS = 200;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const OPAQUE_REF_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/u;
const SAFE_CODE_PATTERN = /^[a-z][a-z0-9_]{1,63}$/u;
const REQUEST_ID_PATTERN = /^req_[A-Za-z0-9_-]{8,120}$/u;
const UTC_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;
const CAMERA_RESOURCE_TYPE = "camera";

export function parseCameraHealthQuery(
  input: unknown,
): CameraHealthQueryValidation {
  if (!isRecord(input)) {
    return invalidQuery();
  }

  const keys = Object.keys(input);
  if (keys.some((key) => !ALLOWED_QUERY_KEYS.has(key))) {
    return invalidQuery();
  }

  const cursor = readOptionalString(input, "cursor");
  const limitValue = readOptionalString(input, "limit");
  if (
    cursor === INVALID_STRING ||
    limitValue === INVALID_STRING ||
    (cursor !== null && !isValidCursor(cursor))
  ) {
    return invalidQuery();
  }

  const limit = limitValue === null ? DEFAULT_LIMIT : parseLimit(limitValue);
  if (limit === null) {
    return invalidQuery();
  }

  return {
    kind: "valid",
    query: { cursor, limit },
  };
}

export function parseOpaqueCameraHealthEnvelope(
  input: unknown,
): OpaqueCameraHealthEnvelopeValidation {
  if (
    !isRecord(input) ||
    !hasExactKeys(input, ["items", "next_cursor", "request_id"]) ||
    !Array.isArray(input.items) ||
    input.items.length > MAX_GATEWAY_ITEMS ||
    !isValidCursorOrNull(input.next_cursor) ||
    typeof input.request_id !== "string" ||
    !REQUEST_ID_PATTERN.test(input.request_id)
  ) {
    return { kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" };
  }

  const items: OpaqueCameraHealthItem[] = [];
  for (const item of input.items) {
    if (
      !isRecord(item) ||
      !hasExactKeys(item, ["resource_id", "resource_type", "updated_at"]) ||
      typeof item.resource_id !== "string" ||
      !UUID_PATTERN.test(item.resource_id) ||
      typeof item.resource_type !== "string" ||
      item.resource_type !== CAMERA_RESOURCE_TYPE ||
      typeof item.updated_at !== "string" ||
      !isUtcInstant(item.updated_at)
    ) {
      return { kind: "invalid", errorCode: "CAMERA_RESPONSE_INVALID" };
    }

    items.push({
      resourceId: item.resource_id,
      resourceType: item.resource_type,
      updatedAt: item.updated_at,
    });
  }

  return {
    kind: "valid",
    value: {
      items,
      nextCursor: input.next_cursor,
      requestId: input.request_id,
    },
  };
}

export function isCameraConnectivityState(
  value: unknown,
): value is CameraConnectivityState {
  return (
    typeof value === "string" &&
    (CAMERA_CONNECTIVITY_STATES as readonly string[]).includes(value)
  );
}

export function isAnsvisTaskState(value: unknown): value is AnsvisTaskState {
  return (
    typeof value === "string" &&
    (ANSVIS_TASK_STATES as readonly string[]).includes(value)
  );
}

export function isEventDelayState(value: unknown): value is EventDelayState {
  return (
    typeof value === "string" &&
    (EVENT_DELAY_STATES as readonly string[]).includes(value)
  );
}

export function isCollectionAvailabilityState(
  value: unknown,
): value is CollectionAvailabilityState {
  return (
    typeof value === "string" &&
    (COLLECTION_AVAILABILITY_STATES as readonly string[]).includes(value)
  );
}

export function isValidCameraId(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

export function isValidOpaqueRef(value: unknown): value is string {
  return typeof value === "string" && OPAQUE_REF_PATTERN.test(value);
}

export function isValidStateCode(value: unknown): value is string {
  return typeof value === "string" && SAFE_CODE_PATTERN.test(value);
}

const INVALID_STRING = Symbol("invalid-string");

function readOptionalString(
  input: Record<string, unknown>,
  key: string,
): string | null | typeof INVALID_STRING {
  const value = input[key];
  if (value === undefined) {
    return null;
  }
  return typeof value === "string" && value.length > 0 ? value : INVALID_STRING;
}

function parseLimit(value: string): number | null {
  if (!/^(?:[1-9]|[1-9]\d|100)$/u.test(value)) {
    return null;
  }
  const parsed = Number(value);
  return parsed <= MAX_LIMIT ? parsed : null;
}

function isValidCursor(value: string): boolean {
  return (
    value.length >= 16 &&
    value.length <= 512 &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function isValidCursorOrNull(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && isValidCursor(value));
}

function isUtcInstant(value: string): boolean {
  if (!UTC_INSTANT_PATTERN.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return (
    Number.isFinite(parsed) &&
    new Date(parsed).toISOString() === value &&
    parsed <= Date.now()
  );
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    keys.length === sortedExpected.length &&
    keys.every((key, index) => key === sortedExpected[index])
  );
}

function invalidQuery(): CameraHealthQueryValidation {
  return { kind: "invalid", errorCode: "CAMERA_FILTER_INVALID" };
}
