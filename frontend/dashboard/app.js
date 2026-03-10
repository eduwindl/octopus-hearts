const API_BASE = window.API_BASE || "http://localhost:8000";
const AUTH_KEY = "fgbm_auth";

function getAuthHeader() {
  const token = localStorage.getItem(AUTH_KEY);
  if (!token) return {};
  return { Authorization: `Basic ${token}` };
}

function showAuthOverlay(show) {
  const overlay = document.getElementById("authOverlay");
  overlay.classList.toggle("hidden", !show);
}

function setAuthError(message) {
  document.getElementById("authError").textContent = message || "";
}

async function fetchJson(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
    ...getAuthHeader(),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) {
      showAuthOverlay(true);
      throw new Error("Unauthorized");
    }
    throw new Error(await res.text());
  }
  return res.json();
}

function formatDate(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString();
}

async function loadDashboard() {
  const centers = await fetchJson("/centers");
  const events = await fetchJson("/events");

  document.getElementById("totalCenters").textContent = centers.length;
  const lastBackup = centers
    .map((c) => c.last_backup)
    .filter(Boolean)
    .sort()
    .pop();
  document.getElementById("lastBackup").textContent = formatDate(lastBackup);
  const failed = centers.filter((c) => c.status === "FAILED").length;
  document.getElementById("failedCenters").textContent = failed;

  const tbody = document.getElementById("centersBody");
  tbody.innerHTML = "";
  centers.forEach((c) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${c.name}</td>
      <td>${c.fortigate_ip}</td>
      <td>${c.model || "--"}</td>
      <td class="${c.status === "OK" ? "status-ok" : "status-failed"}">${c.status}</td>
      <td>${formatDate(c.last_backup)}</td>
      <td><button data-id="${c.id}" class="primary">Run</button></td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetchJson(`/backups/run/${btn.dataset.id}`, { method: "POST" });
      await loadDashboard();
    });
  });

  const eventsContainer = document.getElementById("events");
  eventsContainer.innerHTML = "";
  events.slice(0, 6).forEach((e) => {
    const div = document.createElement("div");
    div.className = "event";
    div.textContent = `${formatDate(e.timestamp)} | ${e.event_type} | ${e.message}`;
    eventsContainer.appendChild(div);
  });
}

async function runAll() {
  await fetchJson("/backups/run", { method: "POST" });
  await loadDashboard();
}

document.getElementById("runAll").addEventListener("click", runAll);

document.getElementById("authSubmit").addEventListener("click", async () => {
  const user = document.getElementById("authUser").value.trim();
  const pass = document.getElementById("authPass").value;
  if (!user || !pass) {
    setAuthError("Username and password required.");
    return;
  }
  const token = btoa(`${user}:${pass}`);
  localStorage.setItem(AUTH_KEY, token);
  setAuthError("");
  try {
    await loadDashboard();
    showAuthOverlay(false);
  } catch (err) {
    setAuthError("Invalid credentials.");
  }
});

const existingAuth = localStorage.getItem(AUTH_KEY);
showAuthOverlay(!existingAuth);
if (existingAuth) {
  loadDashboard().catch(() => showAuthOverlay(true));
}
