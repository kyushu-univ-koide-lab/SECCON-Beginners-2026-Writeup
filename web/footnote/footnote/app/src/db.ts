import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "./generated/prisma/client.js";

export const databaseUrl = process.env.DATABASE_URL ?? "file:./prisma/dev.db";

export function createPrismaClient() {
  const adapter = new PrismaBetterSqlite3({
    url: databaseUrl,
  });

  return new PrismaClient({ adapter });
}
