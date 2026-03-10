const API_BASE = window.API_BASE || "http://localhost:8000";

async function fetchJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
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

loadDashboard();
