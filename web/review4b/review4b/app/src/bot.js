"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const puppeteer = require("puppeteer-core");

const PORT = Number(process.env.PORT || 3000);
const DEFAULT_BASE_URL = `http://127.0.0.1:${PORT}`;
const BOT_BASE_URL = process.env.BOT_BASE_URL || DEFAULT_BASE_URL;
const EXTENSION_DIR = path.resolve(__dirname, "../../extension");

function chromeExecutablePath() {
  if (process.env.CHROME_BIN) {
    return process.env.CHROME_BIN;
  }

  const candidates = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  throw new Error("Chrome/Chromium executable not found. Set CHROME_BIN.");
}

async function rmrf(target) {
  await fs.promises.rm(target, { recursive: true, force: true });
}

function botHeadlessMode() {
  if (process.env.BOT_HEADLESS === "true") {
    return true;
  }
  return false;
}

async function visitNote(id) {
  const url = new URL(`/notes/${encodeURIComponent(id)}`, BOT_BASE_URL).toString();
  const userDataDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "review4b-"));

  const browser = await puppeteer.launch({
    executablePath: chromeExecutablePath(),
    headless: botHeadlessMode(),
    pipe: true,
    enableExtensions: [EXTENSION_DIR],
    userDataDir,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--js-flags=--jitless"
    ]
  });

  try {
    const page = await browser.newPage();
    await page.goto(url, {
      waitUntil: "networkidle0",
      timeout: Number(process.env.BOT_TIMEOUT_MS || 10000)
    });
    await new Promise((resolve) => setTimeout(resolve, Number(process.env.BOT_STAY_MS || 1000)));

    const helperText = await page.evaluate(() => {
      return document.getElementById("review4b-helper-result")?.textContent || "";
    });

    return {
      helperText
    };
  } finally {
    await browser.close().catch(() => undefined);
    await rmrf(userDataDir).catch(() => undefined);
  }
}

module.exports = { visitNote };
