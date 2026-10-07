import { describe, expect, it, vi } from "vitest";

import {
  inactiveAccessMutationProvider,
  type AccessMutationSubmitProvider,
} from "./submit-access-action";

describe("inactiveAccessMutationProvider", () => {
  it("denies every submission while no runtime is approved", async () => {
    expect(
      await inactiveAccessMutationProvider.submit({
        request: {
          assignmentId: "00000000-0000-4000-8000-00000000007a",
          kind: "propose_change",
          expectedVersion: 2,
          grantRef: "grant_test_001",
        },
        scope: {
          tenantId: "tenant_test_001",
          schoolId: "school_test_001",
          actorId: "actor_test_001",
        },
      }),
    ).toEqual({
      kind: "unavailable",
      errorCode: "ACCESS_MUTATION_INACTIVE",
    });
  });
});

describe("provider contract", () => {
  it("never resolves an accepted result from the checked-in provider", async () => {
    const provider: AccessMutationSubmitProvider =
      inactiveAccessMutationProvider;
    const spy = vi.spyOn(provider, "submit");
    await provider.submit({
      request: {
        assignmentId: "00000000-0000-4000-8000-00000000007a",
        kind: "approve_change",
        expectedVersion: 1,
        grantRef: "grant_test_001",
      },
      scope: {
        tenantId: "tenant_test_001",
        schoolId: "school_test_001",
        actorId: "actor_test_001",
      },
    });

    expect(spy).toHaveBeenCalledTimes(1);
    expect(await spy.mock.results[0]?.value).not.toMatchObject({
      kind: "accepted",
    });
  });
});
