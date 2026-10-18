import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vurgun_radari.db")
_db_lock = threading.Lock()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS deals (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    cheapest_merchant TEXT NOT NULL,
                    cheapest_price REAL NOT NULL,
                    second_merchant TEXT NOT NULL,
                    second_price REAL NOT NULL,
                    reference_price REAL NOT NULL,
                    discount_pct REAL NOT NULL,
                    spread_pct REAL NOT NULL,
                    suggested_resell_price REAL NOT NULL,
                    estimated_profit_tl REAL NOT NULL,
                    roi_pct REAL NOT NULL,
                    deal_type TEXT NOT NULL,
                    offers_json TEXT NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    recorded_at INTEGER NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            default_topic = f"vurgun-radari-{secrets.token_hex(4)}"
            defaults = {
                "ntfy_topic": os.environ.get("NTFY_TOPIC", default_topic),
                "ntfy_server": "https://ntfy.sh",
                "min_discount_pct": "20",
                "min_profit_tl": "350",
                "amazon_affiliate_tag": "vurgunradari-21",
                "hepsiburada_aff_id": "",
                "telegram_bot_token": "",
                "telegram_chat_id": "@vurgunradari",
                "telegram_auto_post": "1",
                "x_api_key": "",
                "x_api_secret": "",
                "x_access_token": "",
                "x_access_secret": "",
                "x_auth_token": "",
                "x_auto_post": "1",
                "auto_notify": "1",
                "scan_interval_sec": "90",
            }
            for k, v in defaults.items():
                cur.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (k, v),
                )
            conn.commit()
        finally:
            conn.close()


def get_settings() -> Dict[str, str]:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cur.fetchall()}
        finally:
            conn.close()


def update_settings(new_settings: Dict[str, Any]) -> Dict[str, str]:
    allowed_keys = {
        "ntfy_topic",
        "ntfy_server",
        "min_discount_pct",
        "min_profit_tl",
        "amazon_affiliate_tag",
        "hepsiburada_aff_id",
        "telegram_bot_token",
        "telegram_chat_id",
        "telegram_auto_post",
        "x_api_key",
        "x_api_secret",
        "x_access_token",
        "x_access_secret",
        "x_auth_token",
        "x_auto_post",
        "auto_notify",
        "scan_interval_sec",
    }
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            for k, v in new_settings.items():
                if k in allowed_keys and v is not None:
                    val_str = str(v).strip()[:160]
                    cur.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (k, val_str),
                    )
            conn.commit()
        finally:
            conn.close()
    return get_settings()


def upsert_deal(deal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inserts or updates a deal using parameterized SQL queries.
    Returns metadata indicating if this deal is newly discovered or dropped further in price.
    """
    now = int(time.time())
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT cheapest_price, notified FROM deals WHERE id = ?",
                (deal["id"],),
            )
            existing = cur.fetchone()

            is_new = existing is None
            price_dropped_more = False
            already_notified = False

            if existing is not None:
                old_price = float(existing["cheapest_price"])
                already_notified = bool(existing["notified"])
                if deal["cheapest_price"] < old_price * 0.97:
                    price_dropped_more = True
                    already_notified = False

            cur.execute(
                """
                INSERT INTO deals (
                    id, source, category, title, url,
                    cheapest_merchant, cheapest_price,
                    second_merchant, second_price, reference_price,
                    discount_pct, spread_pct,
                    suggested_resell_price, estimated_profit_tl, roi_pct,
                    deal_type, offers_json, notified, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    cheapest_merchant = excluded.cheapest_merchant,
                    cheapest_price = excluded.cheapest_price,
                    second_merchant = excluded.second_merchant,
                    second_price = excluded.second_price,
                    reference_price = excluded.reference_price,
                    discount_pct = excluded.discount_pct,
                    spread_pct = excluded.spread_pct,
                    suggested_resell_price = excluded.suggested_resell_price,
                    estimated_profit_tl = excluded.estimated_profit_tl,
                    roi_pct = excluded.roi_pct,
                    deal_type = excluded.deal_type,
                    offers_json = excluded.offers_json,
                    notified = ?,
                    updated_at = excluded.updated_at
                """,
                (
                    deal["id"],
                    deal["source"],
                    deal["category"],
                    deal["title"],
                    deal["url"],
                    deal["cheapest_merchant"],
                    deal["cheapest_price"],
                    deal["second_merchant"],
                    deal["second_price"],
                    deal["reference_price"],
                    deal["discount_pct"],
                    deal["spread_pct"],
                    deal["suggested_resell_price"],
                    deal["estimated_profit_tl"],
                    deal["roi_pct"],
                    deal["deal_type"],
                    deal["offers_json"],
                    1 if already_notified else 0,
                    now,
                    now,
                    1 if already_notified else 0,
                ),
            )

            if is_new or price_dropped_more:
                cur.execute(
                    "INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                    (deal["id"], deal["cheapest_price"], now),
                )

            conn.commit()
            return {
                "is_new": is_new,
                "price_dropped_more": price_dropped_more,
                "already_notified": already_notified,
            }
        finally:
            conn.close()


def mark_deal_notified(deal_id: str) -> None:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE deals SET notified = 1 WHERE id = ?", (deal_id,))
            conn.commit()
        finally:
            conn.close()


def get_unnotified_deals(
    min_disc: float = 10.0,
    min_profit: float = 30.0,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            safe_limit = max(1, min(int(limit), 50))
            cur.execute(
                """
                SELECT * FROM deals
                WHERE notified = 0
                  AND url LIKE 'https://www.amazon.com.tr/dp/%'
                  AND (discount_pct >= ? OR estimated_profit_tl >= ?)
                ORDER BY discount_pct DESC, estimated_profit_tl DESC, updated_at DESC
                LIMIT ?
                """,
                (float(min_disc), float(min_profit), safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()


def list_deals(filter_type: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    with _db_lock:
        conn = get_connection()
        try:
            cur = conn.cursor()
            safe_limit = max(1, min(int(limit), 300))
            if filter_type == "arbitrage":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE estimated_profit_tl > 0
                    ORDER BY estimated_profit_tl DESC, discount_pct DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            elif filter_type == "low_budget":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE cheapest_price > 100 AND cheapest_price <= 10000 AND estimated_profit_tl >= 100
                    ORDER BY roi_pct DESC, estimated_profit_tl DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            elif filter_type == "amazon":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE source = 'Amazon TR Canlı' OR cheapest_merchant LIKE '%Amazon%'
                    ORDER BY updated_at DESC, discount_pct DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            elif filter_type == "cosmetics":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE category LIKE '%Kozmetik%' OR category LIKE '%Cilt%' OR category LIKE '%Parfüm%' OR category LIKE '%Bakım%' OR category LIKE '%Şampuan%'
                    ORDER BY updated_at DESC, discount_pct DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            elif filter_type == "market_home":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE category LIKE '%Market%' OR category LIKE '%Kahve%' OR category LIKE '%Temizlik%' OR category LIKE '%Mutfak%' OR category LIKE '%Bebek%' OR category LIKE '%Yapı%'
                    ORDER BY updated_at DESC, discount_pct DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            elif filter_type == "hot_threads":
                cur.execute(
                    """
                    SELECT * FROM deals
                    WHERE source = 'DH Sıcak Fırsat'
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM deals
                    ORDER BY discount_pct DESC, estimated_profit_tl DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
