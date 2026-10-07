import { describe, expect, it, vi } from "vitest";

import {
  inactiveConsentMutationProvider,
  type ConsentMutationSubmitProvider,
} from "./submit-consent-action";

const CONSENT_ID = "00000000-0000-4000-8000-00000000007c";

describe("inactiveConsentMutationProvider", () => {
  it("denies every decision submission while no runtime is approved", async () => {
    expect(
      await inactiveConsentMutationProvider.submit({
        request: {
          consentId: CONSENT_ID,
          kind: "record_decision",
          expectedVersion: 2,
          decisionCode: "granted",
        },
        scope: {
          tenantId: "tenant_test_001",
          schoolId: "school_test_001",
          actorId: "actor_test_001",
        },
      }),
    ).toEqual({
      kind: "unavailable",
      errorCode: "CONSENT_MUTATION_INACTIVE",
    });
  });

  it("denies withdrawal requests identically", async () => {
    expect(
      await inactiveConsentMutationProvider.submit({
        request: {
          consentId: CONSENT_ID,
          kind: "request_withdrawal",
          expectedVersion: 3,
          decisionCode: "withdraw",
        },
        scope: {
          tenantId: "tenant_test_001",
          schoolId: "school_test_001",
          actorId: "actor_test_001",
        },
      }),
    ).toEqual({
      kind: "unavailable",
      errorCode: "CONSENT_MUTATION_INACTIVE",
    });
  });
});

describe("provider contract", () => {
  it("never resolves an accepted result from the checked-in provider", async () => {
    const provider: ConsentMutationSubmitProvider =
      inactiveConsentMutationProvider;
    const spy = vi.spyOn(provider, "submit");
    await provider.submit({
      request: {
        consentId: CONSENT_ID,
        kind: "record_decision",
        expectedVersion: 1,
        decisionCode: "granted",
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
