export const ACCESS_TOKEN_KEY = "access_token";
export const REFRESH_TOKEN_KEY = "refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
      // also sync as a cookie for middleware/server checks (non-HttpOnly)
      document.cookie = `${ACCESS_TOKEN_KEY}=${encodeURIComponent(token)}; path=/; samesite=lax`;
    } else {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY);
      // clear cookie
      document.cookie = `${ACCESS_TOKEN_KEY}=; path=/; max-age=0; samesite=lax`;
    }
  } catch {
    // ignore storage errors
  }
}

export function setRefreshToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  } catch {
    // ignore storage errors
  }
}

export function clearTokens(): void {
  setAccessToken(null);
  setRefreshToken(null);
}


