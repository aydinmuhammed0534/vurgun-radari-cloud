import os
import time
import db
import scanner


def main() -> None:
    """
    Headless 7/24 cloud runner for GitHub Actions (runs even when your PC is completely turned off).
    Restores cached deal history, scans Amazon TR Electronics + Cosmetics/Dermocosmetics deals,
    dispatches to Telegram (@vurgunradari), X (Twitter via free web session), and ntfy.sh,
    and runs a real-time sniper loop before caching state.
    """
    db.init_db()
    existing_count = len(db.list_deals())

    env_mapping = {
        "NTFY_TOPIC": "ntfy_topic",
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "TELEGRAM_CHAT_ID": "telegram_chat_id",
        "AMAZON_AFFILIATE_TAG": "amazon_affiliate_tag",
        "X_AUTH_TOKEN": "x_auth_token",
        "X_API_KEY": "x_api_key",
        "X_API_SECRET": "x_api_secret",
        "X_ACCESS_TOKEN": "x_access_token",
        "X_ACCESS_SECRET": "x_access_secret",
        "INSTAGRAM_SESSIONID": "instagram_sessionid",
        "INSTAGRAM_USERNAME": "instagram_username",
    }
    updates = {
        "auto_notify": "1",
        "telegram_auto_post": "1",
        "x_auto_post": "1",
        "instagram_auto_post": "1",
        "telegram_chat_id": "@vurgunradari",
        "instagram_username": "@vurgunradari",
        "amazon_affiliate_tag": "vurgunradari-21",
    }
    for env_key, setting_key in env_mapping.items():
        val = os.environ.get(env_key, "").strip()
        if val:
            updates[setting_key] = val

    db.update_settings(updates)

    if existing_count == 0:
        print("[Cloud Runner] İlk kurulum (soğuk önbellek): Mevcut fırsatlar baz alınıyor...")
        res = scanner.run_full_scan(trigger_notifications=False)
        all_deals = db.list_deals()
        for idx, d in enumerate(all_deals):
            if idx == 0 and os.environ.get("FORCE_FIRST_POST", "0") == "1":
                scanner._dispatch_alerts([d], db.get_settings(), max_alerts=1)
            db.mark_deal_notified(d["id"])
        print(f"[Cloud Runner] Baz tablo oluşturuldu ({len(all_deals)} aktif Amazon TR ürünü). Canlı nöbet başlıyor...")
    else:
        print(f"[Cloud Runner] Önbellek yüklendi ({existing_count} kayıtlı ürün). Tam tarama çalışıyor...")
        res = scanner.run_full_scan(trigger_notifications=True)
        print("[Cloud Runner] Tam tarama sonucu:", res)

    for i in range(sniper_cycles):
        time.sleep(25)
        s_res = scanner.run_sniper_scan(trigger_notifications=True)
        print(f"[Cloud Runner] Sniper döngüsü {i + 1}/{sniper_cycles}:", s_res)

    if os.environ.get("GITHUB_ACTIONS") == "true":
        db.update_settings(
            {
                "telegram_bot_token": "",
                "x_auth_token": "",
                "x_api_key": "",
                "x_api_secret": "",
                "x_access_token": "",
                "x_access_secret": "",
            }
        )


if __name__ == "__main__":
    main()
