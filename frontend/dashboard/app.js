/* ═══════════════════════════════════════════════════════════════════
   FortiGate Backup Manager – Frontend Logic v1.3.0
   ═══════════════════════════════════════════════════════════════════ */

const API = window.API_BASE || `http://localhost:${location.port || 8000}`;
const AUTH_KEY = "fgbm_auth";
let currentUser = null;
let centersCache = [];

// ── Helpers ─────────────────────────────────────────────────────────

function authHeader() {
  const t = localStorage.getItem(AUTH_KEY);
  return t ? { Authorization: `Basic ${t}` } : {};
}

async function api(path, opts = {}) {
  const headers = { ...opts.headers, ...authHeader() };
  const r = await fetch(`${API}${path}`, { ...opts, headers });
  if (!r.ok) {
    if (r.status === 401) { showAuth(true); throw new Error("Unauthorized"); }
    const msg = await r.text();
    throw new Error(msg);
  }
  return r.json();
}

function fmtDate(v) {
  if (!v) return "--";
  const d = new Date(v);
  return d.toLocaleDateString("en-US", { month:"short", day:"numeric", year:"numeric" })
    + " " + d.toLocaleTimeString("en-US", { hour:"2-digit", minute:"2-digit" });
}

function fmtSize(bytes) {
  if (!bytes) return "--";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

const TAG_COLORS = {
  minerd: "#f59e0b",
  transi: "#10b981",
  unphu: "#6366f1",
  lanco: "#ec4899",
};

function tagBadge(tag) {
  if (!tag) return '<span class="tag-badge none">—</span>';
  const color = TAG_COLORS[tag] || "#64748b";
  return `<span class="tag-badge" style="--tag-color:${color}">${tag.toUpperCase()}</span>`;
}

// ── Toast notifications ─────────────────────────────────────────────

function toast(message, type = "info") {
  const c = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icons = {
    success: "✓", error: "✗", info: "ℹ"
  };
  el.innerHTML = `<span>${icons[type] || "ℹ"}</span> ${message}`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Auth ────────────────────────────────────────────────────────────

function showAuth(show) {
  document.getElementById("authOverlay").classList.toggle("hidden", !show);
}

document.getElementById("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const user = document.getElementById("authUser").value.trim();
  const pass = document.getElementById("authPass").value;
  const errEl = document.getElementById("authError");
  if (!user || !pass) { errEl.textContent = "Username and password required."; return; }

  const btn = document.getElementById("authSubmit");
  btn.disabled = true;
  btn.querySelector(".btn-text").textContent = "Signing in…";
  btn.querySelector(".btn-loader").classList.remove("hidden");

  try {
    localStorage.setItem(AUTH_KEY, btoa(`${user}:${pass}`));
    errEl.textContent = "";
    currentUser = await api("/me");
    showAuth(false);
    initApp();
    toast(`Welcome back, ${currentUser.username}`, "success");
  } catch {
    errEl.textContent = "Invalid credentials. Please try again.";
    localStorage.removeItem(AUTH_KEY);
  } finally {
    btn.disabled = false;
    btn.querySelector(".btn-text").textContent = "Sign In";
    btn.querySelector(".btn-loader").classList.add("hidden");
  }
});

// ── App init ────────────────────────────────────────────────────────

function initApp() {
  document.getElementById("mainApp").classList.remove("hidden");
  document.getElementById("currentUserName").textContent = currentUser.username;
  document.getElementById("currentUserRole").textContent = currentUser.role;
  document.querySelector(".avatar").textContent = currentUser.username[0].toUpperCase();

  if (currentUser.role === "admin") {
    document.getElementById("navUsers").style.display = "";
  }

  loadDashboard();
}

// ── Tab switching ───────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  document.querySelector(`[data-tab="${name}"]`).classList.add("active");

  if (name === "centers") loadCenters();
  if (name === "backups") updateBackupSelect();
  if (name === "events") loadEvents();
  if (name === "users") loadUsers();
}

// ── Auth mode toggle ────────────────────────────────────────────────

function toggleAuthFields() {
  const mode = document.getElementById("centerAuthMode").value;
  document.querySelectorAll(".auth-cred-field").forEach(el => el.style.display = mode === "credentials" ? "" : "none");
  document.querySelectorAll(".auth-token-field").forEach(el => el.style.display = mode === "token" ? "" : "none");
}

// ── Dashboard ───────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const tagFilter = document.getElementById("tagFilterDash")?.value || "";
    const centersUrl = tagFilter ? `/centers?tag=${tagFilter}` : "/centers";
    const [centers, events, tags] = await Promise.all([api(centersUrl), api("/events"), api("/tags")]);
    centersCache = centers;

    animateCounter("totalCenters", centers.length);
    animateCounter("okCenters", centers.filter(c => c.status === "OK").length);
    animateCounter("failedCenters", centers.filter(c => c.status === "FAILED").length);

    const dates = centers.map(c => c.last_backup).filter(Boolean).sort();
    document.getElementById("lastBackup").textContent = dates.length ? fmtDate(dates[dates.length - 1]) : "--";

    // Tag summary cards
    const tagEl = document.getElementById("tagSummary");
    if (tags.length > 0) {
      tagEl.innerHTML = tags.map(t => {
        const color = TAG_COLORS[t.tag] || "#64748b";
        return `<div class="tag-summary-card" style="--tag-color:${color}">
          <div class="tag-summary-name">${t.tag.toUpperCase()}</div>
          <div class="tag-summary-count">${t.count}</div>
          <div class="tag-summary-label">centers</div>
        </div>`;
      }).join("");
    } else {
      tagEl.innerHTML = "";
    }

    // Recent events
    const evtEl = document.getElementById("recentEvents");
    if (events.length === 0) {
      evtEl.innerHTML = '<p class="empty-state">No events yet</p>';
    } else {
      evtEl.innerHTML = events.slice(0, 8).map((e, i) => {
        const dotClass = e.event_type.includes("FAIL") ? "fail"
          : e.event_type.includes("OK") || e.event_type.includes("SUCCESS") ? "ok" : "info";
        return `<div class="event-item" style="animation-delay:${i * 0.05}s">
          <div class="event-dot ${dotClass}"></div>
          <div class="event-content">
            <div class="event-msg">${esc(e.message)}</div>
            <div class="event-time">${fmtDate(e.timestamp)}</div>
          </div>
        </div>`;
      }).join("");
    }

    // Fleet status
    const fleetEl = document.getElementById("fleetStatus");
    if (centers.length === 0) {
      fleetEl.innerHTML = '<p class="empty-state">No centers registered</p>';
    } else {
      fleetEl.innerHTML = centers.map((c, i) => {
        const cls = c.status === "OK" ? "ok" : c.status === "FAILED" ? "failed" : "unknown";
        return `<div class="fleet-item" style="animation-delay:${i * 0.04}s">
          <div><div class="fleet-name">${esc(c.name)}</div><div class="fleet-ip">${esc(c.fortigate_ip)} ${tagBadge(c.tag)}</div></div>
          <span class="status-badge ${cls}">${c.status}</span>
        </div>`;
      }).join("");
    }
  } catch (err) {
    if (err.message !== "Unauthorized") toast("Failed to load dashboard", "error");
  }
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  const start = parseInt(el.textContent) || 0;
  const diff = target - start;
  if (diff === 0) { el.textContent = target; return; }
  const duration = 600;
  const startTime = performance.now();
  function step(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(start + diff * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Centers ─────────────────────────────────────────────────────────

async function loadCenters() {
  try {
    const tagFilter = document.getElementById("tagFilterCenters")?.value || "";
    const url = tagFilter ? `/centers?tag=${tagFilter}` : "/centers";
    const centers = await api(url);
    centersCache = centers;
    const tbody = document.getElementById("centersBody");
    const empty = document.getElementById("centersEmpty");

    if (centers.length === 0) {
      tbody.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    tbody.innerHTML = centers.map((c, i) => {
      const cls = c.status === "OK" ? "ok" : c.status === "FAILED" ? "failed" : "unknown";
      const authIcon = c.auth_mode === "credentials" ? "🔑" : "🔐";
      return `<tr style="animation: eventIn 0.3s ease ${i * 0.04}s backwards">
        <td><strong>${esc(c.name)}</strong></td>
        <td>${tagBadge(c.tag)}</td>
        <td>${esc(c.location || "--")}</td>
        <td><code style="color:var(--accent)">${esc(c.fortigate_ip)}</code></td>
        <td><span title="${c.auth_mode === 'credentials' ? 'Username/Password' : 'API Token'}">${authIcon}</span></td>
        <td>${esc(c.model || "--")}</td>
        <td><span class="status-badge ${cls}">${c.status}</span></td>
        <td>${fmtDate(c.last_backup)}</td>
        <td><div class="actions">
          <button class="btn-sm action" onclick="runBackup(${c.id})">▶ Backup</button>
          <button class="btn-sm danger" onclick="deleteCenter(${c.id},'${esc(c.name)}')">✗ Delete</button>
        </div></td>
      </tr>`;
    }).join("");
  } catch (err) {
    if (err.message !== "Unauthorized") toast("Failed to load centers", "error");
  }
}

function toggleAddForm() {
  document.getElementById("addCenterForm").classList.toggle("collapsed");
}

function toggleBulkForm() {
  document.getElementById("bulkImportForm").classList.toggle("collapsed");
}

async function addCenter() {
  const authMode = document.getElementById("centerAuthMode").value;
  const payload = {
    name: document.getElementById("centerName").value.trim(),
    location: document.getElementById("centerLocation").value.trim() || null,
    fortigate_ip: document.getElementById("centerIp").value.trim(),
    model: document.getElementById("centerModel").value.trim() || null,
    tag: document.getElementById("centerTag").value || null,
    auth_mode: authMode,
  };

  if (authMode === "credentials") {
    payload.fortigate_username = document.getElementById("centerFgUser").value.trim();
    payload.fortigate_password = document.getElementById("centerFgPass").value;
  } else {
    payload.api_token = document.getElementById("centerToken").value.trim();
  }

  const msgEl = document.getElementById("centerMessage");
  if (!payload.name || !payload.fortigate_ip) {
    msgEl.textContent = "Name and IP are required.";
    msgEl.className = "form-message error";
    return;
  }
  if (authMode === "credentials" && (!payload.fortigate_username || !payload.fortigate_password)) {
    msgEl.textContent = "FortiGate username and password are required.";
    msgEl.className = "form-message error";
    return;
  }
  if (authMode === "token" && !payload.api_token) {
    msgEl.textContent = "API Token is required.";
    msgEl.className = "form-message error";
    return;
  }

  try {
    await api("/centers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    msgEl.textContent = "";
    ["centerName","centerLocation","centerIp","centerModel","centerToken","centerFgUser","centerFgPass"].forEach(
      id => { const el = document.getElementById(id); if (el) el.value = ""; });
    document.getElementById("centerTag").value = "";
    toggleAddForm();
    toast(`Center "${payload.name}" added successfully`, "success");
    loadCenters();
    loadDashboard();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "form-message error";
  }
}

async function bulkImport() {
  const msgEl = document.getElementById("bulkMessage");
  const raw = document.getElementById("bulkJson").value.trim();
  if (!raw) {
    msgEl.textContent = "Paste a JSON array of centers.";
    msgEl.className = "form-message error";
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error("Must be an array");
  } catch (e) {
    msgEl.textContent = "Invalid JSON: " + e.message;
    msgEl.className = "form-message error";
    return;
  }
  try {
    const result = await api("/centers/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ centers: parsed }),
    });
    msgEl.textContent = `Created: ${result.created}, Skipped: ${result.skipped}, Errors: ${result.errors.length}`;
    msgEl.className = "form-message success";
    toast(`Bulk import: ${result.created} created, ${result.skipped} skipped`, "success");
    loadCenters();
    loadDashboard();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "form-message error";
  }
}

async function deleteCenter(id, name) {
  if (!confirm(`Delete "${name}" and all its backups?\nThis cannot be undone.`)) return;
  try {
    await api(`/centers/${id}`, { method: "DELETE" });
    toast(`"${name}" deleted`, "info");
    loadCenters();
    loadDashboard();
  } catch (err) { toast(err.message, "error"); }
}

async function runBackup(centerId) {
  toast("Starting backup…", "info");
  try {
    await api(`/backups/run/${centerId}`, { method: "POST" });
    toast("Backup completed!", "success");
    loadCenters();
    loadDashboard();
  } catch (err) { toast(`Backup failed: ${err.message}`, "error"); }
}

async function runAllBackups() {
  const btn = document.getElementById("runAll");
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-loader"></span> Running…';
  toast("Running backups for all centers…", "info");
  try {
    await api("/backups/run", { method: "POST" });
    toast("All backups completed!", "success");
    loadCenters();
    loadDashboard();
  } catch (err) { toast(`Backup run failed: ${err.message}`, "error"); }
  finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run All Backups`;
  }
}

async function runTagBackup() {
  const tag = document.getElementById("backupTagSelect").value;
  if (!tag) {
    toast("Select a tag first to run backups by tag", "error");
    return;
  }
  const btn = document.getElementById("runTagBackup");
  btn.disabled = true;
  btn.innerHTML = '<span class="btn-loader"></span> Running…';
  toast(`Running backups for all ${tag.toUpperCase()} centers…`, "info");
  try {
    const result = await api(`/backups/run-by-tag/${tag}`, { method: "POST" });
    toast(`${tag.toUpperCase()}: ${result.ok} OK, ${result.failed} failed out of ${result.total}`, "success");
    loadDashboard();
  } catch (err) { toast(`Tag backup failed: ${err.message}`, "error"); }
  finally {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run by Tag`;
  }
}

// ── Backups ─────────────────────────────────────────────────────────

function filterBackupCenters() {
  const tag = document.getElementById("backupTagSelect").value;
  const filtered = tag ? centersCache.filter(c => c.tag === tag) : centersCache;
  const sel = document.getElementById("backupCenterSelect");
  sel.innerHTML = '<option value="">Select a center…</option>'
    + filtered.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
}

function updateBackupSelect() {
  const sel = document.getElementById("backupCenterSelect");
  const current = sel.value;
  sel.innerHTML = '<option value="">Select a center…</option>'
    + centersCache.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  sel.value = current;
}

async function loadBackups() {
  const centerId = document.getElementById("backupCenterSelect").value;
  const tbody = document.getElementById("backupsBody");
  const empty = document.getElementById("backupsEmpty");
  if (!centerId) { tbody.innerHTML = ""; empty.classList.remove("hidden"); return; }

  try {
    const backups = await api(`/backups?center_id=${centerId}`);
    if (backups.length === 0) {
      tbody.innerHTML = "";
      empty.textContent = "No backups found for this center";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    tbody.innerHTML = backups.map((b, i) => {
      const hash = b.checksum ? b.checksum.substring(0, 16) + "…" : "--";
      const cls = b.status === "OK" ? "ok" : "failed";
      return `<tr style="animation: eventIn 0.3s ease ${i * 0.04}s backwards">
        <td>${fmtDate(b.backup_date)}</td>
        <td style="font-size:0.8rem; color:var(--text-muted)">${esc(b.file_path || "--")}</td>
        <td><code style="font-size:0.8rem">${hash}</code></td>
        <td>${fmtSize(b.size)}</td>
        <td><span class="status-badge ${cls}">${b.status}</span></td>
        <td><button class="btn-sm action" onclick="restoreBackup(${b.id})">⏪ Restore</button></td>
      </tr>`;
    }).join("");
  } catch (err) { toast("Failed to load backups", "error"); }
}

async function restoreBackup(id) {
  if (!confirm("Restore this configuration to the FortiGate?\nThis will overwrite the current config.")) return;
  toast("Restoring configuration…", "info");
  try {
    await api(`/restore/${id}`, { method: "POST" });
    toast("Restore completed!", "success");
  } catch (err) { toast(`Restore failed: ${err.message}`, "error"); }
}

// ── Events ──────────────────────────────────────────────────────────

async function loadEvents() {
  try {
    const events = await api("/events");
    const tbody = document.getElementById("eventsBody");
    const empty = document.getElementById("eventsEmpty");

    if (events.length === 0) {
      tbody.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    tbody.innerHTML = events.slice(0, 50).map((e, i) => {
      const typeClass = e.event_type.includes("FAIL") ? "failed"
        : e.event_type.includes("OK") || e.event_type.includes("SUCCESS") ? "ok" : "unknown";
      return `<tr style="animation: eventIn 0.3s ease ${i * 0.03}s backwards">
        <td style="white-space:nowrap">${fmtDate(e.timestamp)}</td>
        <td><strong>${esc(e.center_name || "--")}</strong></td>
        <td><span class="status-badge ${typeClass}">${esc(e.event_type)}</span></td>
        <td>${esc(e.message)}</td>
      </tr>`;
    }).join("");
  } catch (err) { toast("Failed to load events", "error"); }
}

// ── Users ───────────────────────────────────────────────────────────

function toggleUserForm() {
  document.getElementById("addUserForm").classList.toggle("collapsed");
}

async function loadUsers() {
  try {
    const users = await api("/users");
    const tbody = document.getElementById("usersBody");

    tbody.innerHTML = users.map((u, i) => {
      const cls = u.is_active ? "ok" : "failed";
      const statusText = u.is_active ? "Active" : "Disabled";
      const actions = u.username === currentUser.username ? '<span style="color:var(--text-muted)">You</span>'
        : `<div class="actions">
            ${u.is_active
              ? `<button class="btn-sm danger" onclick="toggleUser(${u.id}, false)">Disable</button>`
              : `<button class="btn-sm success" onclick="toggleUser(${u.id}, true)">Enable</button>`}
          </div>`;
      return `<tr style="animation: eventIn 0.3s ease ${i * 0.04}s backwards">
        <td><strong>${esc(u.username)}</strong></td>
        <td style="text-transform:capitalize">${esc(u.role)}</td>
        <td><span class="status-badge ${cls}">${statusText}</span></td>
        <td>${fmtDate(u.created_at)}</td>
        <td>${actions}</td>
      </tr>`;
    }).join("");
  } catch (err) { toast("Failed to load users", "error"); }
}

async function createUser() {
  const payload = {
    username: document.getElementById("userName").value.trim(),
    password: document.getElementById("userPassword").value,
    role: document.getElementById("userRole").value,
  };
  const msgEl = document.getElementById("userMessage");
  if (!payload.username || !payload.password) {
    msgEl.textContent = "Username and password required.";
    msgEl.className = "form-message error";
    return;
  }
  try {
    await api("/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    ["userName","userPassword"].forEach(id => document.getElementById(id).value = "");
    toggleUserForm();
    toast(`User "${payload.username}" created`, "success");
    loadUsers();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "form-message error";
  }
}

async function toggleUser(id, activate) {
  try {
    const endpoint = activate ? `/users/${id}/enable` : `/users/${id}/disable`;
    await api(endpoint, { method: "PUT" });
    toast(`User ${activate ? "enabled" : "disabled"}`, "info");
    loadUsers();
  } catch (err) { toast(err.message, "error"); }
}

// ── Utility ─────────────────────────────────────────────────────────

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ── Boot ────────────────────────────────────────────────────────────

(async function boot() {
  const existing = localStorage.getItem(AUTH_KEY);
  if (!existing) { showAuth(true); return; }
  try {
    currentUser = await api("/me");
    showAuth(false);
    initApp();
  } catch {
    showAuth(true);
  }
})();
