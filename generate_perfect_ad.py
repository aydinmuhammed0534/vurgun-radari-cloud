import math
import os
import random
import re
import shutil
import subprocess
import textwrap
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

base_dir = os.path.dirname(os.path.abspath(__file__))


def load_font(font_type="bold", size=60):
    """Loads universal cross-platform font supporting both macOS and Ubuntu Linux."""
    candidates = []
    if font_type == "condensed":
        candidates = [
            os.path.join(base_dir, "static", "fonts", "DIN_Condensed_Bold.ttf"),
            "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
            "/System/Library/Fonts/Avenir Next Condensed.ttc",
            os.path.join(base_dir, "static", "fonts", "Roboto-Bold.ttf"),
        ]
    elif font_type == "bold":
        candidates = [
            os.path.join(base_dir, "static", "fonts", "Roboto-Bold.ttf"),
            "/System/Library/Fonts/Avenir Next.ttc",
        ]
    else:
        candidates = [
            os.path.join(base_dir, "static", "fonts", "Roboto-Regular.ttf"),
            "/System/Library/Fonts/Avenir Next.ttc",
        ]

    for c in candidates:
        if os.path.isfile(c):
            try:
                idx = 0
                if "Avenir Next Condensed" in c:
                    idx = 8
                elif "Avenir Next.ttc" in c:
                    idx = 2 if font_type == "bold" else 0
                return ImageFont.truetype(c, size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


def fit_font(draw, text, font_type, max_width, initial_size, min_size=28):
    """Dynamically scales down font size until text strictly fits within max_width."""
    size = initial_size
    while size >= min_size:
        f = load_font(font_type, size)
        box = draw.textbbox((0, 0), text, font=f)
        w = box[2] - box[0]
        if w <= max_width:
            return f, size, w, box[3] - box[1]
        size -= 2
    f = load_font(font_type, min_size)
    box = draw.textbbox((0, 0), text, font=f)
    return f, min_size, box[2] - box[0], box[3] - box[1]


def draw_star(draw, center_x, center_y, size=21, color=(255, 164, 28)):
    points = []
    for i in range(10):
        r = size if i % 2 == 0 else size / 2.2
        angle = i * math.pi / 5 - math.pi / 2
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=color)


def generate_deal_story(
    deal_title="Fırsat Ürünü",
    deal_price=990.0,
    market_price=1875.0,
    discount_pct=47,
    product_image_path=None,
    output_png="static/dedekto_deal_story.png",
    output_mp4="static/dedekto_deal_reels.mp4"
):
    W, H = 2160, 3840

    deal_price = float(deal_price or 0.0)
    market_price = float(market_price or 0.0)
    if market_price <= deal_price:
        market_price = round(deal_price * 1.30, 2)
    if discount_pct <= 0:
        discount_pct = round(((market_price - deal_price) / market_price) * 100, 1)

    # 1. Warm Terracotta / Orange Ambient Gradient (User's preferred vibrant background)
    bg = Image.new("RGB", (W, H))
    bg_draw = ImageDraw.Draw(bg)

    top_color = (216, 75, 30)
    mid_color = (235, 105, 45)
    bot_color = (150, 42, 18)

    for y in range(H):
        t = y / H
        if t < 0.40:
            f = t / 0.40
            r = int(top_color[0] + (mid_color[0] - top_color[0]) * f)
            g = int(top_color[1] + (mid_color[1] - top_color[1]) * f)
            b = int(top_color[2] + (mid_color[2] - top_color[2]) * f)
        else:
            f = (t - 0.40) / 0.60
            r = int(mid_color[0] + (bot_color[0] - mid_color[0]) * f)
            g = int(mid_color[1] + (bot_color[1] - mid_color[1]) * f)
            b = int(mid_color[2] + (bot_color[2] - bot_color[2]) * f)
        bg_draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Center soft ambient spotlight
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([(W // 2 - 950, 400), (W // 2 + 950, 2600)], fill=(255, 185, 110, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(280))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow)
    draw = ImageDraw.Draw(bg)

    # 2. Top Header Pill: "VURGUN RADARI • GÜNÜN FIRSATI"
    font_top = load_font("regular", 54)
    top_txt = "VURGUN RADARI  •  GÜNÜN FIRSATI"
    tpb = draw.textbbox((0, 0), top_txt, font=font_top)
    tpw, tph = tpb[2] - tpb[0], tpb[3] - tpb[1]
    tp_pad_x, tp_pad_y = 52, 18
    tp_w, tp_h = tpw + tp_pad_x * 2, tph + tp_pad_y * 2
    tp_x = (W - tp_w) // 2
    tp_y = 150

    top_pill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tp_draw = ImageDraw.Draw(top_pill)
    tp_draw.rounded_rectangle(
        [(tp_x, tp_y), (tp_x + tp_w, tp_y + tp_h)],
        radius=tp_h // 2,
        fill=(255, 255, 255, 45),
        outline=(255, 255, 255, 160),
        width=4
    )
    tp_draw.text((tp_x + tp_pad_x, tp_y + tp_pad_y - 2), top_txt, fill=(255, 255, 255), font=font_top)
    bg = Image.alpha_composite(bg, top_pill)
    draw = ImageDraw.Draw(bg)

    # 3. Authentic Amazon Mobile App Screenshot Card (1920px wide)
    card_w = 1920
    card_h = 2650
    card_x = (W - card_w) // 2
    card_y = 330
    card_rad = 54

    # 3D Soft Drop Shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle(
        [(card_x - 10, card_y + 30), (card_x + card_w + 10, card_y + card_h + 40)],
        radius=card_rad + 10,
        fill=(40, 10, 5, 160)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(60))
    bg = Image.alpha_composite(bg, shadow)

    # Card base: Pure Amazon Mobile App White
    amz_card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    c_draw = ImageDraw.Draw(amz_card)

    # 3A. Header Bar inside Card
    font_amz_brand = load_font("bold", 62)
    font_prime = load_font("bold", 46)

    # amazon.com.tr
    c_draw.text((80, 65), "amazon.com.tr", fill=(19, 25, 33), font=font_amz_brand)

    # Prime cyan badge
    prime_w, prime_h = 210, 62
    prime_x = card_w - 80 - prime_w
    prime_y = 66
    c_draw.rounded_rectangle([(prime_x, prime_y), (prime_x + prime_w, prime_y + prime_h)], radius=14, fill=(0, 168, 225))
    c_draw.text((prime_x + 36, prime_y + 8), "prime", fill=(255, 255, 255), font=font_prime)

    # Clean divider
    c_draw.line([(80, 155), (card_w - 80, 155)], fill=(234, 237, 240), width=3)

    # 3B. Real Product Photo (Direct from link - Huge & Crisp!)
    photo_box_h = 1180
    photo_box_w = card_w - 160
    if product_image_path and os.path.exists(product_image_path):
        p_img = Image.open(product_image_path).convert("RGBA")
        p_img.thumbnail((photo_box_w, photo_box_h), Image.Resampling.LANCZOS)
        pw, ph = p_img.size
        px = (card_w - pw) // 2
        py = 185 + (photo_box_h - ph) // 2
        amz_card.paste(p_img, (px, py), p_img if p_img.mode == "RGBA" else None)

    # Divider below photo
    c_draw.line([(80, 1400), (card_w - 80, 1400)], fill=(240, 242, 245), width=3)

    # 3C. Product Title (Properly wrapped without cutoffs or overlaps)
    font_prod_title = load_font("bold", 64)
    clean_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', deal_title).strip()
    if len(clean_title) > 75:
        clean_title = clean_title[:75].rsplit(' ', 1)[0]

    title_lines = textwrap.wrap(clean_title, width=38)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]

    curr_title_y = 1435
    for t_line in title_lines:
        c_draw.text((80, curr_title_y), t_line, fill=(15, 20, 25), font=font_prod_title)
        curr_title_y += 76

    # 3D. 5 Stars (Drawn cleanly with PIL) + Rating
    star_start_x = 100
    star_y = curr_title_y + 40
    for s_idx in range(5):
        draw_star(c_draw, star_start_x + s_idx * 50, star_y, size=21, color=(255, 164, 28))

    font_rev = load_font("regular", 46)
    c_draw.text((star_start_x + 5 * 50 + 26, star_y - 23), "4.8 (1.942 değerlendirme)", fill=(0, 113, 133), font=font_rev)

    # 3E. Amazon Price Box
    box_y = star_y + 60

    # Red Amazon Deal Pill: "-%XX Fırsat"
    deal_pill_txt = f"- %{int(discount_pct)} Fırsat"
    font_deal_pill = load_font("bold", 62)
    dpb = c_draw.textbbox((0, 0), deal_pill_txt, font=font_deal_pill)
    dpw, dph = dpb[2] - dpb[0], dpb[3] - dpb[1]
    c_draw.rounded_rectangle([(80, box_y), (80 + dpw + 40, box_y + dph + 24)], radius=12, fill=(204, 12, 57))
    c_draw.text((100, box_y + 11), deal_pill_txt, fill=(255, 255, 255), font=font_deal_pill)

    # Super Bold Amazon Deal Price: 5.879 TL
    price_y = box_y + dph + 44
    font_price_main = load_font("condensed", 240)

    price_val = float(deal_price)
    if price_val >= 10000 or price_val == int(price_val):
        price_str = f"{int(price_val):,} TL".replace(',', '.')
    else:
        price_str = f"{price_val:,.2f} TL".replace(',', 'X').replace('.', ',').replace('X', '.')

    c_draw.text((80, price_y), price_str, fill=(15, 17, 17), font=font_price_main)

    # Strikethrough Market Price: "Tavsiye Edilen Fiyat: 7.290 TL"
    m_price_val = float(market_price)
    strike_label = "Tavsiye Edilen Satış Fiyatı: "
    strike_price = f"{int(m_price_val):,} TL".replace(',', '.')
    font_strike = load_font("regular", 54)
    font_strike_bold = load_font("bold", 54)

    sl_b = c_draw.textbbox((0, 0), strike_label, font=font_strike)
    sl_w = sl_b[2] - sl_b[0]
    sp_b = c_draw.textbbox((0, 0), strike_price, font=font_strike_bold)
    sp_w, sp_h = sp_b[2] - sp_b[0], sp_b[3] - sp_b[1]

    strike_y = price_y + 245
    c_draw.text((80, strike_y), strike_label, fill=(86, 89, 89), font=font_strike)
    c_draw.text((80 + sl_w, strike_y), strike_price, fill=(86, 89, 89), font=font_strike_bold)

    # Clean red horizontal line crossing out the price value
    c_draw.line([(80 + sl_w - 6, strike_y + sp_h // 2 + 2), (80 + sl_w + sp_w + 6, strike_y + sp_h // 2 + 2)], fill=(204, 12, 57), width=6)

    # Green Delivery badge
    font_stock = load_font("bold", 52)
    font_seller = load_font("regular", 46)
    stock_y = strike_y + sp_h + 40
    c_draw.text((80, stock_y), "Stokta Var • Ücretsiz Hızlı Kargo", fill=(0, 118, 0), font=font_stock)
    c_draw.text((80, stock_y + 60), "Gönderici ve Satıcı: Amazon.com.tr", fill=(86, 89, 89), font=font_seller)

    # Apply card mask
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (card_w, card_h)], radius=card_rad, fill=255)
    bg.paste(amz_card, (card_x, card_y), mask)
    draw = ImageDraw.Draw(bg)

    # 4. Bottom Area (Previous template clean white button)
    font_btn = load_font("bold", 82)
    btn_txt = "Fırsatı Yakala"
    bb = draw.textbbox((0, 0), btn_txt, font=font_btn)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    btn_w = bw + 240
    btn_h = bh + 96
    btn_x = (W - btn_w) // 2
    btn_y = card_y + card_h + 120
    btn_rad = btn_h // 2

    # Button shadow
    btn_shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bs_draw = ImageDraw.Draw(btn_shadow)
    bs_draw.rounded_rectangle([(btn_x, btn_y + 16), (btn_x + btn_w, btn_y + btn_h + 16)], radius=btn_rad, fill=(40, 10, 5, 120))
    btn_shadow = btn_shadow.filter(ImageFilter.GaussianBlur(30))
    bg = Image.alpha_composite(bg, btn_shadow)
    draw = ImageDraw.Draw(bg)

    # White button
    draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=btn_rad, fill=(255, 255, 255))
    draw.text(((W - bw) // 2, btn_y + (btn_h - bh) // 2 - 6), btn_txt, fill=(20, 20, 20), font=font_btn)

    # 5. Subtle Footer Branding
    font_footer = load_font("regular", 50)
    foot_txt = "Amazon TR  •  @vurgunradari  •  Link Hikayede & Bio'da"
    fb = draw.textbbox((0, 0), foot_txt, font=font_footer)
    fw, fh = fb[2] - fb[0], fb[3] - fb[1]
    draw.text(((W - fw) // 2, btn_y + btn_h + 75), foot_txt, fill=(255, 255, 255, 230), font=font_footer)

    # 6. Downsample with Lanczos for razor-sharp 1080x1920 output
    final = bg.convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)
    final.save(output_png, quality=98)
    print(f"Generated Amazon Screenshot deal story: {output_png}")

    # 7. Generate high quality 30fps Reels video with background music and Ken Burns subtle zoom
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not os.path.exists(ffmpeg_bin) and os.path.exists("/usr/bin/ffmpeg"):
        ffmpeg_bin = "/usr/bin/ffmpeg"

    audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "audio")
    audio_files = []
    if os.path.isdir(audio_dir):
        audio_files = [os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.lower().endswith((".mp3", ".wav", ".m4a"))]

    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1", "-i", output_png
    ]

    if audio_files:
        chosen_audio = random.choice(audio_files)
        start_sec = random.randint(5, 20)
        cmd.extend([
            "-ss", str(start_sec), "-t", "6", "-i", chosen_audio,
            "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.0006,1.05)':d=180:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30",
            "-af", "afade=t=in:ss=0:d=0.4,afade=t=out:st=5.2:d=0.8",
            "-t", "6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k"
        ])
    else:
        cmd.extend([
            "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.0006,1.05)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30",
            "-t", "5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18"
        ])

    os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
    cmd.append(output_mp4)
    subprocess.run(cmd, check=True)
    print(f"Generated perfect reels video with music: {output_mp4}")


def resolve_and_download_image(deal):
    """Dynamically resolves and downloads the exact high-res product photo for any deal."""
    deal_id = str(deal.get("id", "deal"))
    local_cache = f"static/deals/{deal_id}_thumb.jpg"
    if os.path.exists(local_cache) and os.path.getsize(local_cache) > 2000:
        return local_cache

    img_raw = str(deal.get("image_url") or "").strip()
    if img_raw and os.path.isfile(img_raw) and os.path.getsize(img_raw) > 2000:
        return img_raw

    candidates = []
    # 1. Direct deal image_url if HTTP(S)
    if img_raw.startswith("http"):
        candidates.append(img_raw)

    # 2. Cimri CDN image by ID
    num = re.sub(r"\D", "", deal_id)
    if num:
        candidates.append(f"https://cdn.cimri.io/image/1000x1000/product_{num}.jpg")
        candidates.append(f"https://cdn.cimri.io/image/500x500/product_{num}.jpg")

    # 3. Amazon ASIN image from page
    raw_url = str(deal.get("url") or "")
    m_asin = re.search(r"B0[A-Z0-9]{8}", raw_url + deal_id)
    if m_asin:
        asin = m_asin.group(0)
        try:
            amz_url = f"https://www.amazon.com.tr/dp/{asin}"
            req = urllib.request.Request(amz_url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                img_m = (
                    re.search(r'data-old-hires="(https://[^"]+)"', html)
                    or re.search(r'"large":"(https://[^"]+)"', html)
                    or re.search(r'data-a-dynamic-image="{&quot;(https://[^&]+)&quot;', html)
                    or re.search(r'id="landingImage"[^>]+src="(https://[^"]+)"', html)
                )
                if img_m:
                    candidates.append(re.sub(r'\._[^.]+\.', '.', img_m.group(1)))
        except Exception:
            pass

    for cand in candidates:
        if not cand.startswith("http"):
            continue
        try:
            req = urllib.request.Request(cand, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
                if len(data) > 2500:
                    with open(local_cache, "wb") as f:
                        f.write(data)
                    return local_cache
        except Exception:
            continue

    return None


def generate_for_deal(deal):
    """Generates Story PNG and Reels MP4 for any deal dictionary with real product photo and music."""
    os.makedirs("static/deals", exist_ok=True)
    deal_id = deal.get("id", "deal")
    out_png = f"static/deals/{deal_id}_story.png"
    out_mp4 = f"static/deals/{deal_id}_reels.mp4"

    real_img = resolve_and_download_image(deal)

    generate_deal_story(
        deal_title=deal.get("title", "Fırsat Ürünü"),
        deal_price=float(deal.get("cheapest_price", 0)),
        market_price=float(deal.get("second_price") or deal.get("reference_price") or 0),
        discount_pct=float(deal.get("discount_pct", 30)),
        product_image_path=real_img,
        output_png=out_png,
        output_mp4=out_mp4
    )
    return out_png, out_mp4


if __name__ == "__main__":
    generate_deal_story()
