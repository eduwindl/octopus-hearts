/* ═══════════════════════════════════════════════════════════════════
   FortiGate Backup Manager – Frontend Logic v1.5.0
   Terminal Theme + Edit Modal + Context Menu
   ═══════════════════════════════════════════════════════════════════ */

const API = window.API_BASE || `http://localhost:${location.port || 8000}`;
const AUTH_KEY = "fgbm_auth";
let currentUser = null;
let centersCache = [];
let contextCenterData = null; // for right-click context menu

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
  const icons = { success: "✓", error: "✗", info: "ℹ" };
  el.innerHTML = `<span>${icons[type] || "ℹ"}</span> ${message}`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Terminal Boot Sequence ──────────────────────────────────────────

const ASCII_LOGO = `
  ███████╗ ██████╗ ██████╗ ███╗   ███╗
  ██╔════╝██╔════╝ ██╔══██╗████╗ ████║
  █████╗  ██║  ███╗██████╔╝██╔████╔██║
  ██╔══╝  ██║   ██║██╔══██╗██║╚██╔╝██║
  ██║     ╚██████╔╝██████╔╝██║ ╚═╝ ██║
  ╚═╝      ╚═════╝ ╚═════╝ ╚═╝     ╚═╝
  ┌─────────────────────────────────────┐
  │  FortiGate Backup Manager v1.5.0   │
  │  Secure Configuration Terminal     │
  └─────────────────────────────────────┘`;

const BOOT_MESSAGES = [
  { text: "[<span class='ok'>OK</span>] Initializing kernel modules...", delay: 200 },
  { text: "[<span class='ok'>OK</span>] Loading cryptographic subsystem...", delay: 350 },
  { text: "[<span class='info'>INFO</span>] Detected FortiGate API engine v3.2.1", delay: 500 },
  { text: "[<span class='ok'>OK</span>] SQLite database engine ready", delay: 650 },
  { text: "[<span class='ok'>OK</span>] Initializing backup scheduler...", delay: 800 },
  { text: "[<span class='warn'>WARN</span>] Firewall rules loaded: 317 endpoints", delay: 950 },
  { text: "[<span class='ok'>OK</span>] Network interfaces configured", delay: 1100 },
  { text: "[<span class='info'>INFO</span>] TLS 1.3 handshake protocol active", delay: 1250 },
  { text: "[<span class='ok'>OK</span>] Secure terminal ready", delay: 1400 },
  { text: "<span class='dim'>─────────────────────────────────────</span>", delay: 1550 },
  { text: "<span class='info'>Authentication required. Enter credentials below.</span>", delay: 1700 },
];

const MANATEE_FRAMES = [
`
             .oO00000000000000Oo.
          .d0000000000000000000000d.
        .k00000000000000000000000000k.
       c0000000      0000      0000000c
      l00000000      0000      00000000l
     l000000000  ██  0000  ██  000000000l
    .0000000000      0000      0000000000.
    l000000000000000O:___:O00000000000000l
    O0000000000000000\\___/000000000000000O
    O000000000000000000000000000000000000O
    o000000000000000000000000000000000000o
    .000000000000000000000000000000000000.
  _ .O0000000000000000000000000000000000O.
 / \\|00000000000000000000000000000000000|
|   |000000000000000000000000000000000000|
 \\ / 000000000000000000000000000000000000
  ~  .0000000000000000000000000000000000.
      k00000000000000000000000000000000k
       d0000000000000000000000000000000d
        :O000000000000000000000000000O:
          cO000000000000000000000000Oc
             'loxO0000000000000Oxdl'
`,
`
             .oO00000000000000Oo.
          .d0000000000000000000000d.
        .k00000000000000000000000000k.
       c0000000      0000      0000000c
      l00000000      0000      00000000l
     l000000000  ██  0000  --  000000000l
    .0000000000      0000      0000000000.
    l000000000000000O:___:O00000000000000l
    O0000000000000000\\___/000000000000000O
    O000000000000000000000000000000000000O
    o000000000000000000000000000000000000o
    .000000000000000000000000000000000000.  _
  _ .O0000000000000000000000000000000000O. //
 / \\|00000000000000000000000000000000000| //
|   |000000000000000000000000000000000000|//
 \\ / 000000000000000000000000000000000000
  ~  .0000000000000000000000000000000000.
      k00000000000000000000000000000000k
       d0000000000000000000000000000000d
        :O000000000000000000000000000O:
          cO000000000000000000000000Oc
             'loxO0000000000000Oxdl'
`
];

let manateeTimer = null;
let currentFrame = 0;
function startManateeAnimation() {
  const el = document.getElementById("manateeArt");
  if (!el) return;
  const loop = () => {
    el.textContent = MANATEE_FRAMES[currentFrame];
    if (currentFrame === 0) {
      if (Math.random() > 0.8) {
        currentFrame = 1;
        manateeTimer = setTimeout(loop, 400); // wink & wave duration
      } else {
        manateeTimer = setTimeout(loop, 1000 + Math.random() * 2000); // normal duration
      }
    } else {
      currentFrame = 0;
      manateeTimer = setTimeout(loop, 1000 + Math.random() * 1500); // back to normal
    }
  };
  loop();
}

function runBootSequence() {
  const artEl = document.getElementById("asciiArt");
  const bootEl = document.getElementById("bootLog");
  const loginEl = document.getElementById("loginPrompt");
  const manateeContainer = document.getElementById("manateeContainer");

  // Reset animations and states
  bootEl.innerHTML = "";
  loginEl.classList.add("hidden");
  manateeContainer.classList.remove("show");
  manateeContainer.classList.add("hidden");
  clearTimeout(manateeTimer);

  // Type out ASCII art for LOGO
  artEl.textContent = ASCII_LOGO;

  // Boot messages with staggered delays
  BOOT_MESSAGES.forEach((msg, i) => {
    setTimeout(() => {
      const line = document.createElement("div");
      line.className = "boot-line";
      line.innerHTML = msg.text;
      bootEl.appendChild(line);

      // Auto scroll
      const body = document.getElementById("terminalBody");
      body.scrollTop = body.scrollHeight;

      // Reveal manatee half way through boot
      if (i === 4) {
        manateeContainer.classList.remove("hidden");
        // small delay before fade in
        setTimeout(() => {
          manateeContainer.classList.add("show");
          startManateeAnimation();
        }, 50);
      }

    }, msg.delay);
  });

  // Show login prompt after boot
  setTimeout(() => {
    loginEl.classList.remove("hidden");
    const body = document.getElementById("terminalBody");
    body.scrollTop = body.scrollHeight;
    document.getElementById("authUser").focus();
  }, BOOT_MESSAGES[BOOT_MESSAGES.length - 1].delay + 300);
}

// ── Auth ────────────────────────────────────────────────────────────

function showAuth(show) {
  const overlay = document.getElementById("authOverlay");
  if (show) {
    overlay.classList.remove("hidden");
    runBootSequence();
  } else {
    overlay.classList.add("hidden");
  }
}

document.getElementById("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const user = document.getElementById("authUser").value.trim();
  const pass = document.getElementById("authPass").value;
  const errEl = document.getElementById("authError");
  if (!user || !pass) { errEl.textContent = "ERROR: Username and password required."; return; }

  const btn = document.getElementById("authSubmit");
  btn.disabled = true;
  btn.textContent = "[ AUTHENTICATING... ]";

  try {
    localStorage.setItem(AUTH_KEY, btoa(`${user}:${pass}`));
    errEl.textContent = "";
    currentUser = await api("/me");
    showAuth(false);
    initApp();
    toast(`Welcome back, ${currentUser.username}`, "success");
  } catch {
    errEl.textContent = "ACCESS DENIED: Invalid credentials.";
    localStorage.removeItem(AUTH_KEY);
  } finally {
    btn.disabled = false;
    btn.textContent = "[ AUTHENTICATE ]";
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
  if (name === "credentials") loadCredentialStatus();
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

function toggleEditAuthFields() {
  const mode = document.getElementById("editAuthMode").value;
  document.querySelectorAll(".edit-cred-field").forEach(el => el.style.display = mode === "credentials" ? "" : "none");
  document.querySelectorAll(".edit-token-field").forEach(el => el.style.display = mode === "token" ? "" : "none");
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
      fleetEl.innerHTML = centers.slice(0, 20).map((c, i) => {
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

let searchTimer = null;
function debouncedSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadCenters(), 300);
}

async function loadCenters() {
  try {
    const tagFilter = document.getElementById("tagFilterCenters")?.value || "";
    const searchQuery = document.getElementById("centerSearch")?.value.trim() || "";
    let url = "/centers?";
    if (tagFilter) url += `tag=${encodeURIComponent(tagFilter)}&`;
    if (searchQuery) url += `q=${encodeURIComponent(searchQuery)}&`;
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
      return `<tr style="animation: eventIn 0.3s ease ${i * 0.04}s backwards" data-center-id="${c.id}" oncontextmenu="showContextMenu(event, ${c.id})">
        <td><strong>${esc(c.name)}</strong></td>
        <td>${tagBadge(c.tag)}</td>
        <td>${esc(c.location || "--")}</td>
        <td><span class="mono-ip">${esc(c.fortigate_ip)}</span></td>
        <td><span title="${c.auth_mode === 'credentials' ? 'Username/Password' : 'API Token'}">${authIcon}</span></td>
        <td>${esc(c.model || "--")}</td>
        <td><span class="status-badge ${cls}">${c.status}</span></td>
        <td>${fmtDate(c.last_backup)}</td>
        <td><div class="actions">
          <button class="btn-sm action" onclick="openEditModal(${c.id})">✏️ Edit</button>
          <button class="btn-sm action" onclick="runBackup(${c.id})">▶ Backup</button>
          <button class="btn-sm danger" onclick="deleteCenter(${c.id},'${esc(c.name)}')">✗</button>
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
    btn.innerHTML = '▶ RUN ALL BACKUPS';
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
    btn.innerHTML = '▶ RUN BY TAG';
  }
}

// ── Context Menu (Right-click) ──────────────────────────────────────

function showContextMenu(e, centerId) {
  e.preventDefault();
  contextCenterData = centersCache.find(c => c.id === centerId);
  if (!contextCenterData) return;

  const menu = document.getElementById("contextMenu");
  menu.classList.remove("hidden");
  menu.style.left = `${e.clientX}px`;
  menu.style.top = `${e.clientY}px`;

  // Ensure menu stays within viewport
  const rect = menu.getBoundingClientRect();
  if (rect.right > window.innerWidth) menu.style.left = `${e.clientX - rect.width}px`;
  if (rect.bottom > window.innerHeight) menu.style.top = `${e.clientY - rect.height}px`;
}

function hideContextMenu() {
  document.getElementById("contextMenu").classList.add("hidden");
  contextCenterData = null;
}

document.addEventListener("click", hideContextMenu);
document.addEventListener("scroll", hideContextMenu, true);

function contextEditCenter() {
  if (contextCenterData) openEditModal(contextCenterData.id);
  hideContextMenu();
}

function contextRunBackup() {
  if (contextCenterData) runBackup(contextCenterData.id);
  hideContextMenu();
}

function contextDeleteCenter() {
  if (contextCenterData) deleteCenter(contextCenterData.id, contextCenterData.name);
  hideContextMenu();
}

// ── Edit Center Modal ───────────────────────────────────────────────

function openEditModal(centerId) {
  const center = centersCache.find(c => c.id === centerId);
  if (!center) return;

  document.getElementById("editCenterId").value = center.id;
  document.getElementById("editName").value = center.name || "";
  document.getElementById("editIp").value = center.fortigate_ip || "";
  document.getElementById("editTag").value = center.tag || "";
  document.getElementById("editAuthMode").value = center.auth_mode || "credentials";
  document.getElementById("editFgUser").value = center.fortigate_username || "";
  document.getElementById("editFgPass").value = "";
  document.getElementById("editToken").value = "";
  document.getElementById("editLocation").value = center.location || "";
  document.getElementById("editModel").value = center.model || "";
  document.getElementById("editMessage").textContent = "";

  toggleEditAuthFields();
  document.getElementById("editModal").classList.remove("hidden");
}

function closeEditModal() {
  document.getElementById("editModal").classList.add("hidden");
}

// Close modal on Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeEditModal();
});

async function saveEditCenter() {
  const id = document.getElementById("editCenterId").value;
  const authMode = document.getElementById("editAuthMode").value;
  const payload = {
    name: document.getElementById("editName").value.trim(),
    fortigate_ip: document.getElementById("editIp").value.trim(),
    tag: document.getElementById("editTag").value || null,
    auth_mode: authMode,
    location: document.getElementById("editLocation").value.trim() || null,
    model: document.getElementById("editModel").value.trim() || null,
  };

  if (authMode === "credentials") {
    const user = document.getElementById("editFgUser").value.trim();
    const pass = document.getElementById("editFgPass").value;
    if (user) payload.fortigate_username = user;
    if (pass) payload.fortigate_password = pass;
  } else {
    const token = document.getElementById("editToken").value.trim();
    if (token) payload.api_token = token;
  }

  const msgEl = document.getElementById("editMessage");
  if (!payload.name || !payload.fortigate_ip) {
    msgEl.textContent = "Name and IP are required.";
    msgEl.className = "form-message error";
    return;
  }

  try {
    await api(`/centers/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    closeEditModal();
    toast(`Center "${payload.name}" updated successfully`, "success");
    loadCenters();
    loadDashboard();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "form-message error";
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

// ── Credentials Tab ─────────────────────────────────────────────────

function toggleCredAuthFields() {
  const mode = document.getElementById("credAuthMode").value;
  document.querySelectorAll(".cred-user-field").forEach(el => el.style.display = mode === "credentials" ? "" : "none");
  document.querySelectorAll(".cred-token-field").forEach(el => el.style.display = mode === "token" ? "" : "none");
}

// Update center count when tag changes
document.getElementById("credTag")?.addEventListener("change", async () => {
  const tag = document.getElementById("credTag").value;
  const display = document.getElementById("credCountDisplay");
  if (!tag) { display.textContent = "-- select a tag --"; return; }
  try {
    const centers = await api(`/centers?tag=${tag}`);
    display.textContent = `${centers.length} centers`;
    display.style.color = centers.length > 0 ? "#22c55e" : "#ef4444";
  } catch { display.textContent = "error"; }
});

async function applyCredentials() {
  const tag = document.getElementById("credTag").value;
  const authMode = document.getElementById("credAuthMode").value;
  const msgEl = document.getElementById("credMessage");

  if (!tag) { msgEl.textContent = "Select a tag first."; msgEl.className = "form-message error"; return; }

  const payload = { auth_mode: authMode, tag };
  if (authMode === "credentials") {
    payload.fortigate_username = document.getElementById("credUser").value.trim();
    payload.fortigate_password = document.getElementById("credPass").value;
    if (!payload.fortigate_username || !payload.fortigate_password) {
      msgEl.textContent = "Username and password are required."; msgEl.className = "form-message error"; return;
    }
  } else {
    payload.api_token = document.getElementById("credToken").value.trim();
    if (!payload.api_token) {
      msgEl.textContent = "API Token is required."; msgEl.className = "form-message error"; return;
    }
  }

  if (!confirm(`This will update credentials for ALL ${tag.toUpperCase()} centers.\nAre you sure?`)) return;

  try {
    const result = await api("/credentials/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    msgEl.textContent = `✓ Updated ${result.updated} centers with ${authMode} auth`;
    msgEl.className = "form-message success";
    toast(`Credentials applied to ${result.updated} ${tag.toUpperCase()} centers`, "success");
    // Clear password fields
    ["credPass", "credToken"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
    loadCredentialStatus();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "form-message error";
  }
}

async function loadCredentialStatus() {
  const grid = document.getElementById("credStatusGrid");
  try {
    const tags = await api("/tags");
    if (tags.length === 0) { grid.innerHTML = '<p class="empty-state">No tags found</p>'; return; }

    let html = '';
    for (const t of tags) {
      if (t.tag === 'untagged') continue;
      const centers = await api(`/centers?tag=${t.tag}`);
      const withCreds = centers.filter(c => c.auth_mode === 'credentials' && c.fortigate_username).length;
      const withToken = centers.filter(c => c.auth_mode === 'token').length;
      const noCreds = centers.length - withCreds - withToken;
      const color = TAG_COLORS[t.tag] || '#4a7a4a';

      html += `<div class="cred-status-card" style="border-color: ${color}30">
        <div class="cred-status-tag" style="color: ${color}">${t.tag.toUpperCase()}</div>
        <div class="cred-status-row"><span>Total</span><span style="color:var(--text)">${centers.length}</span></div>
        <div class="cred-status-row"><span>With Credentials</span><span style="color:#22c55e">${withCreds}</span></div>
        <div class="cred-status-row"><span>With Token</span><span style="color:#06b6d4">${withToken}</span></div>
        <div class="cred-status-row"><span>No Auth</span><span style="color:${noCreds > 0 ? '#ef4444' : '#4a7a4a'}">${noCreds}</span></div>
      </div>`;
    }
    grid.innerHTML = html;
  } catch (err) {
    grid.innerHTML = '<p class="empty-state">Failed to load</p>';
  }
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
