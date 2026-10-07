import "server-only";

import type {
  CameraHealthProvider,
  CameraRuntimeCapabilities,
} from "@/features/cameras/application/query-camera";

export const inactiveCameraCapabilities: CameraRuntimeCapabilities = {
  readActive: false,
};

/**
 * Issue #77 ships without an active API Gateway camera health read
 * contract wired to this composition. The approved baseline defines only
 * `GET /api/v1/cameras/status` with cursor paging; synthetic success
 * providers belong in tests only. Camera Registry does not yet write
 * `last_seen_at`, so no freshness verdict is invented client-side.
 */
export const inactiveCameraHealthProvider: CameraHealthProvider = {
  readList: async () => ({
    kind: "unavailable",
    errorCode: "CAMERA_RUNTIME_INACTIVE",
  }),
};

export function getCameraServerBoundary(): {
  readonly provider: CameraHealthProvider;
  readonly capabilities: CameraRuntimeCapabilities;
} {
  return {
    provider: inactiveCameraHealthProvider,
    capabilities: inactiveCameraCapabilities,
  };
}
