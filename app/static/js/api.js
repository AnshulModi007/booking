const TOKEN_KEY = "booking_token";

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(token) { localStorage.setItem(TOKEN_KEY, token); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

function requireAuth() {
  if (!getToken()) location.href = "login.html";
}

async function api(path, { method = "GET", body, params } = {}) {
  let url = path;
  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, v);
    }
    url += `?${qs.toString()}`;
  }

  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    if (!location.pathname.endsWith("login.html")) location.href = "login.html";
    throw new Error("Not authenticated");
  }

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && data.detail;
    const err = new Error(typeof detail === "string" ? detail : (detail ? JSON.stringify(detail) : res.statusText));
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const res = await fetch("/login", { method: "POST", body });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && data.detail) || "Login failed");

  setToken(data.access_token);
  return data;
}

function logout() {
  clearToken();
  try { sessionStorage.removeItem("booking_chat_messages"); } catch (e) { /* ignore */ }
  location.href = "login.html";
}

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDateTime(iso) {
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function renderBottomNav(active) {
  return `
    <nav class="bottom-nav">
      <a href="facilities.html" class="${active === "facilities" ? "active" : ""}">Facilities</a>
      <a href="bookings.html" class="${active === "bookings" ? "active" : ""}">My Bookings</a>
      <a href="chat.html" class="${active === "chat" ? "active" : ""}">Chat</a>
      <a href="admin.html" class="${active === "admin" ? "active" : ""}">Admin</a>
      <button onclick="logout()">Logout</button>
    </nav>`;
}