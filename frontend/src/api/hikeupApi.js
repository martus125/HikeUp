import { API_URL } from "../constants/api";
import { normalizePointList } from "../utils/points";

let csrfToken = null;

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...options.headers,
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    },
  });

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Backend zwrócił nieprawidłową odpowiedź.");
  }

  if (response.status === 401) {
    csrfToken = null;
    if (path !== "/api/login") window.dispatchEvent(new Event("hikeup:session-expired"));
  }
  if (!response.ok || data.success === false) {
    throw new Error(
      data.message || "Wystąpił błąd połączenia z backendem."
    );
  }

  if (data.csrf_token) csrfToken = data.csrf_token;
  return data;
}

export async function fetchGraph() {
  const data = await request("/api/graph");

  return {
    nodes: normalizePointList(data.nodes || data),
    edges: Array.isArray(data.edges) ? data.edges : [],
  };
}

export async function fetchPoints() {
  const data = await request("/api/points");
  return normalizePointList(data.points || data);
}

export async function fetchRoute({
  start,
  end,
  criterion,
  exampleId,
}) {
  return request("/api/route", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      start,
      end,
      criterion,
      ...(exampleId ? { example_id: exampleId } : {}),
    }),
  });
}

export async function fetchRouteExamples() {
  return request("/api/route-examples");
}

export async function registerUser({ name, email, password }) {
  return request("/api/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      email,
      password,
    }),
  });
}

export async function loginUser({ email, password }) {
  return request("/api/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function saveFavoriteRoute(favoriteData) {
  return request("/api/favorites", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(favoriteData),
  });
}

export async function getUserProfile() {
  return request("/api/profile");
}

export async function updateUserProfile(profileData) {
  return request("/api/profile", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profileData),
  });
}


export function getCurrentUser() {
  return request("/api/auth/me");
}

export async function logoutUser() {
  const result = await request("/api/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  csrfToken = null;
  return result;
}

export function fetchFavorites() {
  return request("/api/favorites");
}
