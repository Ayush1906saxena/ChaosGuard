const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const TOKEN_KEY = 'chaosguard_token';
const USER_KEY = 'chaosguard_user';

export interface AuthUser {
  username: string;
  roles: string[];
  token: string;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setAuth(token: string, username: string, roles: string[]): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify({ username, roles, token }));
  // Set cookie for middleware (server-side route protection)
  // Use SameSite=Lax and ensure path=/ for all routes
  const isSecure = window.location.protocol === 'https:';
  document.cookie = `chaosguard_token=${token}; path=/; max-age=86400; SameSite=Lax${isSecure ? '; Secure' : ''}`;
  // Also set a simple auth flag cookie as fallback
  document.cookie = `chaosguard_authed=1; path=/; max-age=86400; SameSite=Lax${isSecure ? '; Secure' : ''}`;
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = 'chaosguard_token=; path=/; max-age=0';
  document.cookie = 'chaosguard_authed=; path=/; max-age=0';
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: 'Login failed' }));
    throw new Error(body.error || 'Invalid credentials');
  }

  const data = await res.json();
  setAuth(data.token, data.username, data.roles);
  return { username: data.username, roles: data.roles, token: data.token };
}

export async function register(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: 'Registration failed' }));
    throw new Error(body.error || 'Registration failed');
  }

  const data = await res.json();
  setAuth(data.token, data.username, data.roles);
  return { username: data.username, roles: data.roles, token: data.token };
}

export function logout(): void {
  clearAuth();
  window.location.href = '/login';
}
