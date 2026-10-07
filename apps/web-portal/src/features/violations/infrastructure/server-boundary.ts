import "server-only";

import type {
  ViolationReadProvider,
  ViolationRuntimeCapabilities,
} from "@/features/violations/application/query-violation";
import {
  inactiveViolationCapabilities,
  inactiveViolationReadProvider,
} from "@/features/violations/infrastructure/inactive-runtime";

export interface ViolationServerBoundary {
  readonly provider: ViolationReadProvider;
  readonly capabilities: ViolationRuntimeCapabilities;
}

export function getViolationServerBoundary(): ViolationServerBoundary {
  return {
    provider: inactiveViolationReadProvider,
    capabilities: inactiveViolationCapabilities,
  };
}
