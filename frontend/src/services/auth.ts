import axios from "axios";

const API_BASE = "http://127.0.0.1:8001/api";

export async function login(username: string, password: string): Promise<string> {
  const { data } = await axios.post(`${API_BASE}/auth/login`, { username, password });
  const token = data.token;
  localStorage.setItem("auth_token", token);
  return token;
}

export function logout() {
  localStorage.removeItem("auth_token");
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}
