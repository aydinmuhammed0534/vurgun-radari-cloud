import json
import os
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

import db
import notifier
import scanner

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
CLOUD_REPO_SLUG = "aydinmuhammed0534/vurgun-radari-cloud"

_scan_state: Dict[str, Any] = {
    "is_scanning": False,
    "last_scan_ts": 0,
    "last_result": None,
}
_scan_lock = threading.Lock()


def _sync_github_secrets_background(settings: Dict[str, str]) -> None:
    gh_bin = "/opt/homebrew/bin/gh"
    if not os.path.isfile(gh_bin):
        return
    mapping = {
        "NTFY_TOPIC": settings.get("ntfy_topic", ""),
        "TELEGRAM_BOT_TOKEN": settings.get("telegram_bot_token", ""),
        "X_AUTH_TOKEN": settings.get("x_auth_token", ""),
        "X_API_KEY": settings.get("x_api_key", ""),
        "X_API_SECRET": settings.get("x_api_secret", ""),
        "X_ACCESS_TOKEN": settings.get("x_access_token", ""),
        "X_ACCESS_SECRET": settings.get("x_access_secret", ""),
    }
    for secret_name, val in mapping.items():
        clean_val = str(val or "").strip()
        if not clean_val or clean_val.startswith("***"):
            continue
        try:
            subprocess.run(
                [gh_bin, "secret", "set", secret_name, "--repo", CLOUD_REPO_SLUG],
                input=clean_val,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except Exception:
            pass


def mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return ""
    return f"***-***-{token[-4:]}"


def sanitize_settings_for_client(raw_settings: Dict[str, str]) -> Dict[str, str]:
    safe = dict(raw_settings)
    tok = safe.get("telegram_bot_token", "")
    safe["telegram_bot_token"] = mask_token(tok) if tok else ""
    safe["telegram_configured"] = "1" if (tok and safe.get("telegram_chat_id")) else "0"

    x_auth = safe.get("x_auth_token", "")
    x_key = safe.get("x_api_key", "")
    x_sec = safe.get("x_api_secret", "")
    x_atok = safe.get("x_access_token", "")
    x_asec = safe.get("x_access_secret", "")
    safe["x_auth_token"] = mask_token(x_auth) if x_auth else ""
    safe["x_api_key"] = mask_token(x_key) if x_key else ""
    safe["x_api_secret"] = mask_token(x_sec) if x_sec else ""
    safe["x_access_token"] = mask_token(x_atok) if x_atok else ""
    safe["x_access_secret"] = mask_token(x_asec) if x_asec else ""
    safe["x_configured"] = "1" if (x_auth or (x_key and x_sec and x_atok and x_asec)) else "0"
    return safe


def trigger_scan_background(send_alerts: bool = True) -> bool:
    with _scan_lock:
        if _scan_state["is_scanning"]:
            return False
        _scan_state["is_scanning"] = True

    def _worker() -> None:
        try:
            res = scanner.run_full_scan(trigger_notifications=send_alerts)
            with _scan_lock:
                _scan_state["last_scan_ts"] = int(time.time())
                _scan_state["last_result"] = res
        finally:
            with _scan_lock:
                _scan_state["is_scanning"] = False

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def trigger_sniper_background() -> bool:
    with _scan_lock:
        if _scan_state["is_scanning"]:
            return False
        _scan_state["is_scanning"] = True

    def _worker() -> None:
        try:
            res = scanner.run_sniper_scan(trigger_notifications=True)
            with _scan_lock:
                _scan_state["last_scan_ts"] = int(time.time())
                _scan_state["last_result"] = res
        finally:
            with _scan_lock:
                _scan_state["is_scanning"] = False

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def background_scheduler_loop() -> None:
    time.sleep(1)
    trigger_scan_background(send_alerts=True)
    last_full_ts = int(time.time())
    while True:
        time.sleep(20)
        now = int(time.time())
        if _scan_state["is_scanning"]:
            continue
        if now - last_full_ts >= 90:
            last_full_ts = now
            trigger_scan_background(send_alerts=True)
        else:
            trigger_sniper_background()


class RadarRequestHandler(BaseHTTPRequestHandler):
    # TODO(security): Local single-user tool bound strictly to 127.0.0.1; OAuth/MFA not required for localhost CLI daemon.

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_security_headers(self, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_header("Content-Type", content_type)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none';",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cache-Control", "no-store")

    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self._send_security_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, filename: str, content_type: str) -> None:
        safe_name = os.path.basename(filename)
        resolved = os.path.realpath(os.path.join(STATIC_DIR, safe_name))
        if not resolved.startswith(os.path.realpath(STATIC_DIR) + os.sep):
            self._send_json(403, {"error": "Access denied"})
            return
        if not os.path.isfile(resolved):
            self._send_json(404, {"error": "Not found"})
            return
        with open(resolved, "rb") as f:
            content = f.read()
        self.send_response(200)
        self._send_security_headers(content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._serve_static("styles.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_static("app.js", "application/javascript; charset=utf-8")
            return

        if path == "/api/state":
            qs = urllib.parse.parse_qs(parsed.query)
            flt = (qs.get("filter") or ["all"])[0]
            settings = db.get_settings()
            deals = db.list_deals(filter_type=flt, limit=120)
            amz_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
            hb_aff = settings.get("hepsiburada_aff_id", "")
            for d in deals:
                d["affiliate_url"] = notifier.build_affiliate_url(
                    d["url"],
                    amz_tag,
                    hb_aff,
                    product_title=d.get("title", ""),
                    merchant=d.get("cheapest_merchant", ""),
                )
                d["share_text"] = notifier.build_telegram_share_text(d, amz_tag, hb_aff)
                d["x_tweet_url"] = notifier.build_x_tweet_intent_url(d, amz_tag, hb_aff)
                d["resell_text"] = notifier.build_resell_listing_text(d)
            self._send_json(
                200,
                {
                    "settings": sanitize_settings_for_client(settings),
                    "scan_state": _scan_state,
                    "deals": deals,
                },
            )
            return

        self._send_json(404, {"error": "Endpoint bulunamadı"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(min(content_len, 65536)) if content_len > 0 else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8", errors="ignore") or "{}")
        except Exception:
            body = {}

        if path == "/api/scan":
            started = trigger_scan_background(send_alerts=True)
            self._send_json(200, {"ok": True, "started": started})
            return

        if path == "/api/settings":
            if isinstance(body, dict):
                for secret_field in (
                    "telegram_bot_token",
                    "x_auth_token",
                    "x_api_key",
                    "x_api_secret",
                    "x_access_token",
                    "x_access_secret",
                ):
                    val = str(body.get(secret_field) or "").strip()
                    if val.startswith("***"):
                        body.pop(secret_field, None)
                updated = db.update_settings(body)
                threading.Thread(
                    target=_sync_github_secrets_background,
                    args=(updated,),
                    daemon=True,
                ).start()
            else:
                updated = db.get_settings()
            self._send_json(200, {"ok": True, "settings": sanitize_settings_for_client(updated)})
            return

        if path == "/api/test-ntfy":
            settings = db.get_settings()
            if isinstance(body, dict) and body.get("ntfy_topic"):
                settings = db.update_settings({"ntfy_topic": body["ntfy_topic"]})
            deals = db.list_deals(filter_type="low_budget", limit=1) or db.list_deals(limit=1)
            sample_deal = (
                deals[0]
                if deals
                else {
                    "title": "Asus ROG Gladius III Wireless AimPoint Oyuncu Mouse",
                    "url": "https://www.cimri.com/oyuncu-mouse",
                    "cheapest_merchant": "idefix",
                    "cheapest_price": 3899.0,
                    "second_merchant": "PttAVM",
                    "second_price": 6821.0,
                    "reference_price": 6821.0,
                    "discount_pct": 42.7,
                    "suggested_resell_price": 6000.0,
                    "estimated_profit_tl": 2101.0,
                    "roi_pct": 53.9,
                }
            )
            res = notifier.send_ntfy_alert(sample_deal, settings, is_test=True)
            self._send_json(200, res)
            return

        if path == "/api/test-telegram":
            if isinstance(body, dict):
                updates: Dict[str, Any] = {}
                tok = str(body.get("telegram_bot_token") or "").strip()
                if tok and not tok.startswith("***"):
                    updates["telegram_bot_token"] = tok
                if body.get("telegram_chat_id") is not None:
                    updates["telegram_chat_id"] = str(body.get("telegram_chat_id")).strip()
                if updates:
                    db.update_settings(updates)
            settings = db.get_settings()
            deals = db.list_deals(filter_type="low_budget", limit=1) or db.list_deals(limit=1)
            sample_deal = (
                deals[0]
                if deals
                else {
                    "title": "Asus ROG Gladius III Wireless AimPoint Oyuncu Mouse",
                    "url": "https://www.cimri.com/oyuncu-mouse",
                    "cheapest_merchant": "idefix",
                    "cheapest_price": 3899.0,
                    "second_merchant": "PttAVM",
                    "second_price": 6821.0,
                    "reference_price": 6821.0,
                    "discount_pct": 42.7,
                }
            )
            res = notifier.send_telegram_channel_post(sample_deal, settings, is_test=True)
            self._send_json(200, res)
            return

        if path == "/api/notify-deal":
            deal_id = str(body.get("deal_id") or "")
            settings = db.get_settings()
            all_deals = db.list_deals(limit=250)
            target = next((x for x in all_deals if x["id"] == deal_id), None)
            if not target:
                self._send_json(404, {"ok": False, "error": "Fırsat bulunamadı"})
                return
            res = notifier.send_ntfy_alert(target, settings, is_test=False)
            if res.get("ok"):
                db.mark_deal_notified(deal_id)
            self._send_json(200, res)
            return

        if path == "/api/telegram-deal":
            deal_id = str(body.get("deal_id") or "")
            settings = db.get_settings()
            all_deals = db.list_deals(limit=250)
            target = next((x for x in all_deals if x["id"] == deal_id), None)
            if not target:
                self._send_json(404, {"ok": False, "error": "Fırsat bulunamadı"})
                return
            res = notifier.send_telegram_channel_post(target, settings, is_test=False)
            self._send_json(200, res)
            return

        self._send_json(404, {"error": "Endpoint bulunamadı"})


def main() -> None:
    db.init_db()
    scheduler = threading.Thread(target=background_scheduler_loop, daemon=True)
    scheduler.start()

    host = "127.0.0.1"
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), RadarRequestHandler)
    print(f"Vurgun Radari aktif: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
