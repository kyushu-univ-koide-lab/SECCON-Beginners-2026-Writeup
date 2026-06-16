"use strict";

const crypto = require("crypto");
const express = require("express");
const fs = require("fs");
const path = require("path");
const { visitNote } = require("./bot");

const app = express();
function positiveIntegerEnv(name, defaultValue) {
  const value = Number(process.env[name] || defaultValue);
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : defaultValue;
}

const PORT = Number(process.env.PORT || 3000);
const MAX_HTML_BYTES = Number(process.env.MAX_HTML_BYTES || 16 * 1024);
const MAX_CSS_BYTES = Number(process.env.MAX_CSS_BYTES || 8 * 1024);
const MAX_LEAKS_PER_NOTE = Number(process.env.MAX_LEAKS_PER_NOTE || 5000);
const REPORT_RATE_INTERVAL_MS = Number(process.env.REPORT_RATE_INTERVAL_MS || 2000);
const REPORT_RATE_BURST = Number(process.env.REPORT_RATE_BURST || 10);
const MAX_REPORT_QUEUE = Number(process.env.MAX_REPORT_QUEUE || 30);
const REPORT_WORKERS = positiveIntegerEnv("REPORT_WORKERS", 1);
const REPORT_JOB_TIMEOUT_MS = positiveIntegerEnv("REPORT_JOB_TIMEOUT_MS", 15000);
const REDIS_URL = process.env.REDIS_URL || "";
const INSTANCE_ID = process.env.INSTANCE_ID || `pid-${process.pid}`;

const notes = new Map();
const leaks = new Map();
const reportRateLimits = new Map();
const reportQueue = [];
let activeReports = 0;
let nextReportJobId = 1;
let redisClient = null;
const PUBLIC_DIR = path.resolve(__dirname, "../../public");

app.disable("x-powered-by");
app.set("trust proxy", process.env.TRUST_PROXY === "1");
app.use(express.urlencoded({ extended: false, limit: "64kb" }));
app.use(express.json({ limit: "64kb" }));

function noteCsp() {
  return [
    "default-src 'self'",
    "script-src 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self'",
    "connect-src 'none'",
    "font-src 'none'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'"
  ].join("; ");
}

function assertValidId(id) {
  if (!/^[a-f0-9]{16}$/.test(id)) {
    const err = new Error("ノートIDが不正です");
    err.status = 400;
    throw err;
  }
}

function getBodyField(req, name) {
  const value = req.body?.[name];
  return typeof value === "string" ? value : "";
}

function wantsJson(req) {
  return req.body?.json === "1" || req.query?.json === "1" || req.is("application/json");
}

function renderTemplate(filename, values) {
  const template = fs.readFileSync(path.join(PUBLIC_DIR, filename), "utf8");
  return template.replace(/\{\{([A-Z0-9_]+)\}\}/g, (match, key) => {
    return Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : match;
  });
}

function noteKey(id) {
  return `review4b:note:${id}`;
}

function leaksKey(id) {
  return `review4b:leaks:${id}`;
}

function rateLimitKey(ip) {
  return `review4b:report-rate:${Buffer.from(ip).toString("hex")}`;
}

function parseJson(value) {
  return value ? JSON.parse(value) : null;
}

async function initRedis() {
  if (!REDIS_URL) {
    console.log(`[${INSTANCE_ID}] storage=memory`);
    return;
  }

  const { createClient } = require("redis");
  redisClient = createClient({ url: REDIS_URL });
  redisClient.on("error", (err) => {
    console.error(`[${INSTANCE_ID}] redis error`, err);
  });
  await redisClient.connect();
  console.log(`[${INSTANCE_ID}] storage=redis url=${REDIS_URL}`);
}

async function saveNote(note) {
  if (redisClient) {
    await redisClient.set(noteKey(note.id), JSON.stringify(note));
    return;
  }
  notes.set(note.id, note);
}

async function getNote(id) {
  if (redisClient) {
    return parseJson(await redisClient.get(noteKey(id)));
  }
  return notes.get(id) || null;
}

async function appendLeak(id, entry) {
  if (redisClient) {
    const key = leaksKey(id);
    await redisClient.rPush(key, JSON.stringify(entry));
    await redisClient.lTrim(key, -MAX_LEAKS_PER_NOTE, -1);
    return;
  }

  const entries = leaks.get(id) || [];
  entries.push(entry);
  if (entries.length > MAX_LEAKS_PER_NOTE) {
    entries.splice(0, entries.length - MAX_LEAKS_PER_NOTE);
  }
  leaks.set(id, entries);
}

async function getLeaks(id) {
  if (redisClient) {
    return (await redisClient.lRange(leaksKey(id), 0, -1)).map((entry) => parseJson(entry));
  }
  return leaks.get(id) || [];
}

const redisRateLimitScript = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local current = redis.call("GET", key)
local tokens = burst
local updatedAt = now

if current then
  local decoded = cjson.decode(current)
  tokens = tonumber(decoded.tokens) or burst
  updatedAt = tonumber(decoded.updatedAt) or now
end

local elapsed = now - updatedAt
tokens = math.min(burst, tokens + elapsed / interval)

local allowed = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
end

redis.call("SET", key, cjson.encode({ tokens = tokens, updatedAt = now }), "PX", math.ceil(interval * burst * 2))
return allowed
`;

async function checkReportRateLimit(ip) {
  const now = Date.now();

  if (redisClient) {
    const allowed = await redisClient.eval(redisRateLimitScript, {
      keys: [rateLimitKey(ip)],
      arguments: [
        String(now),
        String(REPORT_RATE_INTERVAL_MS),
        String(REPORT_RATE_BURST)
      ]
    });
    return Number(allowed) === 1;
  }

  const current = reportRateLimits.get(ip) || {
    tokens: REPORT_RATE_BURST,
    updatedAt: now
  };
  const elapsed = now - current.updatedAt;
  const tokens = Math.min(
    REPORT_RATE_BURST,
    current.tokens + elapsed / REPORT_RATE_INTERVAL_MS
  );

  if (tokens < 1) {
    reportRateLimits.set(ip, { tokens, updatedAt: now });
    return false;
  }

  reportRateLimits.set(ip, { tokens: tokens - 1, updatedAt: now });
  return true;
}

function throwBusyError(reason) {
  console.log(`[${INSTANCE_ID}] [report] rejected reason=${reason} pending=${pendingReports()} active=${activeReports} queued=${reportQueue.length}`);
  const err = new Error("混雑しています。しばらくしてから再度お試しください");
  err.status = 429;
  throw err;
}

function pendingReports() {
  return activeReports + reportQueue.length;
}

function timeoutError(ms) {
  const err = new Error("混雑しています。しばらくしてから再度お試しください");
  err.code = "REPORT_JOB_TIMEOUT";
  err.status = 429;
  err.timeoutMs = ms;
  return err;
}

function withTimeout(promise, ms) {
  if (!Number.isFinite(ms) || ms <= 0) {
    return promise;
  }

  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => reject(timeoutError(ms)), ms);
  });

  return Promise.race([promise, timeout]).finally(() => {
    clearTimeout(timeoutId);
  });
}

function drainReportQueue() {
  while (activeReports < REPORT_WORKERS && reportQueue.length > 0) {
    const job = reportQueue.shift();
    activeReports += 1;
    const startedAt = Date.now();
    const waitMs = startedAt - job.enqueuedAt;
    console.log(`[${INSTANCE_ID}] [report] started job=${job.jobId} id=${job.id} active=${activeReports} queued=${reportQueue.length} waitMs=${waitMs}`);

    withTimeout(visitNote(job.id), REPORT_JOB_TIMEOUT_MS)
      .then((review) => {
        job.resolve(review);
        console.log(`[${INSTANCE_ID}] [report] completed job=${job.jobId} id=${job.id} active=${activeReports} queued=${reportQueue.length} durationMs=${Date.now() - startedAt}`);
      })
      .catch((err) => {
        job.reject(err);
        const reason = err?.code === "REPORT_JOB_TIMEOUT" ? "timeout" : "error";
        console.log(`[${INSTANCE_ID}] [report] failed job=${job.jobId} id=${job.id} reason=${reason} active=${activeReports} queued=${reportQueue.length} durationMs=${Date.now() - startedAt}`);
      })
      .finally(() => {
        activeReports -= 1;
        console.log(`[${INSTANCE_ID}] [report] drained job=${job.jobId} id=${job.id} pending=${pendingReports()} active=${activeReports} queued=${reportQueue.length}`);
        drainReportQueue();
      });
  }
}

function enqueueReport(id) {
  return new Promise((resolve, reject) => {
    const job = {
      id,
      jobId: nextReportJobId,
      enqueuedAt: Date.now(),
      resolve,
      reject
    };
    nextReportJobId += 1;
    reportQueue.push(job);
    console.log(`[${INSTANCE_ID}] [report] queued job=${job.jobId} id=${id} pending=${pendingReports()} active=${activeReports} queued=${reportQueue.length}`);
    drainReportQueue();
  });
}

async function reportNote(req, id) {
  assertValidId(id);
  const note = await getNote(id);
  if (!note) {
    const err = new Error("見つかりません");
    err.status = 404;
    throw err;
  }

  if (!await checkReportRateLimit(req.ip)) {
    throwBusyError("rate-limit");
  }

  if (pendingReports() >= MAX_REPORT_QUEUE) {
    throwBusyError("queue-full");
  }

  return await enqueueReport(id);
}

app.get("/", (req, res) => {
  res.type("html").send(renderTemplate("index.html", {}));
});

app.get("/report", (req, res) => {
  res.type("html").send(renderTemplate("report.html", {
    MESSAGE: "adminに提出するノートIDを入力してください。",
    REVIEW_RESULT: ""
  }));
});

app.post("/notes", async (req, res, next) => {
  try {
    const requestedId = getBodyField(req, "id").trim();
    const id = requestedId || crypto.randomBytes(8).toString("hex");
    assertValidId(id);

    const html = getBodyField(req, "html");
    const css = getBodyField(req, "css");

    if (Buffer.byteLength(html, "utf8") > MAX_HTML_BYTES) {
      return res.status(400).send("HTML が大きすぎます");
    }
    if (Buffer.byteLength(css, "utf8") > MAX_CSS_BYTES) {
      return res.status(400).send("CSS が大きすぎます");
    }

    await saveNote({
      id,
      html,
      css,
      updatedAt: new Date().toISOString()
    });

    if (wantsJson(req)) {
      return res.json({ ok: true, id, url: `/notes/${id}`, leaks: `/leaks/${id}` });
    }

    res.redirect(303, `/notes/${id}`);
  } catch (err) {
    next(err);
  }
});

app.get("/notes/:id", async (req, res, next) => {
  try {
    const { id } = req.params;
    assertValidId(id);
    const note = await getNote(id);
    if (!note) {
      return res.status(404).send("見つかりません");
    }

    res.setHeader("Content-Security-Policy", noteCsp());
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.type("html").send(renderTemplate("note.html", {
      NOTE_ID: id,
      NOTE_CSS: note.css,
      NOTE_HTML: note.html
    }));
  } catch (err) {
    next(err);
  }
});

app.post("/report", async (req, res, next) => {
  try {
    const id = getBodyField(req, "id").trim();
    const review = await reportNote(req, id);

    if (wantsJson(req)) {
      return res.json({ ok: true, review });
    }
    res.type("html").send(renderTemplate("report.html", {
      MESSAGE: "admin がノートを確認しました。",
      REVIEW_RESULT: review.helperText || "結果を取得できませんでした。"
    }));
  } catch (err) {
    next(err);
  }
});

app.post("/report/:id", async (req, res, next) => {
  const { id } = req.params;
  try {
    const review = await reportNote(req, id);

    if (wantsJson(req)) {
      return res.json({ ok: true, review });
    }
    res.type("text").send(`admin がノートを確認しました\n${review.helperText || ""}\n`);
  } catch (err) {
    next(err);
  }
});

app.get("/leak/:id", async (req, res, next) => {
  try {
    const { id } = req.params;
    assertValidId(id);
    const note = await getNote(id);
    if (!note) {
      return res.status(404).send("見つかりません");
    }

    await appendLeak(id, {
      at: new Date().toISOString(),
      query: req.url.includes("?") ? req.url.slice(req.url.indexOf("?") + 1) : "",
      ip: req.ip
    });

    res.setHeader("Cache-Control", "no-store");
    res.status(204).end();
  } catch (err) {
    next(err);
  }
});

app.get("/leaks/:id", async (req, res, next) => {
  try {
    const { id } = req.params;
    assertValidId(id);
    const entries = await getLeaks(id);

    if (req.query.json === "1") {
      return res.json({ ok: true, id, leaks: entries });
    }

    res.type("text").send(entries.map((entry) => {
      return `[${new Date(entry.at).toISOString()}] ${entry.query}`;
    }).join("\n") + (entries.length ? "\n" : ""));
  } catch (err) {
    next(err);
  }
});

app.use((err, req, res, next) => {
  const status = err.status || 500;
  if (status >= 500) {
    console.error(err);
  }
  res.status(status).type("text").send(`${status >= 500 ? "内部エラー" : err.message}\n`);
});

async function main() {
  await initRedis();
  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[${INSTANCE_ID}] review4b web listening on http://0.0.0.0:${PORT}`);
    console.log(`[${INSTANCE_ID}] extension path: ${path.resolve(__dirname, "../../extension")}`);
  });
}

main().catch((err) => {
  console.error(`[${INSTANCE_ID}] failed to start`, err);
  process.exit(1);
});
