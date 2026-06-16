import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Timer
from time import sleep, time

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

from storage import cache_get, cache_remove_many, cache_set, ensure_user, init_storage, maybe_cleanup_storage


def secret_bytes(name: str, default_bytes: int):
    value = os.environ.get(name)
    if value is None:
        value = secrets.token_hex(default_bytes)
    return value.encode()


DATABASE = os.environ.get("DATABASE", "/tmp/coupon-stash.db")
FLAG = os.environ.get("FLAG", "ctf4b{dummy_flag}")
APP_SECRET = secret_bytes("APP_SECRET", 32)
RACE_SALT = secret_bytes("RACE_SALT", 16)

APP_DIR = Path(__file__).resolve().parent
DEFAULT_PUBLIC_DIR = APP_DIR / "public"
if not DEFAULT_PUBLIC_DIR.exists():
    DEFAULT_PUBLIC_DIR = APP_DIR.parent / "public"
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", DEFAULT_PUBLIC_DIR))
SCHEMA_PATH = APP_DIR / "schema.sql"

app = Flask(__name__)


@contextmanager
def db():
    conn = sqlite3.connect(DATABASE, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        init_storage(conn)
        payload = json.dumps(
            {
                "wallet": {"delta": 70},
                "event": {"name": "offer.applied"},
                "document": {"template": "coupon-credit"},
            },
            separators=(",", ":"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO offers (code, payload) VALUES (?, ?)",
            ("SPECIAL_VOUCHER_FOR_CTF4B", payload),
        )

def is_valid_session_id(session_id: str):
    if not 24 <= len(session_id) <= 96:
        return False
    return all(c.isalnum() or c in "-_" for c in session_id)


def issue_session_id():
    return secrets.token_urlsafe(24)


@app.before_request
def load_session():
    maybe_cleanup_storage(db)
    session_id = request.cookies.get("coupon_stash_session", "")
    if not is_valid_session_id(session_id):
        session_id = issue_session_id()
        g.set_session_cookie = True
    else:
        g.set_session_cookie = False

    g.user_id = session_id
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (g.user_id,),
            )


@app.after_request
def attach_wallet_cookie(response):
    if getattr(g, "set_session_cookie", False):
        response.set_cookie(
            "coupon_stash_session",
            g.user_id,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="Lax",
        )
    return response


def read_wallet_balance(user_id: str):
    cached = cache_get(user_id)
    if cached is not None:
        return cached

    with db() as conn:
        row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return 0
        balance = int(row["balance"])

    cache_set(user_id, balance)
    return balance


def read_wallet_balance_with(conn, user_id: str):
    row = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return 0
    return int(row["balance"])


def canonical_wallet_balance(conn, user_id: str):
    rows = conn.execute(
        """
        SELECT metadata
        FROM customer_events
        WHERE principal = ?
          AND applied_at IS NOT NULL
        ORDER BY id
        """,
        (user_id,),
    ).fetchall()

    total = 0
    for row in rows:
        metadata = json.loads(row["metadata"])
        total += int(metadata.get("delta", 0))

    spent = conn.execute(
        """
        SELECT COALESCE(SUM(cost), 0) AS total
        FROM point_spends
        WHERE principal = ?
        """,
        (user_id,),
    ).fetchone()
    total -= int(spent["total"])
    return total


def normalize_wallet_cache(conn, user_id: str):
    row = conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        cache_remove_many([user_id])
        return 0

    balance = canonical_wallet_balance(conn, user_id)
    rank = recalculate_user_rank(balance)
    conn.execute(
        """
        UPDATE users
        SET balance = ?,
            loyalty_rank = ?
        WHERE id = ?
        """,
        (balance, rank, user_id),
    )
    cache_set(user_id, balance)
    return balance


def enqueue_customer_notice(user_id: str, code: str):
    message = f"coupon={code}&user={user_id}&issued_at={time():.6f}".encode()
    return hmac.new(APP_SECRET, message, hashlib.sha256).hexdigest()


def recalculate_user_rank(balance: int):
    tier = "bronze"
    if balance >= 280:
        tier = "platinum"
    elif balance >= 140:
        tier = "gold"
    elif balance >= 70:
        tier = "silver"
    return tier


def read_offer_record(conn, code: str):
    row = conn.execute(
        "SELECT payload FROM offers WHERE code = ?",
        (code,),
    ).fetchone()
    if row is None:
        return None, "invalid coupon"
    return json.loads(row["payload"]), None


def post_ledger_adjustment(conn, user_id: str, amount: int):
    ensure_user(conn, user_id)
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, user_id),
    )
    balance = cache_get(user_id)
    if balance is None:
        balance = read_wallet_balance_with(conn, user_id)
    else:
        balance += amount
    cache_set(user_id, balance)
    return balance


def spend_wallet_points(conn, user_id: str, item: str, cost: int):
    balance = cache_get(user_id)
    if balance is None:
        balance = read_wallet_balance_with(conn, user_id)

    if balance < cost:
        return None

    balance -= cost
    cache_set(user_id, balance)

    conn.execute(
        "UPDATE users SET balance = balance - ? WHERE id = ?",
        (cost, user_id),
    )
    conn.execute(
        """
        INSERT INTO point_spends (principal, item, cost)
        VALUES (?, ?, ?)
        """,
        (user_id, item, cost),
    )
    update_loyalty_profile(conn, user_id, balance)
    return balance


def update_loyalty_profile(conn, user_id: str, balance: int):
    rank = recalculate_user_rank(balance)
    conn.execute(
        "UPDATE users SET loyalty_rank = ? WHERE id = ?",
        (rank, user_id),
    )
    return rank


def write_customer_event(conn, user_id: str, name: str, topic: str, metadata: dict):
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO customer_events (name, topic, principal, metadata)
        VALUES (?, ?, ?, ?)
        """,
        (name, topic, user_id, json.dumps(metadata, separators=(",", ":"))),
    )
    return cursor.rowcount == 1


def statement_timing(user_id: str, event_id: int):
    seed = hmac.new(
        RACE_SALT,
        f"statement:{user_id}:{event_id}".encode(),
        hashlib.sha256,
    ).digest()
    lease = (90 + seed[0] % 141) / 1000.0
    render_ratio = 1.25 + (seed[1] / 255.0) * 0.40
    audit_ratio = 8.0 + (seed[2] / 255.0) * 4.0
    return lease, lease * render_ratio, lease * audit_ratio


def record_early_refresh(conn, event_id: int, now: float):
    row = conn.execute(
        """
        SELECT early_refreshes
        FROM customer_events
        WHERE id = ? AND applied_at IS NULL
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        return

    misses = int(row["early_refreshes"]) + 1
    if misses > 2:
        conn.execute(
            """
            UPDATE customer_events
            SET early_refreshes = ?,
                review_until = ?,
                locked_until = ?
            WHERE id = ? AND applied_at IS NULL
            """,
            (misses, now + 1.2, now + 1.2, event_id),
        )
    else:
        conn.execute(
            """
            UPDATE customer_events
            SET early_refreshes = ?
            WHERE id = ? AND applied_at IS NULL
            """,
            (misses, event_id),
        )


def close_statement_ticket(conn, event_id: int, token: str, metadata: dict):
    cursor = conn.execute(
        """
        UPDATE customer_events
        SET applied_at = CURRENT_TIMESTAMP,
            metadata = ?,
            locked_by = NULL,
            locked_until = NULL
        WHERE id = ?
          AND locked_by = ?
          AND applied_at IS NULL
        """,
        (json.dumps(metadata, separators=(",", ":")), event_id, token),
    )
    return cursor.rowcount == 1


def claim_statement_ticket(conn, user_id: str):
    token = secrets.token_hex(12)
    now = time()
    reprint_limit = 5

    row = conn.execute(
        """
        SELECT id, locked_until, review_until, claim_count
        FROM customer_events
        WHERE principal = ?
          AND applied_at IS NULL
        ORDER BY id
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None, None, None, None

    event_id = int(row["id"])

    if float(row["review_until"] or 0) > now:
        return None, None, None, None

    lease, render_delay, audit_delay = statement_timing(user_id, event_id)

    if float(row["locked_until"] or 0) > now:
        record_early_refresh(conn, event_id, now)
        return None, None, None, None

    if int(row["claim_count"] or 0) >= reprint_limit:
        return None, None, None, None

    cursor = conn.execute(
        """
        UPDATE customer_events
        SET locked_by = ?,
            locked_until = ?,
            early_refreshes = 0,
            claim_count = COALESCE(claim_count, 0) + 1
        WHERE id = ?
          AND principal = ?
          AND applied_at IS NULL
          AND COALESCE(review_until, 0) < ?
          AND COALESCE(locked_until, 0) < ?
          AND COALESCE(claim_count, 0) < ?
        """,
        (
            token,
            now + lease,
            event_id,
            user_id,
            now,
            now,
            reprint_limit,
        ),
    )
    if cursor.rowcount != 1:
        return None, None, None, None

    event = conn.execute(
        """
        SELECT id, name, topic, metadata
        FROM customer_events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()
    return event, token, render_delay, audit_delay


def make_statement_package(
    user_id: str,
    code: str,
    balance: int,
    template: str,
    render_delay: float,
):
    issued_at = f"{time():.6f}"
    sleep(render_delay)
    return hmac.new(
        APP_SECRET,
        f"{user_id}:{code}:{balance}:{template}:{issued_at}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]


def register_offer_event(conn, user_id: str, code: str):
    conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_user(conn, user_id)
        offer, error = read_offer_record(conn, code)
        if error is not None:
            conn.execute("ROLLBACK")
            return None, error

        created = write_customer_event(
            conn,
            user_id,
            offer["event"]["name"],
            code,
            {
                "delta": int(offer["wallet"]["delta"]),
                "template": offer["document"]["template"],
            },
        )
        if not created:
            conn.execute("ROLLBACK")
            return None, "claim limit reached"

        enqueue_customer_notice(user_id, code)
        conn.execute("COMMIT")
        return {"accepted": True}, None
    except Exception:
        conn.execute("ROLLBACK")
        raise


def reconcile_statement_batch(user_id: str):
    with db() as conn:
        event, token, render_delay, audit_delay = claim_statement_ticket(conn, user_id)
    if event is None:
        return {"accepted": True}

    metadata = json.loads(event["metadata"])
    balance_before = read_wallet_balance(user_id)
    document_id = make_statement_package(
        user_id,
        event["topic"],
        balance_before,
        metadata["template"],
        render_delay,
    )
    metadata["document"] = document_id

    with db() as conn:
        balance = post_ledger_adjustment(conn, user_id, int(metadata["delta"]))
        update_loyalty_profile(conn, user_id, balance)
        close_statement_ticket(conn, int(event["id"]), token, metadata)

    schedule_wallet_audit(user_id, audit_delay)

    return {"accepted": True}


def schedule_wallet_audit(user_id: str, delay: float):
    def run_audit():
        with db() as conn:
            normalize_wallet_cache(conn, user_id)

    timer = Timer(delay, run_audit)
    timer.daemon = True
    timer.start()


def quote_price(item: str):
    if item == "flag":
        return 260
    if item == "secret":
        return 50
    return None


def issue_checkout_quote(user_id: str, item: str):
    now = time()
    balance = read_wallet_balance(user_id)
    price = quote_price(item)
    if price is None:
        return None

    if balance >= price:
        expires_at = now + 30.0
        payload = {
            "sub": user_id,
            "item": item,
            "balance": balance,
            "exp": expires_at,
            "nonce": secrets.token_urlsafe(8),
        }
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        sig = hmac.new(APP_SECRET, body.encode(), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    with db() as conn:
        row = conn.execute(
            """
            SELECT quote_misses, quote_cooldown_until
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return None

    if float(row["quote_cooldown_until"] or 0) > now:
        return None

    misses = int(row["quote_misses"] or 0) + 1
    cooldown_until = 0
    if misses > 2:
        cooldown_until = now + 0.85

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET quote_misses = ?,
                quote_cooldown_until = ?
            WHERE id = ?
            """,
            (misses, cooldown_until, user_id),
        )
    return None


def read_checkout_quote(user_id: str, quote_id: str):
    try:
        body, sig = quote_id.split(".", 1)
        expected = hmac.new(APP_SECRET, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None

        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        item = str(payload.get("item", ""))
        if payload.get("sub") != user_id:
            return None
        if float(payload.get("exp", 0)) < time():
            return None
        price = quote_price(item)
        if price is None:
            return None
        if int(payload.get("balance", 0)) < price:
            return None
        return payload
    except Exception:
        return None


def wants_json():
    return request.is_json or "application/json" in request.headers.get("Accept", "")


def maybe_json(payload: dict, status: int = 200, text=None):
    if wants_json():
        return jsonify(payload), status
    return (text if text is not None else payload.get("error", "ok")), status


def request_value(name: str, default: str = ""):
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return str(data.get(name, default)).strip()
    return request.form.get(name, default).strip()


def request_quote():
    return request_value("quote")


@app.get("/")
def index():
    balance = read_wallet_balance(g.user_id)
    with db() as conn:
        row = conn.execute(
            "SELECT loyalty_rank FROM users WHERE id = ?",
            (g.user_id,),
        ).fetchone()
    wallet_status = row["loyalty_rank"] if row is not None else "bronze"
    html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
    return render_template_string(
        html,
        balance=balance,
        wallet_status=wallet_status,
        flag_price=260,
        secret_price=50,
    )


@app.post("/redeem")
def redeem():
    code = request_value("code")

    with db() as conn:
        _, error = register_offer_event(conn, g.user_id, code)

        if error == "invalid coupon":
            return maybe_json(
                {"ok": False, "error": "invalid coupon"},
                404,
                "invalid coupon",
            )

        if error == "claim limit reached":
            return maybe_json(
                {"ok": False, "error": "このクーポンはすでに使用されています"},
                409,
                "このクーポンはすでに使用されています",
            )

    if wants_json():
        return jsonify(
            {
                "ok": True,
                "status": "received",
                "balance": read_wallet_balance(g.user_id),
            }
        ), 202
    return redirect(url_for("index"))


@app.post("/support/statement")
def support_statement():
    reconcile_statement_batch(g.user_id)

    if wants_json():
        return jsonify(
            {
                "ok": True,
                "status": "received",
                "balance": read_wallet_balance(g.user_id),
            }
        ), 202
    return redirect(url_for("index"))


@app.post("/cart/quote")
def cart_quote():
    item = request_value("item", "flag")

    quote_id = issue_checkout_quote(g.user_id, item)

    if quote_id is None:
        return maybe_json({"ok": True, "status": "received"}, 202, "received")

    if wants_json():
        return jsonify({"ok": True, "item": item, "quote": quote_id}), 201
    return quote_id, 201


def complete_secret_exchange():
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            balance = spend_wallet_points(
                conn,
                g.user_id,
                "secret",
                50,
            )
            if balance is None:
                conn.execute("ROLLBACK")
                return maybe_json(
                    {
                        "ok": False,
                        "error": "points are not enough",
                        "balance": read_wallet_balance(g.user_id),
                    },
                    402,
                    "points are not enough",
                )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    if wants_json():
        return jsonify(
            {
                "ok": True,
                "message": "secretを交換しました",
                "reward": "https://youtu.be/dQw4w9WgXcQ",
                "balance": balance,
            }
        )
    return "https://youtu.be/dQw4w9WgXcQ"


@app.post("/exchange")
def exchange_item():
    quote_id = request_quote()

    if not quote_id:
        return maybe_json({"ok": False, "error": "missing quote"}, 400)

    payload = read_checkout_quote(g.user_id, quote_id)
    if payload is None:
        return maybe_json({"ok": False, "error": "invalid quote"}, 403)

    item = payload.get("item")
    if item == "flag":
        if wants_json():
            return jsonify({"ok": True, "flag": FLAG})
        return FLAG

    if item == "secret":
        return complete_secret_exchange()

    return maybe_json({"ok": False, "error": "invalid quote"}, 403)


@app.post("/wallet/new")
def new_wallet():
    g.user_id = issue_session_id()
    g.set_session_cookie = True
    with db() as conn:
        ensure_user(conn, g.user_id)
    cache_set(g.user_id, 0)
    return redirect(url_for("index"))


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
