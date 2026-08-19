/* ====================================================================
   سپر | Dashboard logic
   ==================================================================== */

const API_BASE = window.location.origin;
const STORAGE_KEY = "shepar_api_key";

let apiKey = localStorage.getItem(STORAGE_KEY) || "";
let activeRuleType = "";
let pollTimer = null;

// ---------------------------------------------------------------------
// کمک‌کننده‌های فراخوانی API
// ---------------------------------------------------------------------

async function apiCall(path, { method = "GET", body = null } = {}) {
  const headers = { "X-API-Key": apiKey };
  if (body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    showAuthModal("کلید نامعتبر است. دوباره وارد کنید.");
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || `خطا (${res.status})`);
  }
  return res.json();
}

// ---------------------------------------------------------------------
// مودال احراز هویت
// ---------------------------------------------------------------------

const authOverlay = document.getElementById("authOverlay");
const apiKeyInput = document.getElementById("apiKeyInput");
const authError = document.getElementById("authError");

function showAuthModal(message = "") {
  authOverlay.classList.remove("hidden");
  authError.textContent = message;
  if (pollTimer) clearInterval(pollTimer);
}

function hideAuthModal() {
  authOverlay.classList.add("hidden");
}

document.getElementById("connectBtn").addEventListener("click", async () => {
  const value = apiKeyInput.value.trim();
  if (!value) {
    authError.textContent = "کلید را وارد کنید.";
    return;
  }
  apiKey = value;
  try {
    await apiCall("/api/stats");
    localStorage.setItem(STORAGE_KEY, apiKey);
    hideAuthModal();
    bootstrap();
  } catch (e) {
    authError.textContent = "کلید نامعتبر است یا سرور در دسترس نیست.";
  }
});

apiKeyInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("connectBtn").click();
});

// ---------------------------------------------------------------------
// رادار: تبدیل رویداد بلاک به نقطه‌ی روی رادار
// ---------------------------------------------------------------------

const radarBlips = document.getElementById("radarBlips");

function spawnBlip() {
  const angle = Math.random() * 2 * Math.PI;
  const radius = 20 + Math.random() * 65;
  const x = 100 + radius * Math.cos(angle);
  const y = 100 + radius * Math.sin(angle);

  const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  circle.setAttribute("cx", x.toFixed(1));
  circle.setAttribute("cy", y.toFixed(1));
  circle.setAttribute("r", "4");
  circle.setAttribute("class", "radar-blip");
  radarBlips.appendChild(circle);
  setTimeout(() => circle.remove(), 1600);
}

// ---------------------------------------------------------------------
// آمار
// ---------------------------------------------------------------------

async function refreshStats() {
  const stats = await apiCall("/api/stats");
  document.getElementById("statBlocked").textContent = stats.blocked;
  document.getElementById("statAllowed").textContent = stats.allowed;
  document.getElementById("statRules").textContent = `${stats.active_rules}/${stats.total_rules}`;
  document.getElementById("statTotal").textContent = stats.total_events;
}

// ---------------------------------------------------------------------
// قوانین
// ---------------------------------------------------------------------

const rulesList = document.getElementById("rulesList");

function ruleTypeLabel(t) { return t === "cookie" ? "کوکی" : "شبکه"; }

function renderRules(rules) {
  if (!rules.length) {
    rulesList.innerHTML = `<p class="empty-state">هنوز قانونی ثبت نشده. یک الگو اضافه کنید.</p>`;
    return;
  }
  rulesList.innerHTML = rules.map((r) => `
    <div class="rule-item ${r.enabled ? "" : "disabled"}" data-id="${r.id}">
      <div class="rule-main">
        <span class="rule-pattern">${escapeHtml(r.pattern)}</span>
        <div class="rule-meta">
          <span class="badge badge-type">${ruleTypeLabel(r.rule_type)}</span>
          <span class="badge ${r.action === "block" ? "badge-block" : "badge-allow"}">${r.action === "block" ? "بلاک" : "اجازه"}</span>
          ${r.note ? `<span>${escapeHtml(r.note)}</span>` : ""}
        </div>
      </div>
      <div class="rule-actions">
        <button class="icon-btn toggle-btn" title="${r.enabled ? "غیرفعال کن" : "فعال کن"}">${r.enabled ? "⏸" : "▶"}</button>
        <button class="icon-btn danger delete-btn" title="حذف">✕</button>
      </div>
    </div>
  `).join("");
}

async function refreshRules() {
  const qs = activeRuleType ? `?type=${activeRuleType}` : "";
  const rules = await apiCall(`/api/rules${qs}`);
  renderRules(rules);
}

document.getElementById("ruleTypeTabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  btn.classList.add("active");
  activeRuleType = btn.dataset.type;
  refreshRules().catch(console.error);
});

rulesList.addEventListener("click", async (e) => {
  const item = e.target.closest(".rule-item");
  if (!item) return;
  const id = item.dataset.id;

  if (e.target.closest(".toggle-btn")) {
    const isEnabled = !item.classList.contains("disabled");
    await apiCall(`/api/rules/${id}/toggle`, { method: "POST", body: { enabled: !isEnabled } });
    refreshRules().catch(console.error);
  }

  if (e.target.closest(".delete-btn")) {
    if (!confirm("این قانون حذف شود؟")) return;
    await apiCall(`/api/rules/${id}`, { method: "DELETE" });
    refreshRules().catch(console.error);
    refreshStats().catch(console.error);
  }
});

document.getElementById("addRuleForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const pattern = document.getElementById("rulePattern").value.trim();
  const rule_type = document.getElementById("ruleType").value;
  const action = document.getElementById("ruleAction").value;
  const note = document.getElementById("ruleNote").value.trim();

  if (!pattern) return;

  try {
    await apiCall("/api/rules", { method: "POST", body: { pattern, rule_type, action, note } });
    document.getElementById("rulePattern").value = "";
    document.getElementById("ruleNote").value = "";
    refreshRules().catch(console.error);
    refreshStats().catch(console.error);
  } catch (err) {
    alert(err.message);
  }
});

// ---------------------------------------------------------------------
// لاگ‌ها
// ---------------------------------------------------------------------

const logsList = document.getElementById("logsList");
let lastSeenTimestamp = 0;

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function renderLogs(logs) {
  if (!logs.length) {
    logsList.innerHTML = `<p class="empty-state">هنوز رویدادی ثبت نشده.</p>`;
    return;
  }
  logsList.innerHTML = logs.map((log) => `
    <div class="log-item ${log.action === "block" ? "is-block" : "is-allow"}">
      <span class="log-target">${escapeHtml(log.target)}</span>
      <span class="log-time">${formatTime(log.timestamp)}</span>
    </div>
  `).join("");
}

async function refreshLogs() {
  const logs = await apiCall("/api/logs?limit=100");

  // برای هر رویداد بلاک جدید (که قبلاً ندیده بودیم)، روی رادار نشانش بده
  const newest = logs[0]?.timestamp || 0;
  if (lastSeenTimestamp > 0) {
    const freshBlocks = logs.filter((l) => l.timestamp > lastSeenTimestamp && l.action === "block");
    freshBlocks.forEach(() => spawnBlip());
  }
  lastSeenTimestamp = Math.max(newest, lastSeenTimestamp);

  renderLogs(logs);
}

document.getElementById("refreshLogsBtn").addEventListener("click", () => {
  refreshLogs().catch(console.error);
});

// ---------------------------------------------------------------------
// کمکی
// ---------------------------------------------------------------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// بوت‌استرپ
// ---------------------------------------------------------------------

async function bootstrap() {
  try {
    await Promise.all([refreshStats(), refreshRules(), refreshLogs()]);
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => {
      refreshStats().catch(console.error);
      refreshLogs().catch(console.error);
    }, 4000);
  } catch (e) {
    console.error(e);
  }
}

(function init() {
  if (!apiKey) {
    showAuthModal();
  } else {
    hideAuthModal();
    bootstrap();
  }
})();
