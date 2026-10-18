import json
import logging
import os
import random
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("InstagramBot")
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "ig_session.json")

_client_instance = None

def get_instagram_client(settings: Dict[str, str]) -> Optional[Any]:
    """Initializes and authenticates an instagrapi Client."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    try:
        from instagrapi import Client
    except ImportError:
        logger.error("instagrapi is not installed.")
        return None

    cl = Client()
    cl.delay_range = [2, 5]

    import urllib.parse

    # 1. Try loading cached session if present
    sessionid = (settings.get("instagram_sessionid") or "").strip()
    if sessionid:
        sessionid = urllib.parse.unquote(sessionid)

    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cached_sess = cl.settings.get("cookies", {}).get("sessionid") or cl.authorization_data.get("sessionid")
            if cl.user_id and (not sessionid or cached_sess == sessionid):
                logger.info(f"Instagram session restored from cache for user {cl.user_id}.")
                _client_instance = cl
                return cl
        except Exception as e:
            logger.warning(f"Cached session load failed: {e}")

    username = (settings.get("instagram_username") or "").strip().lstrip("@")
    password = (settings.get("instagram_password") or "").strip()

    if not username:
        logger.warning("instagram_username not configured.")
        return None

    try:
        if password:
            logger.info(f"Logging into Instagram as @{username} via mobile device emulation...")
            cl.login(username, password)
        elif sessionid:
            logger.info("Logging into Instagram via sessionid...")
            cl.login_by_sessionid(sessionid)
        else:
            logger.warning("Neither instagram_password nor instagram_sessionid provided.")
            return None

        # Save session for persistent login
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        cl.dump_settings(SESSION_FILE)
        logger.info("Instagram login successful and session saved.")
        _client_instance = cl
        return cl
    except Exception as exc:
        logger.error(f"Instagram login failed: {exc}")
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except Exception:
                pass
        return None


def build_viral_reels_caption(deal: Dict[str, Any], settings: Dict[str, str]) -> str:
    """Creates a natural, street-smart, high-converting Instagram caption without AI cringe."""
    title = deal.get("title", "Fırsat Ürünü")
    price = int(float(deal.get("cheapest_price", 0)))
    old_price = int(float(deal.get("second_price") or deal.get("reference_price") or 0))
    disc = int(float(deal.get("discount_pct", 0)))

    hooks = [
        f"beyler amazon fiyatı resmen yarı yarıya çekmiş şaka gibi indirim var",
        f"fena patlatmışlar normalde bu fiyata imkanı yok bulamazsınız",
        f"böyle bir fiyat hatası yok ihtiyacı olan hiç beklemesin direkt çöksün",
        f"normalde {old_price:,} TL olan ürün şu an {price:,} TL'ye düşmüş bedavadan biraz pahalı".replace(',', '.'),
        f"stokları eritmeye çalışıyorlar herhalde fiyata gel (%{disc} indirim)"
    ]
    hook = random.choice(hooks)

    lines = [
        f"{hook}\n",
        f"ürün: {title}",
        f"piyasa fiyatı: {old_price:,} TL".replace(',', '.'),
        f"fırsat fiyatı: {price:,} TL (%{disc} indirim)\n".replace(',', '.'),
        "yoruma 'link' yazın direkt dm'den atayım beyler 👇",
        "stoklar anında bitiyor haberiniz olsun, kaçırmamak için takipte kalın.\n",
        "#amazontr #indirim #fırsat #fiyathatası #vurgunradari #indirimhaberi"
    ]
    return "\n".join(lines)


def post_deal_reels(deal: Dict[str, Any], video_path: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Posts a video to Instagram Reels."""
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu açılamadı (Kullanıcı adı/şifre veya sessionid gerekli)."}

    if not os.path.exists(video_path):
        return {"ok": False, "error": f"Video dosyası bulunamadı: {video_path}"}

    caption = build_viral_reels_caption(deal, settings)
    thumb_path = video_path.replace(".mp4", ".png")
    if not os.path.exists(thumb_path):
        default_thumb = os.path.join(os.path.dirname(video_path), "dedekto_deal_story.png")
        thumb_path = default_thumb if os.path.exists(default_thumb) else None

    try:
        kwargs = {"caption": caption}
        if thumb_path and os.path.exists(thumb_path):
            kwargs["thumbnail"] = thumb_path
        media = cl.clip_upload(video_path, **kwargs)
        logger.info(f"Reels uploaded successfully! Media ID: {media.pk}")
        return {"ok": True, "media_id": media.pk, "code": media.code}
    except Exception as e:
        logger.error(f"Reels upload error: {e}")
        if "login_required" in str(e).lower():
            global _client_instance
            _client_instance = None
        return {"ok": False, "error": str(e)}


def post_deal_story(deal: Dict[str, Any], image_path: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Posts an image to Instagram Stories."""
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu açılamadı."}

    if not os.path.exists(image_path):
        return {"ok": False, "error": f"Story görseli bulunamadı: {image_path}"}

    try:
        media = cl.photo_upload_to_story(image_path)
        logger.info(f"Story uploaded successfully! Media ID: {media.pk}")
        return {"ok": True, "media_id": media.pk}
    except Exception as e:
        logger.error(f"Story upload error: {e}")
        if "login_required" in str(e).lower():
            _client_instance = None
        return {"ok": False, "error": str(e)}


def run_organic_growth_loop(settings: Dict[str, str], max_likes: int = 5) -> Dict[str, Any]:
    """Safely engages with real Turkish deal/shopper accounts on Instagram to drive followers."""
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu aktif değil."}

    hashtags = ["amazontr", "fırsatürünleri", "fiyathatası", "indirimhaberi", "kulaklık"]
    tag = random.choice(hashtags)
    liked = 0
    try:
        medias = cl.hashtag_medias_recent(tag, amount=max_likes + 2)
        for m in medias:
            if liked >= max_likes:
                break
            try:
                cl.media_like(m.id)
                liked += 1
                time.sleep(random.uniform(3, 8))
            except Exception:
                continue
        return {"ok": True, "tag": tag, "liked_count": liked}
    except Exception as e:
        return {"ok": False, "error": str(e)}
