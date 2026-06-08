import { useState, useEffect, useCallback } from "react";

const TOKEN_KEY = "auth_token";
const USERNAME_KEY = "auth_username";
const ROLE_KEY = "auth_role";
const AUTH_CHANGE_EVENT = "auth-change";

function emitAuthChange() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string, username: string, role: number = 1): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USERNAME_KEY, username);
  localStorage.setItem(ROLE_KEY, String(role));
  emitAuthChange();
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(ROLE_KEY);
  emitAuthChange();
}

export function getUsername(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USERNAME_KEY);
}

export function getRole(): number {
  if (typeof window === "undefined") return 1;
  return parseInt(localStorage.getItem(ROLE_KEY) || "1", 10);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Reactive hook — re-renders component when auth state changes */
export function useAuth() {
  const read = useCallback(() => ({
    token: getToken(),
    username: getUsername(),
    role: getRole(),
    authenticated: isAuthenticated(),
  }), []);

  const [auth, setAuth] = useState(read);

  useEffect(() => {
    const sync = () => setAuth(read);
    window.addEventListener(AUTH_CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [read]);

  return auth;
}
