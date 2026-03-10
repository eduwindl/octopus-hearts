const API_BASE = window.API_BASE || "http://localhost:8000";
const AUTH_KEY = "fgbm_auth";
let currentUser = null;

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
  currentUser = await fetchJson("/me");
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

  const adminPanel = document.getElementById("adminPanel");
  if (currentUser && currentUser.role === "admin") {
    adminPanel.classList.remove("hidden");
    await loadUsers();
  } else {
    adminPanel.classList.add("hidden");
  }
}

async function runAll() {
  await fetchJson("/backups/run", { method: "POST" });
  await loadDashboard();
}

document.getElementById("runAll").addEventListener("click", runAll);

document.getElementById("addCenter").addEventListener("click", async () => {
  const payload = {
    name: document.getElementById("centerName").value.trim(),
    location: document.getElementById("centerLocation").value.trim() || null,
    fortigate_ip: document.getElementById("centerIp").value.trim(),
    model: document.getElementById("centerModel").value.trim() || null,
    api_token: document.getElementById("centerToken").value.trim(),
  };
  if (!payload.name || !payload.fortigate_ip || !payload.api_token) {
    document.getElementById("centerMessage").textContent = "Name, IP and token are required.";
    return;
  }
  try {
    await fetchJson("/centers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    document.getElementById("centerMessage").textContent = "Center created.";
    await loadDashboard();
  } catch (err) {
    document.getElementById("centerMessage").textContent = `Error: ${err.message}`;
  }
});

document.getElementById("createUser").addEventListener("click", async () => {
  const payload = {
    username: document.getElementById("userName").value.trim(),
    password: document.getElementById("userPassword").value,
    role: document.getElementById("userRole").value,
  };
  if (!payload.username || !payload.password) {
    document.getElementById("userMessage").textContent = "Username and password are required.";
    return;
  }
  try {
    await fetchJson("/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    document.getElementById("userMessage").textContent = "User created.";
    await loadUsers();
  } catch (err) {
    document.getElementById("userMessage").textContent = `Error: ${err.message}`;
  }
});

document.getElementById("updateMyPassword").addEventListener("click", async () => {
  const newPassword = document.getElementById("myNewPassword").value;
  if (!newPassword) {
    document.getElementById("myPasswordMessage").textContent = "Password required.";
    return;
  }
  try {
    await fetchJson(`/users/${currentUser.id}/password`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: newPassword }),
    });
    document.getElementById("myPasswordMessage").textContent = "Password updated.";
  } catch (err) {
    document.getElementById("myPasswordMessage").textContent = `Error: ${err.message}`;
  }
});

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

async function loadUsers() {
  const users = await fetchJson("/users");
  const tbody = document.getElementById("usersBody");
  tbody.innerHTML = "";
  users.forEach((u) => {
    const tr = document.createElement("tr");
    const status = u.is_active ? "Active" : "Disabled";
    const action = u.is_active ? `<button data-id="${u.id}" class="primary">Disable</button>` : "--";
    tr.innerHTML = `
      <td>${u.username}</td>
      <td>${u.role}</td>
      <td>${status}</td>
      <td>${action}</td>
    `;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetchJson(`/users/${btn.dataset.id}/disable`, { method: "PUT" });
      await loadUsers();
    });
  });
}
