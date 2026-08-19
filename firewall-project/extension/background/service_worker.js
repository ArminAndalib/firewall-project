/* ====================================================================
   سپر | Background Service Worker
   - کوکی‌های ورودی/خروجی را با بک‌اند چک می‌کند و در صورت بلاک‌بودن حذف می‌کند
   - قوانین شبکه را از بک‌اند می‌گیرد و به‌صورت declarativeNetRequest اعمال می‌کند
   - چون بک‌اند فقط لوکال (127.0.0.1) است، هیچ داده‌ای به سرور خارجی نمی‌رود
   ==================================================================== */

const BACKEND_URL = "http://127.0.0.1:5000";
const STORAGE_KEYS = {
  apiKey: "shepar_api_key",
  rulesCache: "shepar_rules_cache",
  statsCache: "shepar_stats_cache",
};

const COOKIE_CHECK_TTL_MS = 5000;
const cookieDecisionCache = new Map(); // name -> { action, expiresAt }

// ---------------------------------------------------------------------
// کمک‌کننده‌ها
// ---------------------------------------------------------------------

async function getApiKey() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.apiKey);
  return data[STORAGE_KEYS.apiKey] || "";
}

async function backendFetch(path, options = {}) {
  const apiKey = await getApiKey();
  if (!apiKey) return null;

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      ...options,
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    // بک‌اند در دسترس نیست؛ fail-open برای کوکی‌ها تا مرورگر مسدود نشود،
    // اما قوانین شبکه‌ی محلی (declarativeNetRequest) همچنان فعال می‌مانند
    return null;
  }
}

// ---------------------------------------------------------------------
// مدیریت کوکی‌ها
// ---------------------------------------------------------------------

async function evaluateCookie(name) {
  const cached = cookieDecisionCache.get(name);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.action;
  }

  const result = await backendFetch("/api/evaluate/cookie", {
    method: "POST",
    body: JSON.stringify({ name }),
  });

  const action = result?.action || "allow";
  cookieDecisionCache.set(name, { action, expiresAt: Date.now() + COOKIE_CHECK_TTL_MS });
  return action;
}

chrome.cookies.onChanged.addListener(async (changeInfo) => {
  // فقط کوکی‌های تازه‌ست‌شده را بررسی می‌کنیم، نه حذف‌شده‌ها (برای جلوگیری از حلقه)
  if (changeInfo.removed) return;

  const cookie = changeInfo.cookie;
  const action = await evaluateCookie(cookie.name);

  if (action === "block") {
    const protocol = cookie.secure ? "https://" : "http://";
    const domain = cookie.domain.startsWith(".") ? cookie.domain.slice(1) : cookie.domain;
    const url = `${protocol}${domain}${cookie.path}`;

    try {
      await chrome.cookies.remove({ url, name: cookie.name, storeId: cookie.storeId });
    } catch (e) {
      // اگر حذف ناموفق بود (مثلا دامنه نامعتبر برای ساخت url)، نادیده می‌گیریم
    }
  }
});

// ---------------------------------------------------------------------
// همگام‌سازی قوانین شبکه با declarativeNetRequest
// ---------------------------------------------------------------------

function patternToDnrFilter(pattern) {
  // الگوی glob ساده (با * ) را به urlFilter قابل فهم برای DNR تبدیل می‌کند
  return pattern.replace(/\*/g, "*");
}

async function syncNetworkRulesToDnr() {
  const rules = await backendFetch("/api/rules?type=network");
  if (!rules) return;

  const dnrRules = rules
    .filter((r) => r.enabled && r.action === "block")
    .slice(0, 4900) // سقف امن زیر محدودیت DNR (5000 قانون دینامیک)
    .map((r, idx) => ({
      id: idx + 1,
      priority: 1,
      action: { type: "block" },
      condition: {
        urlFilter: patternToDnrFilter(r.pattern),
        resourceTypes: [
          "main_frame", "sub_frame", "script", "image", "stylesheet",
          "xmlhttprequest", "ping", "media", "font", "object", "other",
        ],
      },
    }));

  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  const existingIds = existing.map((r) => r.id);

  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existingIds,
    addRules: dnrRules,
  });

  await chrome.storage.local.set({ [STORAGE_KEYS.rulesCache]: rules });
}

// هر ۳۰ ثانیه قوانین را از بک‌اند تازه‌سازی می‌کند
chrome.alarms.create("shepar_sync", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "shepar_sync") {
    syncNetworkRulesToDnr().catch(() => {});
  }
});

chrome.runtime.onStartup.addListener(() => {
  syncNetworkRulesToDnr().catch(() => {});
});
chrome.runtime.onInstalled.addListener(() => {
  syncNetworkRulesToDnr().catch(() => {});
});

// پیام از popup برای همگام‌سازی فوری (مثلا بعد از وارد کردن API Key)
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "shepar_resync") {
    syncNetworkRulesToDnr().then(() => sendResponse({ ok: true })).catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (msg.type === "shepar_get_blocked_count") {
    chrome.declarativeNetRequest.getMatchedRules({}, (details) => {
      sendResponse({ count: details?.rulesMatchedInfo?.length || 0 });
    });
    return true;
  }
});
