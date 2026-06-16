importScripts("secret.js");

const DEFAULT_PUBLIC_KEYS = ["theme", "helperVersion", "lastUpdated"];
const ALLOWED_HOSTS = new Set(["web", "localhost", "127.0.0.1"]);

async function initializeStorage() {
  const current = await chrome.storage.local.get("helperVersion");
  if (current.helperVersion) {
    return;
  }

  await chrome.storage.local.set({
    theme: "light",
    helperVersion: "1.0.0",
    lastUpdated: "2026-06-01",
    flag: self.FLAG
  });
}

chrome.runtime.onInstalled.addListener(() => {
  initializeStorage();
});

function isAllowedNoteUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    return url.protocol === "http:" &&
      ALLOWED_HOSTS.has(url.hostname) &&
      url.pathname.startsWith("/notes/");
  } catch {
    return false;
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    await initializeStorage();

    if (!sender.tab || !isAllowedNoteUrl(sender.tab.url)) {
      throw new Error("bad sender");
    }

    if (!msg || msg.cmd !== "settings.get") {
      throw new Error("unknown command");
    }

    const keys = Object.prototype.hasOwnProperty.call(msg, "keys")
      ? msg.keys
      : DEFAULT_PUBLIC_KEYS;

    if (String(keys).includes("flag") || String(keys).includes("secret")) {
      throw new Error("blocked key");
    }

    const result = await chrome.storage.local.get(keys);

    sendResponse({
      ok: true,
      result
    });
  })().catch((e) => {
    sendResponse({
      ok: false,
      error: e.message
    });
  });

  return true;
});
