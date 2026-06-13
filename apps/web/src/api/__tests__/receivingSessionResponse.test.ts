import { describe, expect, it } from "vitest";

import { ApiError } from "../apiError";
import { normalizeReceivingSessionSummaryResponse } from "../client";

describe("normalizeReceivingSessionSummaryResponse", () => {
  it("accepts a top-level session object", () => {
    const response = normalizeReceivingSessionSummaryResponse({ id: 12, status: "PENDING" });
    expect(response.id).toBe(12);
    expect(response.status).toBe("PENDING");
  });

  it("accepts a wrapped session object", () => {
    const response = normalizeReceivingSessionSummaryResponse({ session: { id: 34, status: "ACTIVE" } });
    expect(response.id).toBe(34);
    expect(response.status).toBe("ACTIVE");
  });

  it("accepts a { data } envelope shape defensively", () => {
    const response = normalizeReceivingSessionSummaryResponse({ data: { id: 56, status: "PENDING" } });
    expect(response.id).toBe(56);
    expect(response.status).toBe("PENDING");
  });

  it("throws a friendly error when the response lacks an id", () => {
    expect(() => normalizeReceivingSessionSummaryResponse({ session: {} })).toThrow(ApiError);
    expect(() => normalizeReceivingSessionSummaryResponse({ session: {} })).toThrow(/missing session id/i);
  });
});
