import base64
import hashlib
import hmac
import html
import json
import re
import secrets
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
    short_title = raw_title[:62].rstrip() + ("..." if len(raw_title) > 62 else "")
    price = float(deal.get("cheapest_price", 0))
    second_price = float(deal.get("second_price", 0))
    disc = float(deal.get("discount_pct", 0))
    merchant = (deal.get("cheapest_merchant") or "Mağaza")[:15]

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
                "Anlık radar: https://t.me/vurgunradari #işbirliği",
            ]
        elif variant == 1:
            lines = [
                f"{short_title} dip fiyata indi.",
                "",
                f"Diğer mağazalarda {format_tl(second_price)} bandında; şu an {merchant} üzerinde {format_tl(price)}.",
                "",
                f"Link: {aff_url}",
                "t.me/vurgunradari #işbirliği",
            ]
        else:
            lines = [
                f"{short_title} — %{disc:.0f} fiyat farkı",
                "",
                f"• Güncel ({merchant}): {format_tl(price)}",
                f"• En yakın rakip: {format_tl(second_price)}",
                "",
                f"{aff_url}",
                "Kanal: https://t.me/vurgunradari #işbirliği",
            ]
    else:
        lines = [
            f"{short_title}",
            "",
            f"{merchant}: {format_tl(price)}" if price > 0 else "Anlık fiyat fırsatı",
            "",
            f"{aff_url}",
            "Anlık radar: https://t.me/vurgunradari #işbirliği",
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


def send_x_auto_tweet(deal: Dict[str, Any], settings: Dict[str, str]) -> Dict[str, Any]:
    """
    Automatically posts a tweet to X (Twitter) using Free Tier API v2 (POST /2/tweets) with OAuth 1.0a.
    """
    api_key = (settings.get("x_api_key") or "").strip()
    api_secret = (settings.get("x_api_secret") or "").strip()
    access_token = (settings.get("x_access_token") or "").strip()
    access_secret = (settings.get("x_access_secret") or "").strip()

    if not (api_key and api_secret and access_token and access_secret):
        return {"ok": False, "error": "X API anahtarları henüz girilmemiş."}

    amazon_tag = settings.get("amazon_affiliate_tag", "vurgunradari-21")
    hb_aff_id = settings.get("hepsiburada_aff_id", "")
    tweet_text = build_x_tweet_text(deal, amazon_tag, hb_aff_id)

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
            "inline_keyboard": [[{"text": btn_label, "url": aff_url}]]
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
