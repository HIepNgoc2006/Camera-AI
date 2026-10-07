import { validateAuthenticatedSessionSnapshot } from "@/features/auth/domain/route-access";
import {
  isAnsvisTaskState,
  isCameraConnectivityState,
  isCollectionAvailabilityState,
  isEventDelayState,
  isValidCameraId,
  parseCameraHealthQuery,
  type CameraHealthQuery,
  type CameraHealthView,
} from "@/features/cameras/domain/camera-view";
import { isRecord } from "@/shared/validation/type-guards";

export interface CameraRuntimeCapabilities {
  readonly readActive: boolean;
}

export interface CameraProviderScope {
  readonly tenantId: string;
  readonly schoolId: string;
  readonly actorId: string;
}

export type CameraHealthProviderResult =
  | { readonly kind: "success"; readonly page: CameraHealthPage }
  | { readonly kind: "denied_or_not_found" }
  | {
      readonly kind: "unavailable";
      readonly errorCode:
        "CAMERA_RUNTIME_INACTIVE" | "CAMERA_UPSTREAM_UNAVAILABLE";
    };

export interface CameraHealthProvider {
  readList(
    input: Readonly<{
      query: CameraHealthQuery;
      scope: CameraProviderScope;
    }>,
  ): Promise<CameraHealthProviderResult>;
}

export interface CameraHealthPage {
  readonly items: readonly CameraHealthView[];
  readonly nextCursor: string | null;
}

export type CameraHealthListViewState =
  | { readonly kind: "denied" }
  | { readonly kind: "unavailable"; readonly query: CameraHealthQuery }
  | {
      readonly kind: "validation";
      readonly errorCode: "CAMERA_FILTER_INVALID";
    }
  | { readonly kind: "empty"; readonly query: CameraHealthQuery }
  | {
      readonly kind: "success";
      readonly query: CameraHealthQuery;
      readonly page: CameraHealthPage;
    };

export interface QueryCameraHealthListViewInput {
  readonly session: unknown;
  readonly rawQuery: unknown;
  readonly provider: CameraHealthProvider;
  readonly capabilities: CameraRuntimeCapabilities;
  readonly now: Date;
}

/**
 * The session is revalidated before every provider call; client-supplied
 * tenant/school/zone/permission values are never accepted as scope. The
 * provider is expected to apply the authoritative school/zone scope
 * server-side through the sanctioned Gateway route only.
 */
export async function queryCameraHealthListView({
  session,
  rawQuery,
  provider,
  capabilities,
  now,
}: QueryCameraHealthListViewInput): Promise<CameraHealthListViewState> {
  const authenticatedSession = validateAuthenticatedSessionSnapshot(
    session,
    now,
  );
  if (
    !authenticatedSession ||
    !authenticatedSession.authorization.permissions.includes(
      "camera_status.view_metadata",
    )
  ) {
    return { kind: "denied" };
  }

  const queryValidation = parseCameraHealthQuery(rawQuery);
  if (queryValidation.kind === "invalid") {
    return {
      kind: "validation",
      errorCode: queryValidation.errorCode,
    };
  }

  if (capabilities.readActive !== true) {
    return { kind: "unavailable", query: queryValidation.query };
  }

  let result: CameraHealthProviderResult;
  try {
    result = await provider.readList({
      query: queryValidation.query,
      scope: {
        tenantId: authenticatedSession.tenantId,
        schoolId: authenticatedSession.schoolId,
        actorId: authenticatedSession.actorId,
      },
    });
  } catch {
    return { kind: "unavailable", query: queryValidation.query };
  }

  if (!isValidProviderResult(result)) {
    return { kind: "unavailable", query: queryValidation.query };
  }
  if (result.kind === "denied_or_not_found") {
    return { kind: "denied" };
  }
  if (result.kind === "unavailable") {
    return { kind: "unavailable", query: queryValidation.query };
  }

  const page = readSafeCameraHealthPage(result.page, queryValidation.query);
  if (!page) {
    return { kind: "unavailable", query: queryValidation.query };
  }

  if (page.items.length === 0) {
    return { kind: "empty", query: queryValidation.query };
  }
  return {
    kind: "success",
    query: queryValidation.query,
    page,
  };
}

function isValidProviderResult(
  value: unknown,
): value is CameraHealthProviderResult {
  if (!isRecord(value) || typeof value.kind !== "string") {
    return false;
  }
  if (value.kind === "success") {
    return hasExactKeys(value, ["kind", "page"]);
  }
  if (value.kind === "denied_or_not_found") {
    return hasExactKeys(value, ["kind"]);
  }
  return (
    value.kind === "unavailable" &&
    hasExactKeys(value, ["errorCode", "kind"]) &&
    (value.errorCode === "CAMERA_RUNTIME_INACTIVE" ||
      value.errorCode === "CAMERA_UPSTREAM_UNAVAILABLE")
  );
}

function readSafeCameraHealthPage(
  value: unknown,
  query: CameraHealthQuery,
): CameraHealthPage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["nextCursor", "items"]) ||
    !Array.isArray(value.items) ||
    value.items.length > query.limit ||
    !isValidCursorOrNull(value.nextCursor)
  ) {
    return null;
  }

  const items: CameraHealthView[] = [];
  const cameraIds = new Set<string>();
  for (const item of value.items) {
    if (!isSafeCameraHealthView(item, cameraIds)) {
      return null;
    }
    cameraIds.add(item.cameraId);
    items.push(item);
  }

  return { items, nextCursor: value.nextCursor };
}

function isSafeCameraHealthView(
  value: unknown,
  cameraIds: ReadonlySet<string>,
): value is CameraHealthView {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      "cameraId",
      "collection",
      "connectivity",
      "displayLabel",
      "eventDelay",
      "lastObservedAt",
      "taskState",
      "zoneLabel",
    ])
  ) {
    return false;
  }

  if (
    typeof value.cameraId !== "string" ||
    !isValidCameraId(value.cameraId) ||
    cameraIds.has(value.cameraId) ||
    typeof value.displayLabel !== "string" ||
    !isSafeLabel(value.displayLabel) ||
    typeof value.zoneLabel !== "string" ||
    !isSafeLabel(value.zoneLabel) ||
    !isCameraConnectivityState(value.connectivity) ||
    !isAnsvisTaskState(value.taskState) ||
    !isEventDelayState(value.eventDelay) ||
    !isCollectionAvailabilityState(value.collection)
  ) {
    return false;
  }

  return (
    value.lastObservedAt === null ||
    (typeof value.lastObservedAt === "string" &&
      isSafeInstant(value.lastObservedAt) &&
      Date.parse(value.lastObservedAt) <= Date.now())
  );
}

/**
 * Maps the allowed sanitized fields onto a diagnosis summary. Unknown or
 * missing state codes render as neutral unknown text — never an invented
 * offline verdict or an AI-quality conclusion.
 */
export function summarizeCameraHealth(view: CameraHealthView): Readonly<{
  headline: string;
  reasonCode: string;
}> {
  if (view.connectivity === "offline") {
    return { headline: "Mất kết nối camera", reasonCode: "camera_offline" };
  }
  if (view.taskState === "stopped") {
    return { headline: "Task ANSVIS đã dừng", reasonCode: "task_stopped" };
  }
  if (view.collection === "unavailable") {
    return {
      headline: "Bộ thu thập không khả dụng",
      reasonCode: "collector_unavailable",
    };
  }
  if (view.eventDelay === "no_recent_event") {
    return {
      headline: "Không có sự kiện gần đây",
      reasonCode: "no_recent_event",
    };
  }
  if (view.eventDelay === "delayed") {
    return { headline: "Sự kiện bị trễ", reasonCode: "event_delayed" };
  }
  if (
    view.connectivity === "unknown" ||
    view.taskState === "unknown" ||
    view.eventDelay === "unknown" ||
    view.collection === "unknown"
  ) {
    return { headline: "Chưa xác định", reasonCode: "health_unknown" };
  }
  return { headline: "Đang hoạt động", reasonCode: "health_ok" };
}

function isSafeLabel(value: unknown, maxLength = 160): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maxLength &&
    value.trim() === value &&
    !/[\u0000-\u001f\u007f]/u.test(value)
  );
}

function isSafeInstant(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value;
}

function isValidCursorOrNull(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value.length >= 16 &&
      value.length <= 512 &&
      value.trim() === value &&
      !/[\u0000-\u001f\u007f]/u.test(value))
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
