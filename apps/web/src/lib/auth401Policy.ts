import { ApiError } from "../api/apiError";

export const AUTH_ME_PATH = "/auth/me";
export const AUTH_SECURITY_CONTEXT_PATH = "/api/v1/auth/security-context";

export function isCredentialExchangePath(path: string): boolean {
  return path === "/auth/login" || path === "/auth/register" || path.startsWith("/auth/login?");
}

/** Endpoints whose 401 means the session is invalid and the client should log out. */
export function isSessionLogout401Path(path: string): boolean {
  return path === AUTH_ME_PATH || path === AUTH_SECURITY_CONTEXT_PATH;
}

export type Api401HandlerDeps = {
  clearStoredToken: () => void;
  redirectToLogin: () => void;
  parseStructuredApiError: (data: unknown) => string | null;
  warn: (...args: unknown[]) => void;
};

export async function handleApi401Response(
  path: string,
  response: Response,
  deps: Api401HandlerDeps,
): Promise<never> {
  if (isCredentialExchangePath(path)) {
    let message = "Incorrect email or password";
    try {
      const data = (await response.json()) as unknown;
      message = deps.parseStructuredApiError(data) ?? message;
    } catch {
      // Ignore invalid error payloads.
    }
    throw new ApiError(message, 401);
  }

  if (isSessionLogout401Path(path)) {
    deps.clearStoredToken();
    deps.redirectToLogin();
    throw new ApiError("Authentication required", 401);
  }

  deps.warn("[AUTH] Non-session endpoint returned 401", path);
  throw new ApiError("Authentication required", 401);
}
