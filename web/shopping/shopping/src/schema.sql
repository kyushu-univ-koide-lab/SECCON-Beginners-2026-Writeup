CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL,
    loyalty_rank TEXT NOT NULL DEFAULT 'bronze',
    quote_misses INTEGER NOT NULL DEFAULT 0,
    quote_cooldown_until REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS offers (
    code TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    topic TEXT NOT NULL,
    principal TEXT NOT NULL,
    metadata TEXT NOT NULL,
    applied_at TEXT,
    locked_by TEXT,
    locked_until REAL,
    review_until REAL NOT NULL DEFAULT 0,
    early_refreshes INTEGER NOT NULL DEFAULT 0,
    claim_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, topic, principal)
);

CREATE TABLE IF NOT EXISTS point_spends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    principal TEXT NOT NULL,
    item TEXT NOT NULL,
    cost INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
