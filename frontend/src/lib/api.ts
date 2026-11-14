import type {
  ApiError,
  FollowCounts,
  FollowRelationship,
  FollowStatus,
  Page,
  Post,
  PublicProfile,
  TokenResponse,
  User,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const ACCESS_KEY = "frame.access";
const REFRESH_KEY = "frame.refresh";

let accessToken: string | null = localStorage.getItem(ACCESS_KEY);
let refreshToken: string | null = localStorage.getItem(REFRESH_KEY);
let refreshInFlight: Promise<boolean> | null = null;

export function getAccessToken() {
  return accessToken;
}

export function saveTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function rotateTokens(): Promise<boolean> {
  if (!refreshToken) return false;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clearTokens();
        return false;
      }
      const tokens = (await response.json()) as TokenResponse;
      saveTokens(tokens.access_token, tokens.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

function errorMessage(payload: ApiError, fallback: string): string {
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg ?? "Invalid input").join(", ");
  }
  return fallback;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  const isAuthEntryPoint = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"].includes(path);\n  if (response.status === 401 && retry && refreshToken && !isAuthEntryPoint) {
    if (await rotateTokens()) {
      return request<T>(path, init, false);
    }
  }

  if (!response.ok) {
    if (response.status === 204) return undefined as T;
    let payload: ApiError = {};
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      // Keep the HTTP status as the fallback when the body is not JSON.
    }
    throw new Error(errorMessage(payload, `Request failed (${response.status})`));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  register: (input: {
    username: string;
    email: string;
    password: string;
    bio?: string;
    is_private: boolean;
  }) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  refresh: () => rotateTokens(),
  logout: async () => {
    const token = refreshToken;
    try {
      if (token) {
        await request("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: token }),
        }, false);
      }
    } finally {
      clearTokens();
    }
  },
  me: () => request<User>("/auth/me"),
  feed: (limit = 20, cursor?: string) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return request<Page<Post>>(`/feed?${query.toString()}`);
  },
  createPost: (caption: string, imageUrls: string[]) =>
    request<Post>("/posts", {
      method: "POST",
      body: JSON.stringify({
        caption: caption || null,
        post_img_url: imageUrls.map((url) => ({ url })),
        is_private: false,
      }),
    }),
  deletePost: (postId: string) =>
    request<void>(`/posts/${postId}`, { method: "DELETE" }),
  profile: (username: string) =>
    request<PublicProfile>(`/users/${encodeURIComponent(username)}`),
  profilePosts: (username: string, limit = 20, cursor?: string) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return request<Page<Post>>(
      `/posts/users/${encodeURIComponent(username)}?${query.toString()}`,
    );
  },
  relationship: (username: string) =>
    request<FollowStatus>(`/follows/${encodeURIComponent(username)}/relationship`),
  follow: (username: string) =>
    request<FollowRelationship>(`/follows/${encodeURIComponent(username)}`, {
      method: "POST",
    }),
  unfollow: (username: string) =>
    request<void>(`/follows/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }),
  counts: (username: string) =>
    request<FollowCounts>(`/follows/${encodeURIComponent(username)}/counts`),
};
