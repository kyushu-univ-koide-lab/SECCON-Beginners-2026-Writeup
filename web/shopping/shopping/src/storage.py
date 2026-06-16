from collections import OrderedDict
from threading import Lock
from time import time


# キャッシュ処理用
WALLET_CACHE = OrderedDict()
CACHE_LOCK = Lock()
MAINTENANCE_LOCK = Lock()
LAST_MAINTENANCE = 0.0


def cache_get(user_id: str):
    with CACHE_LOCK:
        if user_id not in WALLET_CACHE:
            return None
        value = WALLET_CACHE.pop(user_id)
        WALLET_CACHE[user_id] = value
        return value


def cache_set(user_id: str, balance: int):
    with CACHE_LOCK:
        WALLET_CACHE[user_id] = balance
        WALLET_CACHE.move_to_end(user_id)
        while len(WALLET_CACHE) > 4096:
            WALLET_CACHE.popitem(last=False)


def cache_remove_many(user_ids):
    with CACHE_LOCK:
        for user_id in user_ids:
            WALLET_CACHE.pop(user_id, None)


def ensure_user(conn, user_id: str):
    conn.execute("INSERT OR IGNORE INTO users (id, balance, created_at, last_seen) VALUES (?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)", (user_id,))
    conn.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


def init_storage(conn):
    conn.execute("PRAGMA wal_autocheckpoint=100")
    conn.execute("PRAGMA journal_size_limit=1048576")
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    for name in ("created_at", "last_seen"):
        if name not in columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} TEXT")
    conn.execute("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), last_seen = COALESCE(last_seen, CURRENT_TIMESTAMP)")
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)",
        "CREATE INDEX IF NOT EXISTS idx_customer_events_principal ON customer_events(principal)",
        "CREATE INDEX IF NOT EXISTS idx_point_spends_principal ON point_spends(principal)",
    ):
        conn.execute(sql)
    cleanup_storage(conn)


def cleanup_storage(conn):
    user_ids = [row["id"] for row in conn.execute("SELECT id FROM users WHERE last_seen < datetime('now', '-3600 seconds') LIMIT 1000")]
    extra = int(conn.execute("SELECT COUNT(*) - 2000 AS n FROM users").fetchone()["n"] or 0)
    if extra > 0:
        user_ids += [row["id"] for row in conn.execute("SELECT id FROM users ORDER BY last_seen, created_at LIMIT ?", (min(extra, 1000),))]
    if user_ids:
        placeholders = ",".join("?" for _ in user_ids)
        for table in ("point_spends", "customer_events", "users"):
            column = "id" if table == "users" else "principal"
            conn.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", user_ids)
        cache_remove_many(user_ids)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def maybe_cleanup_storage(db):
    global LAST_MAINTENANCE
    now = time()
    if now - LAST_MAINTENANCE < 60 or not MAINTENANCE_LOCK.acquire(blocking=False):
        return
    try:
        if now - LAST_MAINTENANCE >= 60:
            with db() as conn:
                cleanup_storage(conn)
            LAST_MAINTENANCE = now
    finally:
        MAINTENANCE_LOCK.release()
