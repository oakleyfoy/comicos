import { ApiError, apiClient } from "../api/client";

export const GMAIL_IMPORTS_PATH = "/imports/email";

export async function startGmailOAuth(redirectPath: string = GMAIL_IMPORTS_PATH): Promise<void> {
  try {
    const response = await apiClient.getGmailConnectStart(redirectPath);
    window.location.href = response.authorization_url;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("Unable to start Gmail connection.", 0);
  }
}

export function consumeGmailConnectedSearchParam(): boolean {
  const searchParams = new URLSearchParams(window.location.search);
  if (searchParams.get("gmail") !== "connected") {
    return false;
  }
  searchParams.delete("gmail");
  const nextQuery = searchParams.toString();
  const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
  return true;
}
