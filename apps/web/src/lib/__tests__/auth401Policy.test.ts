import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/apiError";
import {
  AUTH_ME_PATH,
  AUTH_SECURITY_CONTEXT_PATH,
  handleApi401Response,
  isCredentialExchangePath,
  isSessionLogout401Path,
} from "../auth401Policy";

function mockResponse(status = 401, body: unknown = {}): Response {
  return {
    status,
    json: async () => body,
  } as Response;
}

function createDeps() {
  return {
    clearStoredToken: vi.fn(),
    redirectToLogin: vi.fn(),
    parseStructuredApiError: vi.fn((_data: unknown) => null as string | null),
    warn: vi.fn(),
  };
}

describe("isCredentialExchangePath", () => {
  it("matches login and register", () => {
    expect(isCredentialExchangePath("/auth/login")).toBe(true);
    expect(isCredentialExchangePath("/auth/register")).toBe(true);
    expect(isCredentialExchangePath("/auth/me")).toBe(false);
  });
});

describe("isSessionLogout401Path", () => {
  it("matches session probe endpoints only", () => {
    expect(isSessionLogout401Path(AUTH_ME_PATH)).toBe(true);
    expect(isSessionLogout401Path(AUTH_SECURITY_CONTEXT_PATH)).toBe(true);
    expect(isSessionLogout401Path("/inventory/summary")).toBe(false);
    expect(isSessionLogout401Path("/api/v1/auth/sessions")).toBe(false);
  });
});

describe("handleApi401Response", () => {
  it("does not clear session on non-session 401", async () => {
    const deps = createDeps();

    await expect(handleApi401Response("/scan-pipeline-dashboard", mockResponse(), deps)).rejects.toThrow(ApiError);

    expect(deps.clearStoredToken).not.toHaveBeenCalled();
    expect(deps.redirectToLogin).not.toHaveBeenCalled();
    expect(deps.warn).toHaveBeenCalledWith("[AUTH] Non-session endpoint returned 401", "/scan-pipeline-dashboard");
  });

  it("clears session and redirects on /auth/me 401", async () => {
    const deps = createDeps();

    await expect(handleApi401Response(AUTH_ME_PATH, mockResponse(), deps)).rejects.toThrow("Authentication required");

    expect(deps.clearStoredToken).toHaveBeenCalledTimes(1);
    expect(deps.redirectToLogin).toHaveBeenCalledTimes(1);
    expect(deps.warn).not.toHaveBeenCalled();
  });

  it("clears session and redirects on security-context 401", async () => {
    const deps = createDeps();

    await expect(handleApi401Response(AUTH_SECURITY_CONTEXT_PATH, mockResponse(), deps)).rejects.toThrow(
      ApiError,
    );

    expect(deps.clearStoredToken).toHaveBeenCalledTimes(1);
    expect(deps.redirectToLogin).toHaveBeenCalledTimes(1);
  });

  it("does not clear session on login credential 401", async () => {
    const deps = createDeps();
    deps.parseStructuredApiError.mockReturnValue("Incorrect email or password");

    await expect(
      handleApi401Response("/auth/login", mockResponse(401, { detail: "Incorrect email or password" }), deps),
    ).rejects.toThrow("Incorrect email or password");

    expect(deps.clearStoredToken).not.toHaveBeenCalled();
    expect(deps.redirectToLogin).not.toHaveBeenCalled();
  });
});
