import type {
  ViolationReadProvider,
  ViolationRuntimeCapabilities,
} from "@/features/violations/application/query-violation";

export const inactiveViolationCapabilities: ViolationRuntimeCapabilities = {
  readActive: false,
  reviewActive: false,
  correctionActive: false,
  exportActive: false,
};

/**
 * Issue #73 deliberately ships without an active API Gateway violation read
 * contract. Synthetic success providers belong in tests only; checked-in
 * runtime composition stays unavailable until a separately approved contract
 * and deployment gate activate it. Review/correction/export mutations stay
 * disabled for the same reason; appeal and evidence permissions have no
 * approved mapping in this composition and must not be invented here.
 */
export const inactiveViolationReadProvider: ViolationReadProvider = {
  readList: async () => ({
    kind: "unavailable",
    errorCode: "VIOLATION_RUNTIME_INACTIVE",
  }),
  readDetail: async () => ({
    kind: "unavailable",
    errorCode: "VIOLATION_RUNTIME_INACTIVE",
  }),
};
