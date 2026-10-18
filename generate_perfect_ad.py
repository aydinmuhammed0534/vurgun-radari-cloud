import math
import os
import re
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def load_font(font_type="bold", size=60):
    """Loads universal cross-platform font supporting both macOS and Ubuntu Linux."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
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


def create_product_squircle_card(product_image_path, size=780, radius=180):
    """
    Renders the real product image inside an Apple-style rounded 3D showcase squircle
    with subtle inner border and soft lighting.
    """
    pad = 50
    inner_size = size - pad * 2
    
    # Base pure white squircle
    card = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    
    if product_image_path and os.path.exists(product_image_path):
        p_img = Image.open(product_image_path).convert("RGB")
        # Fit inside inner_size maintaining aspect ratio
        p_img.thumbnail((inner_size, inner_size), Image.Resampling.LANCZOS)
        pw, ph = p_img.size
        # Center inside padded card
        card.paste(p_img, ((size - pw) // 2, (size - ph) // 2))
    
    # Apply squircle mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=255)
    
    final_card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final_card.paste(card, (0, 0), mask)
    
    # Inner rim highlight
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    r_draw = ImageDraw.Draw(rim)
    r_draw.rounded_rectangle([(3, 3), (size - 3, size - 3)], radius=radius - 2, outline=(255, 255, 255, 220), width=6)
    final_card = Image.alpha_composite(final_card, rim)
    
    return final_card


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
    MAX_CONTENT_W = 1860

    # Ensure valid market price
    if market_price <= deal_price:
        market_price = round(deal_price * 1.35, 2)
    if discount_pct <= 0:
        discount_pct = round(((market_price - deal_price) / market_price) * 100, 1)

    savings_amount = max(0, int(market_price - deal_price))

    # 1. Warm Terracotta Ambient Gradient
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

    # Center ambient spotlight behind hero product and price card
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([(W//2 - 950, 400), (W//2 + 950, 2400)], fill=(255, 175, 90, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(280))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow)
    draw = ImageDraw.Draw(bg)

    # 2. Top Header Pill: "VURGUN RADARI • GÜNÜN FIRSATI" (Y = 170)
    font_top = load_font("regular", 54)
    top_txt = "VURGUN RADARI • GÜNÜN FIRSATI"
    tpb = draw.textbbox((0, 0), top_txt, font=font_top)
    tpw, tph = tpb[2] - tpb[0], tpb[3] - tpb[1]
    tp_pad_x, tp_pad_y = 50, 18
    tp_w = tpw + tp_pad_x * 2
    tp_h = tph + tp_pad_y * 2
    tp_x = (W - tp_w) // 2
    tp_y = 170

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

    # 3. Product Showcase Squircle (Y = 320, size = 780)
    card_size = 780
    radius = 180
    ix = (W - card_size) // 2
    iy = 310

    # 3D Soft Drop Shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle(
        [(ix, iy + 40), (ix + card_size, iy + card_size + 40)],
        radius=radius,
        fill=(45, 10, 5, 150)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(60))
    bg = Image.alpha_composite(bg, shadow)

    # Paste the real product showcase card
    prod_card = create_product_squircle_card(product_image_path, size=card_size, radius=radius)
    bg.paste(prod_card, (ix, iy), prod_card)
    draw = ImageDraw.Draw(bg)

    # 4. Clean Product Title (Y = 1140)
    # Clean up excessively noisy titles for the visual showcase
    short_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', deal_title).strip()
    short_title = re.sub(r'(?i)(tüm .*|notebook stant.*|dizüstü.*)', '', short_title).strip()
    if len(short_title) > 55:
        short_title = short_title[:55].rsplit(' ', 1)[0]

    wrapped_lines = textwrap.wrap(short_title, width=28)
    if len(wrapped_lines) > 2:
        wrapped_lines = wrapped_lines[:2]

    prod_y = iy + card_size + 45
    for line in wrapped_lines:
        f_line, _, lw, lh = fit_font(draw, line, "bold", max_width=MAX_CONTENT_W, initial_size=90, min_size=60)
        draw.text(((W - lw)//2, prod_y), line, fill=(255, 255, 255), font=f_line)
        prod_y += lh + 14

    # 5. THE HERO PRICE SHOWCASE CARD (FİYAT VURGUNU ALANI - FRONT & CENTER)
    stage_w = 1920
    stage_x = (W - stage_w) // 2
    stage_y = prod_y + 45
    stage_rad = 80

    inner_y = stage_y + 65

    # 5A. Row 1: Side-by-Side High Contrast Pills
    font_pill_old = load_font("bold", 80)
    old_val_txt = f"Piyasa: {int(market_price):,} TL".replace(',', '.')
    ovb = draw.textbbox((0, 0), old_val_txt, font=font_pill_old)
    ovw, ovh = ovb[2] - ovb[0], ovb[3] - ovb[1]
    old_pill_pad_x, old_pill_pad_y = 52, 22
    old_pill_w = ovw + old_pill_pad_x * 2
    old_pill_h = ovh + old_pill_pad_y * 2

    font_badge = load_font("condensed", 85)
    badge_txt = f"%{int(discount_pct)} İNDİRİM"
    bb = draw.textbbox((0, 0), badge_txt, font=font_badge)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    badge_pad_x, badge_pad_y = 52, 20
    badge_w = bw + badge_pad_x * 2
    badge_h = bh + badge_pad_y * 2

    pill_row_h = max(old_pill_h, badge_h)
    pill_row_gap = 50
    total_pill_row_w = old_pill_w + pill_row_gap + badge_w
    pill_row_x = (W - total_pill_row_w) // 2

    old_pill_x = pill_row_x
    badge_x = old_pill_x + old_pill_w + pill_row_gap
    pill_row_y = inner_y

    # 5B. Divider / "ŞU AN SADECE" Label
    div_y = pill_row_y + pill_row_h + 45
    font_now_label = load_font("regular", 56)
    now_txt = "ŞU AN VURGUN FİYATI"
    nb = draw.textbbox((0, 0), now_txt, font=font_now_label)
    nw, nh = nb[2] - nb[0], nb[3] - nb[1]

    # 5C. THE VURGUN PRICE (410pt CONDENSED BOLD - ABSOLUTE KING OF THE SCREEN)
    font_deal = load_font("condensed", 410)
    if deal_price >= 10000:
        deal_txt = f"{int(deal_price):,} TL".replace(',', '.')
    elif deal_price == int(deal_price):
        deal_txt = f"{int(deal_price):,} TL".replace(',', '.')
    else:
        deal_txt = f"{deal_price:,.2f} TL".replace(',', 'X').replace('.', ',').replace('X', '.')

    deal_price_y = div_y + nh + 40
    box_temp = draw.textbbox((0, 0), deal_txt, font=font_deal)
    dw = box_temp[2] - box_temp[0]
    if dw > stage_w - 140:
        font_deal, _, dw, _ = fit_font(draw, deal_txt, "condensed", stage_w - 140, 410, 240)

    deal_price_x = (W - dw) // 2
    placed_price_box = draw.textbbox((deal_price_x, deal_price_y), deal_txt, font=font_deal)
    price_actual_bottom = placed_price_box[3]

    # 5D. SAVINGS CALLOUT PILL: "Net 885 TL Cebinde Kalıyor!"
    sav_h = 0
    sav_y = price_actual_bottom + 85
    if savings_amount > 0:
        font_sav = load_font("bold", 66)
        sav_txt = f"Net {savings_amount:,} TL Cebinde Kalıyor!".replace(',', '.')
        sb = draw.textbbox((0, 0), sav_txt, font=font_sav)
        sw, sh = sb[2] - sb[0], sb[3] - sb[1]

        sav_pad_x, sav_pad_y = 60, 24
        sav_w = sw + sav_pad_x * 2
        sav_h = sh + sav_pad_y * 2
        sav_x = (W - sav_w) // 2

    # Calculate exact stage height
    bottom_element_y = (sav_y + sav_h) if savings_amount > 0 else price_actual_bottom
    stage_h = (bottom_element_y + 70) - stage_y

    # --- Render Stage Layers ---
    # Stage shadow
    stage_shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    st_s_draw = ImageDraw.Draw(stage_shadow)
    st_s_draw.rounded_rectangle(
        [(stage_x, stage_y + 25), (stage_x + stage_w, stage_y + stage_h + 25)],
        radius=stage_rad,
        fill=(30, 8, 4, 180)
    )
    stage_shadow = stage_shadow.filter(ImageFilter.GaussianBlur(45))
    bg = Image.alpha_composite(bg, stage_shadow)

    # Stage background
    stage_card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sc_draw = ImageDraw.Draw(stage_card)
    sc_draw.rounded_rectangle(
        [(stage_x, stage_y), (stage_x + stage_w, stage_y + stage_h)],
        radius=stage_rad,
        fill=(18, 8, 6, 235),
        outline=(255, 175, 75, 170),
        width=5
    )

    # Draw Old Price Pill inside stage with exact mathematical vertical centering
    sc_draw.rounded_rectangle(
        [(old_pill_x, pill_row_y), (old_pill_x + old_pill_w, pill_row_y + pill_row_h)],
        radius=pill_row_h // 2,
        fill=(65, 20, 16, 220),
        outline=(255, 100, 80, 180),
        width=4
    )
    old_text_y = pill_row_y + (pill_row_h - ovh) // 2 - ovb[1]
    sc_draw.text((old_pill_x + old_pill_pad_x, old_text_y), old_val_txt, fill=(255, 220, 215), font=font_pill_old)
    # Bold Red Strike through Old Price
    sc_draw.line(
        [(old_pill_x + old_pill_pad_x - 10, pill_row_y + pill_row_h // 2), (old_pill_x + old_pill_pad_x + ovw + 10, pill_row_y + pill_row_h // 2)],
        fill=(255, 45, 45, 255),
        width=12
    )

    # Draw Discount Badge inside stage with exact mathematical vertical centering
    sc_draw.rounded_rectangle(
        [(badge_x, pill_row_y), (badge_x + badge_w, pill_row_y + pill_row_h)],
        radius=pill_row_h // 2,
        fill=(255, 215, 0, 255),
        outline=(255, 255, 255, 220),
        width=4
    )
    badge_text_y = pill_row_y + (pill_row_h - bh) // 2 - bb[1]
    sc_draw.text((badge_x + badge_pad_x, badge_text_y), badge_txt, fill=(15, 10, 5), font=font_badge)

    bg = Image.alpha_composite(bg, stage_card)
    draw = ImageDraw.Draw(bg)

    # Render "ŞU AN VURGUN FİYATI"
    draw.text(((W - nw) // 2, div_y), now_txt, fill=(255, 200, 100), font=font_now_label)

    # Render Deal Price Ambient Glow
    p_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pg_draw = ImageDraw.Draw(p_glow)
    pg_draw.text((deal_price_x, deal_price_y + 12), deal_txt, fill=(255, 120, 40, 140), font=font_deal)
    p_glow = p_glow.filter(ImageFilter.GaussianBlur(30))
    bg = Image.alpha_composite(bg, p_glow)
    draw = ImageDraw.Draw(bg)

    # Render Deal Price (King of the Screen)
    draw.text((deal_price_x, deal_price_y), deal_txt, fill=(255, 255, 255), font=font_deal)

    # Render Savings Pill with exact mathematical vertical centering
    if savings_amount > 0:
        sav_pill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sp_draw = ImageDraw.Draw(sav_pill)
        sp_draw.rounded_rectangle(
            [(sav_x, sav_y), (sav_x + sav_w, sav_y + sav_h)],
            radius=sav_h // 2,
            fill=(10, 180, 80, 70),
            outline=(0, 255, 130, 220),
            width=5
        )
        sav_text_y = sav_y + (sav_h - sh) // 2 - sb[1]
        sp_draw.text((sav_x + sav_pad_x, sav_text_y), sav_txt, fill=(0, 255, 150), font=font_sav)
        bg = Image.alpha_composite(bg, sav_pill)
        draw = ImageDraw.Draw(bg)

    # 6. CTA Button: "Fırsatı Yakala" (Below the Price Stage)
    btn_w = 1200
    btn_h = 210
    bx = (W - btn_w) // 2
    by = stage_y + stage_h + 80
    b_rad = btn_h // 2

    # Button shadow
    btn_shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bs_draw = ImageDraw.Draw(btn_shadow)
    bs_draw.rounded_rectangle([(bx, by + 18), (bx + btn_w, by + btn_h + 18)], radius=b_rad, fill=(40, 10, 5, 120))
    btn_shadow = btn_shadow.filter(ImageFilter.GaussianBlur(35))
    bg = Image.alpha_composite(bg, btn_shadow)
    draw = ImageDraw.Draw(bg)

    # Pure white button base
    draw.rounded_rectangle([(bx, by), (bx + btn_w, by + btn_h)], radius=b_rad, fill=(255, 255, 255))

    # Button text with exact mathematical vertical centering
    font_btn = load_font("bold", 92)
    btn_txt = "Fırsatı Yakala"
    btn_b = draw.textbbox((0, 0), btn_txt, font=font_btn)
    btn_tw = btn_b[2] - btn_b[0]
    btn_th = btn_b[3] - btn_b[1]
    btn_text_y = by + (btn_h - btn_th) // 2 - btn_b[1]
    draw.text(((W - btn_tw)//2, btn_text_y), btn_txt, fill=(20, 16, 14), font=font_btn)

    # 7. Footer: "Amazon TR Güvencesiyle • @vurgunradari • Link Hikayede & Bio'da"
    font_footer = load_font("regular", 62)
    ftr_txt = "Amazon TR • @vurgunradari • Link Hikayede & Bio'da"
    fb = draw.textbbox((0, 0), ftr_txt, font=font_footer)
    fw = fb[2] - fb[0]
    draw.text(((W - fw)//2, by + btn_h + 75), ftr_txt, fill=(245, 218, 205, 230), font=font_footer)

    # 8. Downsample with Lanczos for razor-sharp quality
    final = bg.convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
    final.save(output_png, quality=98)
    print(f"Generated price-dominated ad story: {output_png}")

    # 9. Generate high quality 30fps Reels video with background music
    import random
    audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "audio")
    audio_files = []
    if os.path.isdir(audio_dir):
        audio_files = [os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.lower().endswith((".mp3", ".wav", ".m4a"))]

    cmd = [
        "/opt/homebrew/bin/ffmpeg", "-y",
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

    cmd.append(output_mp4)
    subprocess.run(cmd, check=True)
    print(f"Generated perfect reels video with music: {output_mp4}")


def resolve_and_download_image(deal):
    """Dynamically resolves and downloads the exact high-res product photo for any deal."""
    import re
    import urllib.request
    deal_id = str(deal.get("id", "deal"))
    local_cache = f"static/deals/{deal_id}_thumb.jpg"
    if os.path.exists(local_cache) and os.path.getsize(local_cache) > 2000:
        return local_cache

    candidates = []
    # 1. Direct deal image_url
    if deal.get("image_url"):
        candidates.append(deal.get("image_url"))

    # 2. Cimri CDN image by ID
    num = re.sub(r"\D", "", deal_id)
    if num:
        candidates.append(f"https://cdn.cimri.io/image/1000x1000/product_{num}.jpg")
        candidates.append(f"https://cdn.cimri.io/image/500x500/product_{num}.jpg")

    # 3. Amazon ASIN image from page
    raw_url = deal.get("url", "")
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
