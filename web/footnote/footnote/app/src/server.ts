import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import { rateLimit } from "express-rate-limit";
import {
  InvalidFilterError,
  buildAdvancedWhere,
  buildKeywordWhere,
  isAdvancedSearch,
} from "./filter.js";
import { createPrismaClient } from "./db.js";

const prisma = createPrismaClient();
const app = express();
const port = Number(process.env.PORT ?? 44566);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.join(__dirname, "..", "public");
const flag = process.env.FLAG ?? "ctf4b{dummy_flag}";
const trustProxyHops = Number(process.env.TRUST_PROXY_HOPS ?? 1);

if (!Number.isInteger(trustProxyHops) || trustProxyHops < 1) {
  throw new Error("TRUST_PROXY_HOPS must be a positive integer");
}

const articleSelect = {
  id: true,
  title: true,
  body: true,
  author: {
    select: {
      profile: {
        select: {
          displayName: true,
          bio: true,
        },
      },
    },
  },
};

const searchLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 300,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests" },
});

const claimLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests" },
});

app.set("trust proxy", trustProxyHops);
app.use(express.json({ limit: "8kb" }));
app.use(express.static(publicDir));

app.get("/api/articles/search", searchLimiter, async (req, res) => {
  try {
    const filterWhere = isAdvancedSearch({
      field: req.query.field,
      op: req.query.op,
      value: req.query.value,
    })
      ? buildAdvancedWhere({
          field: req.query.field,
          op: req.query.op,
          value: req.query.value,
        })
      : buildKeywordWhere(req.query.q);

    const articles = await prisma.article.findMany({
      where: {
        AND: [{ published: true }, filterWhere],
      },
      orderBy: { id: "asc" },
      select: articleSelect,
    });

    res.json({
      count: articles.length,
      articles,
    });
  } catch (error) {
    if (error instanceof InvalidFilterError) {
      res.status(400).json({ error: "invalid filter" });
      return;
    }

    console.error(error);
    res.status(400).json({ error: "invalid query" });
  }
});

app.post("/api/claim", claimLimiter, async (req, res) => {
  if (!req.body || typeof req.body.memo !== "string") {
    res.status(400).json({ error: "invalid request" });
    return;
  }

  const admin = await prisma.user.findUnique({
    where: { name: "admin" },
    select: {
      profile: {
        select: {
          secretMemo: true,
        },
      },
    },
  });

  if (!admin?.profile || req.body.memo !== admin.profile.secretMemo) {
    res.status(403).json({ error: "forbidden" });
    return;
  }

  res.json({ flag });
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Server is running on port ${port}`);
  console.log(`Trusting ${trustProxyHops} proxy hop(s) for client IPs`);
});
