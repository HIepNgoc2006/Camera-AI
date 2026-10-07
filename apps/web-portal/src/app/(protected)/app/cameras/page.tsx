import { readServerSession } from "@/features/auth/application/session";
import { isUiActionVisible } from "@/features/auth/domain/route-access";
import { queryCameraHealthListView } from "@/features/cameras/application/query-camera";
import { CameraView } from "@/features/cameras/components/camera-view";
import { getCameraServerBoundary } from "@/features/cameras/infrastructure/server-boundary";
import { AppShell } from "@/features/shell/components/app-shell";

export const dynamic = "force-dynamic";

type CameraSearchParams = Record<string, string | string[] | undefined>;

export default async function CamerasPage({
  searchParams,
}: Readonly<{ searchParams: Promise<CameraSearchParams> }>) {
  const now = new Date();
  const [rawQuery, serverSession] = await Promise.all([
    searchParams,
    readServerSession(),
  ]);
  const boundary = getCameraServerBoundary();
  const state = await queryCameraHealthListView({
    session: serverSession.session,
    rawQuery,
    provider: boundary.provider,
    capabilities: boundary.capabilities,
    now,
  });
  const showCameraNavigation = isUiActionVisible({
    session: serverSession.session,
    requiredPermission: "camera_status.view_metadata",
    now,
  });

  return (
    <AppShell showCameraNavigation={showCameraNavigation}>
      <CameraView state={state} />
    </AppShell>
  );
}
