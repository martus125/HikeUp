import { API_URL } from "../constants/api";
import { normalizePointList } from "../utils/points";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const data = await response.json();

  if (!response.ok || data.success === false) {
    throw new Error(data.message || "Wystąpił błąd połączenia z backendem.");
  }

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

export async function fetchRoute({ start, end, criterion }) {
  return request("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start, end, criterion }),
  });
}

export async function registerUser({ name, email, password }) {
  return request("/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
}

export async function loginUser({ email, password }) {
  return request("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function saveFavoriteRoute(favoriteData) {
  return request("/api/favorites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(favoriteData),
  });
}
