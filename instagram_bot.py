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
        "beyler amazon fiyatı resmen dibe çekmiş şaka gibi indirim var",
        "fena patlatmışlar normalde bu fiyata imkanı yok bulamazsınız",
        "böyle bir fiyat hatası yok ihtiyacı olan hiç beklemesin direkt çöksün",
        f"normalde {old_price:,} TL olan ürün şu an {price:,} TL'ye düşmüş bedavadan biraz pahalı".replace(',', '.'),
        f"stokları eritmeye çalışıyorlar herhalde fiyata gel (%{disc} indirim)"
    ]
    hook = random.choice(hooks)

    lines = [
        f"{hook}\n",
        f"📦 Ürün: {title}",
        f"🏷 Piyasa Fiyatı: {old_price:,} TL".replace(',', '.'),
        f"🔥 Vurgun Fiyatı: {price:,} TL (%{disc} İndirim)\n".replace(',', '.'),
        "👉 Satın alma linki biyografideki Telegram kanalımızda sabitlendi! (t.me/vurgunradari)",
        "👉 Hikayedeki link çıkartmasına tıklayarak da direkt Amazon'dan kapabilirsiniz.",
        "⚡️ Fiyat hataları dakikalar içinde düzeliyor, kaçırmamak için takipte kalın!\n",
        "#amazontr #indirim #fırsat #fiyathatası #vurgunradari #indirimhaberi #kampanya"
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


def post_deal_photo(deal: Dict[str, Any], image_path: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Posts a deal screenshot card as a clean, high-converting Photo Post to the Instagram feed."""
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu açılamadı."}

    if not os.path.exists(image_path):
        return {"ok": False, "error": f"Görsel bulunamadı: {image_path}"}

    caption = build_viral_reels_caption(deal, settings)
    try:
        media = cl.photo_upload(image_path, caption=caption)
        logger.info(f"Feed Photo Post uploaded successfully! Media ID: {media.pk}")
        return {"ok": True, "media_id": media.pk, "code": media.code}
    except Exception as e:
        logger.error(f"Feed Photo Post upload error: {e}")
        if "login_required" in str(e).lower():
            global _client_instance
            _client_instance = None
        return {"ok": False, "error": str(e)}


def post_deal_story(deal: Dict[str, Any], image_path: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Posts an image to Instagram Stories with a clickable link sticker."""
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu açılamadı."}

    if not os.path.exists(image_path):
        return {"ok": False, "error": f"Story görseli bulunamadı: {image_path}"}

    links = []
    affiliate_url = str(deal.get("url") or "").strip()
    if affiliate_url.startswith("https://"):
        try:
            from instagrapi.types import StoryLink
            links.append(StoryLink(webUri=affiliate_url))
        except Exception as e:
            logger.warning(f"Failed to create StoryLink: {e}")

    polls = []
    try:
        from instagrapi.types import StoryPoll
        polls.append(
            StoryPoll(
                question="Bu fiyata çökülür mü? 🔥",
                options=[{"text": "Çök 🚀"}, {"text": "Pas ❌"}],
                x=0.5,
                y=0.88,
                width=0.55,
                height=0.10,
            )
        )
    except Exception as pe:
        logger.debug(f"Poll sticker notice: {pe}")

    try:
        kwargs = {}
        if links:
            kwargs["links"] = links
        if polls:
            kwargs["polls"] = polls
        media = cl.photo_upload_to_story(image_path, **kwargs)
        logger.info(f"Story uploaded successfully with link + poll sticker! Media ID: {media.pk}")

        # Automatically add story to "⚡️ Sıcak Fırsatlar" Highlight
        try:
            highlights = cl.user_highlights(cl.user_id)
            target_hl = next((h for h in highlights if "Fırsat" in h.title or "Dip" in h.title), None)
            if target_hl:
                cl.highlight_change_reel(target_hl.pk, added_media_ids=[media.pk])
            else:
                cl.highlight_create("⚡️ Sıcak Fırsatlar", [media.pk])
        except Exception as he:
            logger.debug(f"Highlight sync notice: {he}")

        return {"ok": True, "media_id": media.pk}
    except Exception as e:
        logger.error(f"Story upload error: {e}")
        # Fallback without polls
        if links:
            try:
                media = cl.photo_upload_to_story(image_path, links=links)
                return {"ok": True, "media_id": media.pk}
            except Exception:
                pass
        try:
            media = cl.photo_upload_to_story(image_path)
            return {"ok": True, "media_id": media.pk}
        except Exception:
            pass
        if "login_required" in str(e).lower():
            _client_instance = None
        return {"ok": False, "error": str(e)}


GROWTH_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static", "ig_growth_state.json"
)

TARGET_DEAL_HUBS = [
    {"username": "amazon.tr", "id": "33196416662"},
    {"username": "firsatcik", "id": "54790762935"},
    {"username": "firsatatikla", "id": "45546466216"},
    {"username": "webtekno", "id": "985715137"},
    {"username": "hepsiburada", "id": "206233365"},
    {"username": "trendyolcom", "id": "224957037"},
    {"username": "firsatnobeti", "id": "31857454955"},
]


def _load_growth_state() -> Dict[str, Any]:
    if os.path.exists(GROWTH_STATE_FILE):
        try:
            with open(GROWTH_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read growth state: {e}")
    return {"engaged_users": {}, "daily_stats": {}, "last_run_ts": 0}


def _save_growth_state(state: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(GROWTH_STATE_FILE), exist_ok=True)
        with open(GROWTH_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save growth state: {e}")


def run_targeted_growth_loop(
    settings: Dict[str, str],
    max_follows: int = 6,
    max_likes: int = 6,
    cooldown_seconds: int = 300,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Safely and aggressively acquires high-intent Turkish shoppers from major deal & Amazon pages.
    Drives profile visits, story views, and affiliate conversions with human-jitter delays & anti-ban caps.
    """
    cl = get_instagram_client(settings)
    if not cl:
        return {"ok": False, "error": "Instagram oturumu aktif değil."}

    now = int(time.time())
    today_key = time.strftime("%Y-%m-%d")
    state = _load_growth_state()

    # 1. Cooldown check
    last_run = int(state.get("last_run_ts", 0))
    if not force and (now - last_run < cooldown_seconds):
        return {
            "ok": True,
            "status": "cooling_down",
            "seconds_remaining": cooldown_seconds - (now - last_run),
        }

    daily = state.setdefault("daily_stats", {}).setdefault(
        today_key, {"follows": 0, "likes": 0, "unfollows": 0}
    )

    # 2. Strict 24h anti-ban limits (calibrated for high-velocity safe growth)
    DAILY_MAX_FOLLOWS = 140
    DAILY_MAX_LIKES = 150
    DAILY_MAX_STORY_LIKES = 150

    daily.setdefault("story_likes", 0)
    if daily["follows"] >= DAILY_MAX_FOLLOWS and daily["likes"] >= DAILY_MAX_LIKES:
        logger.info(f"Daily Instagram action limit reached for {today_key}. Resting.")
        return {"ok": True, "status": "daily_limit_reached", "daily_stats": daily}

    # 3. Select target hub
    target = random.choice(TARGET_DEAL_HUBS)
    logger.info(f"Sniping live online shoppers from @{target['username']}...")

    followed_list = []
    liked_list = []
    story_liked_list = []
    unfollowed_list = []

    candidates = []
    # Strategy A: Sniping LIVE ONLINE LIKERS of the latest post (people currently holding their phone)
    try:
        medias = cl.user_medias(target["id"], amount=1)
        if medias:
            likers = cl.media_likers(medias[0].id)
            if likers:
                candidates = likers[:25]
                logger.info(f"Found {len(candidates)} live online likers on @{target['username']} latest post!")
    except Exception as me:
        logger.debug(f"Media liker fetch fallback: {me}")

    # Strategy B: Fallback to fresh followers of the hub
    if not candidates:
        try:
            f_dict = cl.user_followers(target["id"], amount=20)
            candidates = list(f_dict.values())
        except Exception as fe:
            logger.error(f"Failed to fetch audience from @{target['username']}: {fe}")
            return {"ok": False, "error": str(fe)}

    engaged = state.setdefault("engaged_users", {})

    # 4. Triple-Touchpoint Engagement Cycle
    for u in candidates:
        if len(followed_list) >= max_follows and len(liked_list) >= max_likes:
            break

        pk = u.pk
        pk_str = str(pk)
        if pk_str in engaged:
            continue

        if str(cl.user_id) == pk_str:
            continue

        followed_this = False
        story_liked_this = False
        liked_this = False

        # Touchpoint 1: Follow
        if len(followed_list) < max_follows and daily["follows"] < DAILY_MAX_FOLLOWS:
            try:
                ok = cl.user_follow(pk)
                if ok:
                    followed_list.append(u.username)
                    daily["follows"] += 1
                    followed_this = True
                    logger.info(f"Followed live shopper @{u.username} (Today: {daily['follows']}/{DAILY_MAX_FOLLOWS})")
                    time.sleep(random.uniform(5.0, 9.0))
            except Exception as fe:
                logger.warning(f"Follow error on @{u.username}: {fe}")
                if "feedback_required" in str(fe).lower() or "challenge_required" in str(fe).lower():
                    logger.error("Instagram safety barrier hit. Halting growth loop.")
                    break

        # Touchpoint 2: Story Sniper (View + Like active 24h story -> instant red heart DM notification!)
        if daily["story_likes"] < DAILY_MAX_STORY_LIKES:
            try:
                user_stories = cl.user_stories(pk)
                if user_stories:
                    st = user_stories[0]
                    cl.story_seen([st.pk])
                    cl.story_like(st.id)
                    daily["story_likes"] += 1
                    story_liked_this = True
                    story_liked_list.append(u.username)
                    logger.info(f"Liked active story of @{u.username}! ❤️")
                    time.sleep(random.uniform(4.0, 7.0))
            except Exception:
                pass

        # Touchpoint 3: Post Like (if public, likes their recent photo)
        if not getattr(u, "is_private", False) and len(liked_list) < max_likes and daily["likes"] < DAILY_MAX_LIKES:
            try:
                user_medias = cl.user_medias(pk, amount=1)
                if user_medias:
                    m = user_medias[0]
                    cl.media_like(m.id)
                    liked_list.append(u.username)
                    daily["likes"] += 1
                    liked_this = True
                    logger.info(f"Liked post of @{u.username} (Total likes today: {daily['likes']})")
                    time.sleep(random.uniform(4.0, 8.0))
            except Exception as le:
                logger.warning(f"Like error on @{u.username}: {le}")

        if followed_this or story_liked_this or liked_this:
            actions = []
            if followed_this:
                actions.append("follow")
            if story_liked_this:
                actions.append("story_like")
            if liked_this:
                actions.append("post_like")

            engaged[pk_str] = {
                "username": u.username,
                "ts": now,
                "action": "+".join(actions),
                "target_hub": target["username"],
                "unfollowed": False,
            }

    # 4.5 Live Comment Liker Sniper (Likes real active comments on latest hub post)
    comment_liked_list = []
    DAILY_MAX_COMMENT_LIKES = 150
    daily.setdefault("comment_likes", 0)
    if daily["comment_likes"] < DAILY_MAX_COMMENT_LIKES:
        try:
            if medias:
                recent_comments = cl.media_comments(medias[0].id, amount=6)
                for rc in recent_comments:
                    if len(comment_liked_list) >= 4:
                        break
                    rc_pk_str = f"c_{rc.pk}"
                    if rc_pk_str in engaged:
                        continue
                    if str(cl.user_id) == str(rc.user.pk):
                        continue
                    try:
                        ok_c = cl.comment_like(rc.pk)
                        if ok_c:
                            daily["comment_likes"] += 1
                            comment_liked_list.append(rc.user.username)
                            engaged[rc_pk_str] = {"username": rc.user.username, "ts": now, "action": "comment_like"}
                            logger.info(f"Liked comment by @{rc.user.username} on @{target['username']}")
                            time.sleep(random.uniform(2.5, 5.0))
                    except Exception:
                        pass
        except Exception as ce:
            logger.debug(f"Comment liker notice: {ce}")

    # 5. Safe Auto-Unfollow Cleanup (protects follower/following ratio)
    try:
        my_info = cl.user_info(cl.user_id)
        if my_info.following_count > 250:
            three_days_ago = now - (3 * 86400)
            candidates_to_unfollow = [
                (pk, data)
                for pk, data in engaged.items()
                if "follow" in data.get("action", "")
                and not data.get("unfollowed")
                and data.get("ts", 0) < three_days_ago
            ]
            for pk_to_unfollow, data in candidates_to_unfollow[:3]:
                try:
                    cl.user_unfollow(int(pk_to_unfollow))
                    data["unfollowed"] = True
                    unfollowed_list.append(data.get("username", pk_to_unfollow))
                    daily["unfollows"] = daily.get("unfollows", 0) + 1
                    logger.info(f"Unfollowed older non-converted target @{data.get('username')}")
                    time.sleep(random.uniform(6.0, 12.0))
                except Exception as ue:
                    logger.warning(f"Unfollow error: {ue}")
    except Exception as e:
        logger.warning(f"Follow ratio maintenance error: {e}")

    state["last_run_ts"] = now
    _save_growth_state(state)

    return {
        "ok": True,
        "hub": target["username"],
        "followed_count": len(followed_list),
        "followed": followed_list,
        "story_liked_count": len(story_liked_list),
        "story_liked": story_liked_list,
        "liked_count": len(liked_list),
        "liked": liked_list,
        "comment_liked_count": len(comment_liked_list),
        "comment_liked": comment_liked_list,
        "unfollowed": unfollowed_list,
        "today_stats": daily,
    }


def run_organic_growth_loop(settings: Dict[str, str], max_likes: int = 5) -> Dict[str, Any]:
    """Backward compatibility alias for run_targeted_growth_loop."""
    return run_targeted_growth_loop(settings, max_follows=3, max_likes=max_likes)

