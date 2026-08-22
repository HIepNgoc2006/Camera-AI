import type {
  AttendanceReadProvider,
  AttendanceRuntimeCapabilities,
} from "@/features/attendance/application/query-attendance";

export const inactiveAttendanceCapabilities: AttendanceRuntimeCapabilities = {
  readActive: false,
  correctionActive: false,
  linkedChildScopeActive: false,
};

/**
 * Issue #72 deliberately ships without an active API Gateway attendance read
 * contract. Synthetic success providers belong in tests only; checked-in
 * runtime composition stays unavailable until a separately approved contract
 * and deployment gate activate it.
 */
export const inactiveAttendanceReadProvider: AttendanceReadProvider = {
  read: async () => ({
    kind: "unavailable",
    errorCode: "ATTENDANCE_RUNTIME_INACTIVE",
  }),
};
