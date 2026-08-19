/* ====================================================================
   سپر | Popup logic
   ==================================================================== */

const BACKEND_URL = "http://127.0.0.1:5000";
const STORAGE_KEY_API = "shepar_api_key";

const statusPill = document.getElementById("statusPill");
const connectedSection = document.getElementById("connectedSection");
const disconnectedSection = document.getElementById("disconnectedSection");
const errorText = document.getElementById("errorText");

async function getApiKey() {
  const data = await chrome.storage.local.get(STORAGE_KEY_API);
  return data[STORAGE_KEY_API] || "";
}

async function setApiKey(key) {
  await chrome.storage.local.set({ [STORAGE_KEY_API]: key });
}

async function backendGet(path, apiKey) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: { "X-API-Key": apiKey },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function refreshUi() {
  const apiKey = await getApiKey();

  if (!apiKey) {
    setOffline();
    return;
  }

  try {
    const stats = await backendGet("/api/stats", apiKey);
    setOnline();
    document.getElementById("blockedToday").textContent = stats.blocked;
    document.getElementById("activeRules").textContent = `${stats.active_rules}/${stats.total_rules}`;
    connectedSection.style.display = "flex";
    disconnectedSection.style.display = "none";
  } catch (e) {
    setOffline("بک‌اند در دسترس نیست. مطمئن شوید سرور اجرا شده.");
  }
}

function setOnline() {
  statusPill.textContent = "متصل";
  statusPill.className = "status-pill online";
}

function setOffline(message) {
  statusPill.textContent = "قطع";
  statusPill.className = "status-pill offline";
  connectedSection.style.display = "none";
  disconnectedSection.style.display = "flex";
  if (message) errorText.textContent = message;
}

document.getElementById("connectBtn").addEventListener("click", async () => {
  const value = document.getElementById("apiKeyInput").value.trim();
  if (!value) {
    errorText.textContent = "کلید را وارد کنید.";
    return;
  }
  try {
    await backendGet("/api/stats", value);
    await setApiKey(value);
    errorText.textContent = "";
    chrome.runtime.sendMessage({ type: "shepar_resync" });
    refreshUi();
  } catch (e) {
    errorText.textContent = "کلید نامعتبر است یا سرور در دسترس نیست.";
  }
});

document.getElementById("openDashboardBtn").addEventListener("click", () => {
  chrome.tabs.create({ url: BACKEND_URL });
});

document.getElementById("resyncBtn").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "shepar_resync" }, () => {
    refreshUi();
  });
});

refreshUi();
