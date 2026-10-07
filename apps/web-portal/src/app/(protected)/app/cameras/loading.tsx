import { CameraLoading } from "@/features/cameras/components/camera-loading";
import { AppShell } from "@/features/shell/components/app-shell";

export default function Loading() {
  return (
    <AppShell showCameraNavigation>
      <CameraLoading />
    </AppShell>
  );
}
