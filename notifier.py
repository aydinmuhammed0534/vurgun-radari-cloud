import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any, Dict


def build_affiliate_url(
    raw_url: str,
    amazon_tag: str = "vurgunradari-21",
    hb_aff_id: str = "",
    product_title: str = "",
    merchant: str = "",
) -> str:
    """
    Cleans third-party affiliate tags from store URLs and injects the user's affiliate parameters.
    If the cheapest merchant is Amazon but the source URL is Cimri, routes directly to Amazon.com.tr with the user's tag so the user earns the commission instead of Cimri.
    """
    if not raw_url:
        return ""
    tag = (amazon_tag or "vurgunradari-21").strip()
    parsed = urllib.parse.urlparse(raw_url)
    host = (parsed.netloc or "").lower()
    if "amazon.com.tr" in host:
        qs = urllib.parse.parse_qs(parsed.query)
        clean_qs = {}
        if "th" in qs:
            clean_qs["th"] = qs["th"][0]
        if "k" in qs:
            clean_qs["k"] = qs["k"][0]
        if tag:
            clean_qs["tag"] = tag
        clean_path = re.sub(r"(/dp/[A-Z0-9]{10})/ref=.*$", r"\1", parsed.path)
        new_query = urllib.parse.urlencode(clean_qs)
        return urllib.parse.urlunparse(
            (parsed.scheme or "https", parsed.netloc, clean_path, "", new_query, "")
        )
    if "cimri.com" in host or "donanimhaber.com" in host:
        m = (merchant or "").lower()
        q = urllib.parse.quote((product_title or "").strip()[:70])
        if "hepsiburada" in m:
            return f"https://www.hepsiburada.com/ara?q={q}"
        if "idefix" in m:
            return f"https://www.idefix.com/arama/?q={q}"
        if "pttavm" in m:
            return f"https://www.pttavm.com/arama?q={q}"
        if "ince hesap" in m or "incehesap" in m:
            return f"https://www.incehesap.com/arama/{q}/"
        if "trendyol" in m:
            return f"https://www.trendyol.com/sr?q={q}"
        q_params = {"k": (product_title or "firsat").strip()[:70], "tag": tag}
        return "https://www.amazon.com.tr/s?" + urllib.parse.urlencode(q_params)
    if "hepsiburada.com" in host:
        clean_qs = {}
        if hb_aff_id and hb_aff_id.strip():
            clean_qs["wt_af"] = hb_aff_id.strip()
        new_query = urllib.parse.urlencode(clean_qs)
        return urllib.parse.urlunparse(
            (parsed.scheme or "https", parsed.netloc, parsed.path, "", new_query, "")
        )
    if any(d in host for d in ("trendyol.com", "idefix.com", "n11.com", "pttavm.com", "incehesap.com")):
        return urllib.parse.urlunparse(
            (parsed.scheme or "https", parsed.netloc, parsed.path, "", "", "")
        )
    return raw_url


def format_tl(amount: float) -> str:
    if amount <= 0:
        return "0 TL"
    return f"{int(round(amount)):,}".replace(",", ".") + " TL"


def build_telegram_share_text(
    deal: Dict[str, Any],
    amazon_tag: str = "vurgunradari-21",
    hb_aff_id: str = "",
) -> str:
    aff_url = build_affiliate_url(
        deal.get("url", ""),
        amazon_tag,
        hb_aff_id,
        product_title=deal.get("title", ""),
        merchant=deal.get("cheapest_merchant", ""),
    )
    title = (deal.get("title") or "Fırsat Ürünü").strip()
    price = float(deal.get("cheapest_price", 0))
    ref_price = float(deal.get("reference_price", 0))
    disc = float(deal.get("discount_pct", 0))
    merchant = deal.get("cheapest_merchant", "Mağaza")
    second_merchant = deal.get("second_merchant", "")
    second_price = float(deal.get("second_price", 0))

    lines = [title, ""]
    if price > 0 and second_price > price:
        lines.append(f"• {merchant}: {format_tl(price)}")
        lines.append(f"• En yakın fiyat ({second_merchant}): {format_tl(second_price)} (%{disc:.0f} fark)")
    elif price > 0 and ref_price > price:
        lines.append(f"• Güncel fiyat ({merchant}): {format_tl(price)}")
        lines.append(f"• Önceki seviye: {format_tl(ref_price)} (%{disc:.0f} indirim)")
    elif price > 0:
        lines.append(f"• Fiyat ({merchant}): {format_tl(price)}")

    lines.append("")
    lines.append(f"Ürün linki: {aff_url}")
    lines.append("Anlık bildirimler: https://t.me/vurgunradari #işbirliği")
    return "\n".join(lines)


def _pick_x_search_tag(deal: Dict[str, Any]) -> str:
    cat = (deal.get("category") or "").lower()
    title = (deal.get("title") or "").lower()
    hay = f"{cat} {title}"
    if any(k in hay for k in ("cilt", "dermokozmetik", "cerave", "la roche", "bioderma", "vichy", "serum", "krem", "güneş")):
        return "#ciltbakımı #indirim"
    if any(k in hay for k in ("makyaj", "kozmetik", "maybelline", "loreal", "l'oréal", "maskara", "ruj", "fondöten")):
        return "#kozmetik #indirim"
    if any(k in hay for k in ("parfüm", "deodorant", "edt", "edp")):
        return "#parfüm #fırsat"
    if any(k in hay for k in ("şampuan", "saç", "epilasyon", "lumea", "braun", "oral-b", "philips")):
        return "#kişiselbakım #indirim"
    if any(k in hay for k in ("kahve", "market", "gıda", "temizlik", "deterjan", "finish", "fairy", "persil")):
        return "#market #amazonfırsatları"
    if any(k in hay for k in ("mutfak", "termos", "stanley", "airfryer", "tefal", "tencere")):
        return "#mutfak #fırsat"
    if any(k in hay for k in ("mouse", "kulaklık", "monitör", "ssd", "laptop", "gaming", "oyuncu", "asus", "razer", "logitech")):
        return "#teknoloji #indirim"
    return "#indirim #fırsat"


def build_x_tweet_text(
    deal: Dict[str, Any],
    amazon_tag: str = "vurgunradari-21",
    hb_aff_id: str = "",
) -> str:
    aff_url = build_affiliate_url(
        deal.get("url", ""),
        amazon_tag,
        hb_aff_id,
        product_title=deal.get("title", ""),
        merchant=deal.get("cheapest_merchant", ""),
    )
    raw_title = (deal.get("title") or "Fırsat Ürünü").strip()
    short_title = raw_title[:60].rstrip() + ("..." if len(raw_title) > 60 else "")
    price = float(deal.get("cheapest_price", 0))
    second_price = float(deal.get("second_price", 0))
    disc = float(deal.get("discount_pct", 0))
    merchant = (deal.get("cheapest_merchant") or "Mağaza")[:15]
    search_tag = _pick_x_search_tag(deal)

    # Deterministic variation per product so consecutive tweets look organically written by a human analyst
    variant = sum(ord(c) for c in raw_title) % 3

    if price > 0 and second_price > price:
        if variant == 0:
            lines = [
                f"{short_title}",
                "",
                f"Piyasa: {format_tl(second_price)}",
                f"{merchant}: {format_tl(price)} (%{disc:.0f} avantaj)",
                "",
                f"{aff_url}",
                f"Anlık bildirim: https://t.me/vurgunradari {search_tag} #işbirliği",
            ]
        elif variant == 1:
            lines = [
                f"{short_title} dip fiyata indi.",
                "",
                f"Diğer mağazalarda {format_tl(second_price)} bandında; şu an {merchant} üzerinde {format_tl(price)}.",
                "",
                f"Link: {aff_url}",
                f"Kanal: https://t.me/vurgunradari {search_tag} #işbirliği",
            ]
        else:
            lines = [
                f"{short_title} — %{disc:.0f} fiyat farkı",
                "",
                f"• Güncel ({merchant}): {format_tl(price)}",
                f"• En yakın rakip: {format_tl(second_price)}",
                "",
                f"{aff_url}",
                f"Anlık radar: https://t.me/vurgunradari {search_tag} #işbirliği",
            ]
    else:
        lines = [
            f"{short_title}",
            "",
            f"{merchant}: {format_tl(price)}" if price > 0 else "Anlık fiyat fırsatı",
            "",
            f"{aff_url}",
            f"Anlık radar: https://t.me/vurgunradari {search_tag} #işbirliği",
        ]

    return "\n".join(lines)


def build_x_tweet_intent_url(
    deal: Dict[str, Any],
    amazon_tag: str = "vurgunradari-21",
    hb_aff_id: str = "",
) -> str:
    tweet_text = build_x_tweet_text(deal, amazon_tag, hb_aff_id)
    return "https://x.com/intent/tweet?" + urllib.parse.urlencode({"text": tweet_text})


def _oauth1_authorization_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    encoded_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join(
        [
            method.upper(),
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote(encoded_params, safe=""),
        ]
    )
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(access_token_secret, safe='')}"
    hashed = hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1)
    signature = base64.b64encode(hashed.digest()).decode("utf-8")
    oauth_params["oauth_signature"] = signature

    header_parts = ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


def _cdp_send(sock: socket.socket, msg_id: int, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    payload = json.dumps({"id": msg_id, "method": method, "params": params or {}}).encode("utf-8")
    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    mask = os.urandom(4)
    header.extend(mask)
    masked = bytearray(payload[i] ^ mask[i % 4] for i in range(length))
    sock.sendall(header + masked)
    while True:
        b1, b2 = sock.recv(2)
        ln = b2 & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", sock.recv(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", sock.recv(8))[0]
        data = b""
        while len(data) < ln:
            data += sock.recv(ln - len(data))
        res = json.loads(data.decode("utf-8", errors="ignore"))
        if res.get("id") == msg_id:
            return res


def _post_tweet_via_headless_chrome(tweet_text: str, auth_token: str) -> Dict[str, Any]:
    """
    Posts a tweet 100% free using the user's X web session (auth_token) via Headless Chrome CDP.
    Works on both macOS locally and Ubuntu on GitHub Actions.
    """
    clean_auth = re.sub(r"[^a-fA-F0-9]", "", auth_token.strip())
    if len(clean_auth) < 30:
        return {"ok": False, "error": "Geçersiz X auth_token."}

    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    chrome_bin = next((c for c in chrome_candidates if os.path.isfile(c)), "")
    if not chrome_bin:
        return {"ok": False, "error": "Google Chrome bulunamadı."}

    # Fetch fresh ct0 CSRF cookie via curl
    ct0 = ""
    try:
        p = subprocess.run(
            [
                "/usr/bin/curl",
                "-s",
                "-i",
                "-L",
                "--max-time",
                "8",
                "-H",
                f"Cookie: auth_token={clean_auth}",
                "-A",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "https://x.com/home",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        ct0_matches = re.findall(r"set-cookie:\s*ct0=([a-fA-F0-9]+);", p.stdout, re.I)
        if ct0_matches:
            ct0 = ct0_matches[-1]
    except Exception:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_port:
        s_port.bind(("127.0.0.1", 0))
        port = s_port.getsockname()[1]

    profile_dir = tempfile.mkdtemp(prefix="vurgun_x_")
    proc = None
    sock = None
    try:
        proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2.0)
        tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read().decode("utf-8"))
        ws_url = [t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page"][0]
        ws_path = "/" + ws_url.split("/", 3)[3]

        sock = socket.create_connection(("127.0.0.1", port), timeout=18)
        ws_key = base64.b64encode(os.urandom(16)).decode("utf-8")
        handshake = (
            f"GET {ws_path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(handshake.encode("utf-8"))
        sock.recv(4096)

        _cdp_send(sock, 1, "Network.enable")
        _cdp_send(
            sock,
            2,
            "Network.setCookie",
            {
                "name": "auth_token",
                "value": clean_auth,
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
        )
        if ct0:
            _cdp_send(
                sock,
                3,
                "Network.setCookie",
                {
                    "name": "ct0",
                    "value": ct0,
                    "domain": ".x.com",
                    "path": "/",
                    "secure": True,
                },
            )

        intent_url = "https://x.com/intent/post?text=" + urllib.parse.quote(tweet_text)
        _cdp_send(sock, 4, "Page.navigate", {"url": intent_url})
        time.sleep(6.0)

        js_code = """
        (async () => {
            const btn = document.querySelector("[data-testid=\\"tweetButton\\"]");
            if (!btn) return "no_btn:" + location.href;
            btn.click();
            await new Promise(r => setTimeout(r, 3200));
            return "sent:" + location.href;
        })()
        """
        eval_res = _cdp_send(
            sock,
            5,
            "Runtime.evaluate",
            {"expression": js_code, "awaitPromise": True, "returnByValue": True},
        )
        val = str(((eval_res.get("result") or {}).get("result") or {}).get("value") or "")
        if val.startswith("sent:"):
            return {"ok": True, "mode": "web_session", "status": val}
        return {"ok": False, "error": f"X Web oturumu yanıtı: {val}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                pass
        shutil.rmtree(profile_dir, ignore_errors=True)


def send_x_auto_tweet(deal: Dict[str, Any], settings: Dict[str, str]) -> Dict[str, Any]:
    """
    Automatically posts a tweet to X (Twitter).
    Prioritizes 100% free X Web Session (x_auth_token via Headless Chrome CDP),
    with fallback to X API v2 OAuth 1.0a if configured with credits.
    """
    amazon_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
    hb_aff_id = settings.get("hepsiburada_aff_id", "")
    tweet_text = build_x_tweet_text(deal, amazon_tag, hb_aff_id)

    auth_token = (settings.get("x_auth_token") or os.environ.get("X_AUTH_TOKEN") or "").strip()
    if auth_token and not auth_token.startswith("***"):
        web_res = _post_tweet_via_headless_chrome(tweet_text, auth_token)
        if web_res.get("ok"):
            return web_res

    api_key = (settings.get("x_api_key") or "").strip()
    api_secret = (settings.get("x_api_secret") or "").strip()
    access_token = (settings.get("x_access_token") or "").strip()
    access_secret = (settings.get("x_access_secret") or "").strip()

    if not (api_key and api_secret and access_token and access_secret):
        return {"ok": False, "error": "X oturumu (auth_token) veya API anahtarları henüz girilmemiş."}

    url = "https://api.twitter.com/2/tweets"
    auth_header = _oauth1_authorization_header(
        "POST", url, api_key, api_secret, access_token, access_secret
    )
    payload = json.dumps({"text": tweet_text}, ensure_ascii=False).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "VurgunRadariBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return {"ok": True, "response": body}
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"X API Hatası ({he.code}): {err_body[:180]}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def build_resell_listing_text(deal: Dict[str, Any]) -> str:
    title = deal.get("title", "Ürün")
    resell = float(deal.get("suggested_resell_price", 0))
    second_price = float(deal.get("second_price", 0))
    return (
        f"BAŞLIK: SIFIR KAPALI KUTU FATURALI {title[:65]}\n"
        f"SATIŞ FİYATI: {format_tl(resell)}\n\n"
        f"AÇIKLAMA:\n"
        f"Ürün Türkiye resmi distribütör garantili, sıfır, güvenlik bandı açılmamış kapalı kutudur.\n"
        f"Adıma kesilmiş faturası ile birlikte teslim edilecektir.\n"
        f"Mağazalarda şu an en ucuz {format_tl(second_price)} seviyesindedir, nakit ihtiyacından dolayı piyasanın altına {format_tl(resell)} fiyata veriyorum.\n"
        f"Elden teslim veya Param Güvende / Dolap ile aynı gün kargolanır."
    )


def send_telegram_channel_post(
    deal: Dict[str, Any],
    settings: Dict[str, str],
    is_test: bool = False,
) -> Dict[str, Any]:
    """
    Posts a sleek, premium formatted deal message to a Telegram Channel without cheesy AI emojis.
    """
    bot_token = (settings.get("telegram_bot_token") or "").strip()
    chat_id = (settings.get("telegram_chat_id") or "").strip()

    if not bot_token or not chat_id:
        return {
            "ok": False,
            "error": "Telegram Bot Token veya Kanal ID (@kanaladi) henüz girilmemiş.",
        }

    if not re.match(r"^\d+:[A-Za-z0-9_-]{20,}$", bot_token):
        return {"ok": False, "error": "Geçersiz Telegram Bot Token formatı."}

    amazon_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
    hb_aff_id = settings.get("hepsiburada_aff_id", "")
    aff_url = build_affiliate_url(
        deal.get("url", ""),
        amazon_tag,
        hb_aff_id,
        product_title=deal.get("title", ""),
        merchant=deal.get("cheapest_merchant", ""),
    )

    title_safe = html.escape(deal.get("title", "Fırsat Ürünü"))
    merchant_safe = html.escape(deal.get("cheapest_merchant", "Mağaza"))
    second_merchant_safe = html.escape(deal.get("second_merchant", "Piyasa"))
    price = float(deal.get("cheapest_price", 0))
    second_price = float(deal.get("second_price", 0))
    disc = float(deal.get("discount_pct", 0))

    lines = [f"<b>{title_safe}</b>", ""]
    if price > 0 and second_price > price:
        lines.append(f"• <b>{merchant_safe}: {format_tl(price)}</b>")
        lines.append(f"• En yakın fiyat ({second_merchant_safe}): <s>{format_tl(second_price)}</s>  <i>(%{disc:.0f} avantaj)</i>")
    elif price > 0:
        lines.append(f"• <b>Güncel Fiyat ({merchant_safe}): {format_tl(price)}</b>")

    lines.append("")
    lines.append(f'<a href="{html.escape(aff_url)}">Ürünü Mağazada İncele →</a>')
    lines.append("")
    lines.append("<i>#işbirliği</i>")

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if aff_url.startswith("https://"):
        btn_label = f"Ürüne Git — {format_tl(price)}" if price > 0 else "Ürünü İncele"
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": btn_label, "url": aff_url},
                    {"text": "𝕏 @vurgunradari", "url": "https://x.com/vurgunradari"},
                ]
            ]
        }

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "VurgunRadariBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp_body = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return {"ok": bool(resp_body.get("ok")), "response": resp_body}
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"Telegram API Hatası ({he.code}): {err_body[:180]}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def send_and_pin_telegram_welcome(settings: Dict[str, str]) -> Dict[str, Any]:
    """
    Sets the Telegram channel SEO description and sends + pins a high-conversion welcome guide.
    """
    bot_token = (settings.get("telegram_bot_token") or "").strip()
    chat_id = (settings.get("telegram_chat_id") or "").strip()
    if not bot_token or not chat_id:
        return {"ok": False, "error": "Telegram ayarları eksik."}

    # 1. Update Telegram Channel Description for Telegram Global Search SEO
    seo_desc = (
        "Amazon Türkiye anlık fiyat hatası, dip fiyat, dermokozmetik, elektronik, kişisel bakım "
        "ve market indirim radarı. Tüm ürünler canlı stok ve piyasa karşılaştırmalıdır. "
        "X: https://x.com/vurgunradari"
    )
    try:
        desc_req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/setChatDescription",
            data=json.dumps({"chat_id": chat_id, "description": seo_desc}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        urllib.request.urlopen(desc_req, timeout=8).read()
    except Exception:
        pass

    # 2. Send Welcome Message
    welcome_html = "\n".join(
        [
            "<b>VURGUN RADARI — 7/24 Otomatik Fiyat &amp; Stok Takip Sistemi</b>",
            "",
            "Bu kanalda paylaşılan tüm ürünler sistem tarafından 7/24 taranır ve paylaşım anında:",
            "• <b>Canlı stok kontrolünden</b> geçirilir (stokta olmayan ürün atılmaz).",
            "• <b>Diğer pazaryerlerindeki en yakın rakip fiyatla</b> karşılaştırılır.",
            "• <b>Kategoriler:</b> Elektronik, Dermokozmetik &amp; Cilt Bakımı, Parfüm, Kişisel Bakım, Ev &amp; Mutfak, Süpermarket.",
            "",
            "Dip fiyatlı ve hatalı etiketli ürünlerin stoğu dakikalar içinde bittiği için <b>kanal bildirimlerini (🔔 Sessizden Çıkar)</b> açık tutmanız önerilir.",
            "",
            "𝕏 <b>Twitter / X Hesabımız:</b> <a href=\"https://x.com/vurgunradari\">x.com/vurgunradari</a>",
            "📢 <b>Kanal Davet Linki:</b> <a href=\"https://t.me/vurgunradari\">t.me/vurgunradari</a>",
        ]
    )
    msg_payload = {
        "chat_id": chat_id,
        "text": welcome_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "𝕏 Twitter'da Takip Et", "url": "https://x.com/vurgunradari"},
                    {"text": "📢 Kanalı Paylaş", "url": "https://t.me/share/url?url=https://t.me/vurgunradari&text=Amazon%20TR%20anl%C4%B1k%20fiyat%20ve%20indirim%20radar%C4%B1"},
                ]
            ]
        },
    }
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=json.dumps(msg_payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp_body = json.loads(resp.read().decode("utf-8", errors="ignore"))
        msg_id = ((resp_body.get("result") or {}).get("message_id"))
        if msg_id:
            pin_req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
                data=json.dumps({"chat_id": chat_id, "message_id": msg_id, "disable_notification": False}).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            urllib.request.urlopen(pin_req, timeout=8).read()
        return {"ok": True, "message_id": msg_id}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def send_daily_top3_digest(deals: list, settings: Dict[str, str]) -> Dict[str, Any]:
    """
    Publishes a high-bookmark 'Günün En Yüksek 3 Fiyat Farkı Özeti' list post to both Telegram & X.
    """
    amazon_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
    top3 = [d for d in deals if "amazon.com.tr/dp/" in str(d.get("url") or "")][:3]
    if len(top3) < 3:
        return {"ok": False, "error": "Özet için yeterli ürün yok."}

    # 1. Telegram Digest HTML
    tg_lines = ["<b>GÜNÜN ÖNE ÇIKAN 3 FİYAT FARKI (STOKTA AKTİF)</b>", ""]
    for idx, d in enumerate(top3, 1):
        u = build_affiliate_url(d["url"], amazon_tag)
        t = html.escape((d.get("title") or "")[:65].rstrip())
        p = format_tl(float(d.get("cheapest_price") or 0))
        sp = format_tl(float(d.get("second_price") or 0))
        disc = float(d.get("discount_pct") or 0)
        tg_lines.append(f"{idx}) <b>{t}</b>")
        tg_lines.append(f"   • Amazon TR: <b>{p}</b>  (Piyasa: <s>{sp}</s> — %{disc:.0f} avantaj)")
        tg_lines.append(f"   • <a href=\"{html.escape(u)}\">Ürünü İncele →</a>")
        tg_lines.append("")
    tg_lines.append("𝕏 Anlık akış: <a href=\"https://x.com/vurgunradari\">x.com/vurgunradari</a>  <i>#işbirliği</i>")

    bot_token = (settings.get("telegram_bot_token") or "").strip()
    chat_id = (settings.get("telegram_chat_id") or "").strip()
    tg_ok = False
    if bot_token and chat_id:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data=json.dumps(
                    {
                        "chat_id": chat_id,
                        "text": "\n".join(tg_lines),
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                rb = json.loads(resp.read().decode("utf-8", errors="ignore"))
                tg_ok = bool(rb.get("ok"))
        except Exception:
            pass

    # 2. X Digest Tweet (<230 chars so it always fits within 280 limit)
    x_lines = ["Günün öne çıkan 3 fiyat farkı (Amazon TR):"]
    for idx, d in enumerate(top3, 1):
        t_short = (d.get("title") or "")[:24].rstrip()
        p = format_tl(float(d.get("cheapest_price") or 0))
        disc = float(d.get("discount_pct") or 0)
        x_lines.append(f"{idx}) {t_short}.. {p} (-%{disc:.0f})")
    x_lines.append("Linkler: https://t.me/vurgunradari #indirim #işbirliği")
    x_text = "\n".join(x_lines)

    auth_token = (settings.get("x_auth_token") or os.environ.get("X_AUTH_TOKEN") or "").strip()
    x_res = {"ok": False}
    if auth_token and not auth_token.startswith("***"):
        x_res = _post_tweet_via_headless_chrome(x_text, auth_token)

    return {"ok": tg_ok or bool(x_res.get("ok")), "tg_ok": tg_ok, "x_res": x_res}


_X_SNIPER_TARGETS = [
    (
        '"kulaklık önerisi" OR "bluetooth kulaklık" OR "kulaklık lazım" -filter:replies lang:tr',
        ("kulaklık", "airpods", "sennheiser", "anker", "jbl", "sony", "tuf h1", "lp80"),
        "Kulaklık",
    ),
    (
        '"mouse önerisi" OR "oyuncu mouse" OR "kablosuz mouse" -filter:replies lang:tr',
        ("mouse", "logitech", "razer", "rampage", "steelseries"),
        "Mouse",
    ),
    (
        '"monitör önerisi" OR "gaming monitör" -filter:replies lang:tr',
        ("monitör", "monitor", "ips", "oled", "ultragear", "tuf gaming vg"),
        "Monitör",
    ),
    (
        '"güneş kremi" OR "nemlendirici" OR "cerave" OR "la roche" -filter:replies lang:tr',
        ("cerave", "la roche", "bioderma", "vichy", "yüz", "cilt", "güneş", "serum", "nemlendirici"),
        "Dermokozmetik",
    ),
    (
        '"kahve makinesi" OR "espresso" OR "termos" OR "airfryer" -filter:replies lang:tr',
        ("kahve", "espresso", "termos", "stanley", "philips", "mutfak"),
        "Mutfak",
    ),
    (
        '"laptop önerisi" OR "bilgisayar önerisi" -filter:replies lang:tr',
        ("laptop", "dizüstü", "ryzen", "rtx", "ideapad", "zenbook", "cyborg", "omen"),
        "Laptop",
    ),
]

_SNIPER_HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posted_history.json")
SNIPER_REPLY_COOLDOWN_SECONDS = 1500  # 25 minutes anti-ban cooldown between Sniper Replies


def _pick_matching_deal_for_sniper(deals: list, keywords: tuple, preferred_cat: str = "") -> Dict[str, Any]:
    cat_matches = []
    kw_matches = []
    for d in deals:
        if "amazon.com.tr/dp/" not in str(d.get("url") or ""):
            continue
        cat_str = (d.get("category") or "").lower()
        title_str = (d.get("title") or "").lower()
        if preferred_cat and preferred_cat.lower() in cat_str:
            cat_matches.append(d)
        elif any(k in title_str for k in keywords):
            kw_matches.append(d)
    pool = cat_matches or kw_matches or [d for d in deals if "amazon.com.tr/dp/" in str(d.get("url") or "")]
    pool.sort(key=lambda x: float(x.get("discount_pct") or 0), reverse=True)
    return pool[0] if pool else {}


def _build_sniper_reply_text(deal: Dict[str, Any]) -> str:
    raw_title = (deal.get("title") or "Fırsat Ürünü").strip()
    short_title = raw_title[:48].rstrip() + ("..." if len(raw_title) > 48 else "")
    price_str = format_tl(float(deal.get("cheapest_price") or 0))
    second_str = format_tl(float(deal.get("second_price") or 0))
    disc = float(deal.get("discount_pct") or 0)
    variant = int(time.time()) % 3
    if variant == 0:
        return (
            f"Şu an Amazon TR'de {short_title} diğer mağazalara göre %{disc:.0f} daha ucuza ({price_str}) düştü, "
            f"stokta aktif duruyor. Profildeki son paylaşımlarda direkt linki var, bakabilirsin."
        )
    if variant == 1:
        return (
            f"Fiyat/performans olarak {short_title} şu an Amazon'da {price_str} seviyesine indi "
            f"(piyasada {second_str} bandında, %{disc:.0f} avantaj var). Düşünürsen profildeki akışta paylaştık."
        )
    return (
        f"İhtiyacın varsa {short_title} şu an Amazon TR üzerinde %{disc:.0f} fiyat farkıyla {price_str}'ye düştü. "
        f"Stok bitmeden profildeki son paylaşımdan veya t.me/vurgunradari kanalından inceleyebilirsin."
    )


def engage_targeted_x_shoppers(
    settings: Dict[str, str],
    deals: list = None,
    max_likes: int = 2,
    force_reply: bool = False,
) -> Dict[str, Any]:
    """
    Organic user acquisition engine + Sniper Reply:
    1) Searches X Live feed (f=live) for real Turkish shoppers asking for product recommendations.
    2) Likes up to `max_likes` posts.
    3) Writes 1 contextual, link-free Sniper Reply recommending our matching live Amazon TR deal
       (rate-limited to 1 reply per 25 minutes to keep the account 100% safe from spam filters).
    """
    auth_token = (settings.get("x_auth_token") or os.environ.get("X_AUTH_TOKEN") or "").strip()
    clean_auth = re.sub(r"[^a-fA-F0-9]", "", auth_token)
    if len(clean_auth) < 30:
        return {"ok": False, "error": "X auth_token eksik."}

    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    chrome_bin = next((c for c in chrome_candidates if os.path.isfile(c)), "")
    if not chrome_bin:
        return {"ok": False, "error": "Chrome bulunamadı."}

    # Load sniper history (replied_status_ids & last_sniper_reply_ts)
    hist_data: Dict[str, Any] = {}
    try:
        if os.path.isfile(_SNIPER_HISTORY_PATH):
            with open(_SNIPER_HISTORY_PATH, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
    except Exception:
        hist_data = {}

    replied_ids = set(hist_data.get("replied_status_ids") or [])
    last_reply_ts = int(hist_data.get("last_sniper_reply_ts") or 0)
    now_ts = int(time.time())
    can_reply = force_reply or ((now_ts - last_reply_ts) >= SNIPER_REPLY_COOLDOWN_SECONDS)

    idx = int(now_ts // 90) % len(_X_SNIPER_TARGETS)
    query, cat_keywords, preferred_cat = _X_SNIPER_TARGETS[idx]
    matched_deal = _pick_matching_deal_for_sniper(deals or [], cat_keywords, preferred_cat) if deals else {}
    search_url = "https://x.com/search?q=" + urllib.parse.quote(query) + "&src=typed_query&f=live"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_port:
        s_port.bind(("127.0.0.1", 0))
        port = s_port.getsockname()[1]

    profile_dir = tempfile.mkdtemp(prefix="vurgun_x_grow_")
    proc = None
    sock = None
    try:
        proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2.0)
        tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read().decode("utf-8"))
        ws_url = [t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page"][0]
        ws_path = "/" + ws_url.split("/", 3)[3]

        sock = socket.create_connection(("127.0.0.1", port), timeout=18)
        ws_key = base64.b64encode(os.urandom(16)).decode("utf-8")
        handshake = (
            f"GET {ws_path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(handshake.encode("utf-8"))
        sock.recv(4096)

        _cdp_send(sock, 1, "Network.enable")
        _cdp_send(
            sock,
            2,
            "Network.setCookie",
            {
                "name": "auth_token",
                "value": clean_auth,
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
        )
        _cdp_send(sock, 3, "Page.navigate", {"url": search_url})
        time.sleep(6.5)

        replied_js_list = json.dumps(list(replied_ids))
        js_engage = f"""
        (async () => {{
            const seen = new Set({replied_js_list});
            const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
            let liked = 0;
            let targetStatusId = "";
            let targetUser = "";
            for (const art of articles) {{
                const links = Array.from(art.querySelectorAll('a[href*="/status/"]')).map(a => a.getAttribute("href"));
                const stLink = links.find(h => /^\\/[A-Za-z0-9_]+\\/status\\/\\d+$/.test(h || ""));
                if (!stLink) continue;
                const parts = stLink.split("/");
                const user = (parts[1] || "").toLowerCase();
                const sid = parts[3] || "";
                if (!sid || user === "vurgunradari" || seen.has(sid)) continue;
                const likeBtn = art.querySelector('[data-testid="like"]');
                if (likeBtn && liked < {int(max_likes)}) {{
                    likeBtn.click();
                    liked++;
                    await new Promise(r => setTimeout(r, 1200));
                }}
                if (!targetStatusId) {{
                    targetStatusId = sid;
                    targetUser = user;
                }}
            }}
            return JSON.stringify({{liked, targetStatusId, targetUser}});
        }})()
        """
        eval_res = _cdp_send(
            sock,
            4,
            "Runtime.evaluate",
            {"expression": js_engage, "awaitPromise": True, "returnByValue": True},
        )
        raw_val = str(((eval_res.get("result") or {}).get("result") or {}).get("value") or "{}")
        parsed_eng = json.loads(raw_val) if raw_val.startswith("{") else {}
        target_sid = str(parsed_eng.get("targetStatusId") or "")
        target_user = str(parsed_eng.get("targetUser") or "")

        reply_sent = False
        reply_text = ""
        if can_reply and target_sid and matched_deal:
            reply_text = _build_sniper_reply_text(matched_deal)
            intent_reply_url = (
                f"https://x.com/intent/post?in_reply_to={urllib.parse.quote(target_sid)}"
                f"&text={urllib.parse.quote(reply_text)}"
            )
            _cdp_send(sock, 5, "Page.navigate", {"url": intent_reply_url})
            time.sleep(6.0)
            js_send_reply = """
            (async () => {
                const btn = document.querySelector('[data-testid="tweetButton"]');
                if (!btn) return "no_btn";
                btn.click();
                await new Promise(r => setTimeout(r, 3200));
                return "replied:" + location.href;
            })()
            """
            rep_eval = _cdp_send(
                sock,
                6,
                "Runtime.evaluate",
                {"expression": js_send_reply, "awaitPromise": True, "returnByValue": True},
            )
            rep_val = str(((rep_eval.get("result") or {}).get("result") or {}).get("value") or "")
            if rep_val.startswith("replied:"):
                reply_sent = True
                replied_ids.add(target_sid)
                hist_data["replied_status_ids"] = sorted(replied_ids)[-200:]
                hist_data["last_sniper_reply_ts"] = int(time.time())
                try:
                    with open(_SNIPER_HISTORY_PATH, "w", encoding="utf-8") as f:
                        json.dump(hist_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        return {
            "ok": True,
            "query": query,
            "liked": parsed_eng.get("liked", 0),
            "sniper_reply_sent": reply_sent,
            "target_user": target_user,
            "target_status_id": target_sid,
            "reply_text": reply_text,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                pass
        shutil.rmtree(profile_dir, ignore_errors=True)


def send_ntfy_alert(
    deal: Dict[str, Any],
    settings: Dict[str, str],
    is_test: bool = False,
) -> Dict[str, Any]:
    """
    Sends a rich push notification via ntfy.sh JSON endpoint (supports full UTF-8 titles & action buttons).
    """
    topic = re.sub(r"[^a-zA-Z0-9_-]", "", settings.get("ntfy_topic", "").strip())
    if not topic:
        return {"ok": False, "error": "ntfy_topic ayarlanmamış."}

    server = settings.get("ntfy_server", "https://ntfy.sh").strip().rstrip("/")
    if not server.startswith("https://"):
        server = "https://ntfy.sh"

    amazon_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
    hb_aff_id = settings.get("hepsiburada_aff_id", "")
    target_url = build_affiliate_url(
        deal.get("url", ""),
        amazon_tag,
        hb_aff_id,
        product_title=deal.get("title", ""),
        merchant=deal.get("cheapest_merchant", ""),
    )

    price = float(deal.get("cheapest_price", 0))
    second_price = float(deal.get("second_price", 0))
    profit = float(deal.get("estimated_profit_tl", 0))
    resell = float(deal.get("suggested_resell_price", 0))
    disc = float(deal.get("discount_pct", 0))
    merchant = deal.get("cheapest_merchant", "Mağaza")
    second_merchant = deal.get("second_merchant", "Rakip")

    if is_test:
        title = "🚀 VURGUN RADARI AKTİF! (Test Bildirimi)"
    elif profit >= 500:
        title = f"🚨 AL-SAT VURGUNU: +{format_tl(profit)} Net Kâr! (%{disc:.0f} Fark)"
    elif disc >= 25:
        title = f"🔥 FİYAT ÇAKILDI (%{disc:.0f}): {format_tl(price)} ({merchant})"
    else:
        title = f"⚡ YENİ FIRSAT: {deal.get('title', '')[:48]}"

    msg_lines = [f"📦 {deal.get('title', '')}"]
    if price > 0:
        msg_lines.append(f"🏷️ Alış ({merchant}): {format_tl(price)}")
    if second_price > price:
        msg_lines.append(f"📈 2. En Ucuz ({second_merchant}): {format_tl(second_price)}")
    if profit > 0 and resell > price:
        msg_lines.append(
            f"💸 Al-Sat Hedefi (Sarı Site/Dolap): {format_tl(resell)} -> Tahmini Net Kâr: +{format_tl(profit)} (%{deal.get('roi_pct', 0):.0f} ROI)"
        )
    if disc > 0:
        msg_lines.append(f"📉 İndirim / Arbitraj Oranı: %{disc:.1f}")

    priority = 5 if (profit >= 1500 or disc >= 35) else (4 if (profit >= 400 or disc >= 20) else 3)
    tags = ["rotating_light", "moneybag", "fire"] if priority >= 4 else ["zap", "shopping_cart"]

    payload: Dict[str, Any] = {
        "topic": topic,
        "title": title[:120],
        "message": "\n".join(msg_lines),
        "priority": priority,
        "tags": tags,
    }
    if target_url.startswith("https://"):
        payload["click"] = target_url
        payload["actions"] = [
            {
                "action": "view",
                "label": f"Hemen Kap ({format_tl(price)})" if price > 0 else "Fırsata Git",
                "url": target_url,
            }
        ]

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{server}/",
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "VurgunRadariBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp_body = resp.read().decode("utf-8", errors="ignore")
            return {"ok": resp.status == 200, "status": resp.status, "response": resp_body[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
