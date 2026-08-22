import "server-only";

import type {
  AttendanceReadProvider,
  AttendanceRuntimeCapabilities,
} from "@/features/attendance/application/query-attendance";
import {
  inactiveAttendanceCapabilities,
  inactiveAttendanceReadProvider,
} from "@/features/attendance/infrastructure/inactive-runtime";

export interface AttendanceServerBoundary {
  readonly provider: AttendanceReadProvider;
  readonly capabilities: AttendanceRuntimeCapabilities;
}

export function getAttendanceServerBoundary(): AttendanceServerBoundary {
  return {
    provider: inactiveAttendanceReadProvider,
    capabilities: inactiveAttendanceCapabilities,
  };
}
