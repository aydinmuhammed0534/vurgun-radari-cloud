import html
import json
import re
import subprocess
import time
import urllib.parse
from typing import Any, Dict, List

import db
import notifier

import os

ALLOWED_URL_PREFIXES = (
    "https://www.cimri.com/",
    "https://forum.donanimhaber.com/",
    "https://www.amazon.com.tr/",
    "https://t.me/s/",
)

CIMRI_CATEGORIES = [
    ("cilt-bakim-urunleri", "Dermokozmetik & Cilt"),
    ("parfum", "Parfüm"),
    ("gunes-kremleri", "Güneş Kremi & Bakım"),
    ("bluetooth-kulaklik", "Kulaklık"),
    ("oyuncu-mouse", "Oyuncu Mouse"),
    ("ssd-solid-state-drive", "SSD & Depolama"),
    ("monitor", "Monitör"),
    ("dizustu-bilgisayar", "Laptop"),
]


def safe_fetch_html(url: str, timeout: int = 12) -> str:
    """
    Fetches HTML from strictly allow-listed domains using /usr/bin/curl without shell execution.
    """
    if not any(url.startswith(prefix) for prefix in ALLOWED_URL_PREFIXES):
        raise ValueError("URL is not in the allowed domain list")
    if any(ch in url for ch in (" ", "\n", "\r", "\t", ";", "|")):
        raise ValueError("Disallowed character in URL")

    cmd = [
        "/usr/bin/curl",
        "-s",
        "-L",
        "--compressed",
        "--max-time",
        str(int(timeout)),
        "-H",
        "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H",
        "Accept-Language: tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout


_direct_offer_cache: Dict[str, Dict[str, Any]] = {}
_amazon_stock_cache: Dict[str, Dict[str, Any]] = {}


def verify_amazon_live_stock(amazon_url: str) -> Dict[str, Any]:
    """
    Checks an Amazon.com.tr /dp/ product page in real time to verify it is ACTUALLY in stock
    and extracts the live price, basis (previous) price, savings %, clean title, and stock badge.
    """
    now = int(time.time())
    cached = _amazon_stock_cache.get(amazon_url)
    if cached and (now - cached.get("ts", 0) < 240):
        return cached

    m_asin = re.search(r"/dp/([A-Z0-9]{10})", amazon_url)
    if not m_asin:
        return {"in_stock": False, "stock_text": "Belirsiz", "live_price": 0.0, "ts": now}

    clean_dp = f"https://www.amazon.com.tr/dp/{m_asin.group(1)}"
    try:
        html_str = safe_fetch_html(clean_dp, timeout=8)
    except Exception:
        html_str = ""

    if not html_str:
        return {"in_stock": False, "stock_text": "Bağlantı Hatası", "live_price": 0.0, "ts": now}

    avail_m = re.search(r'id="availability"[^>]*>(.*?)</div>', html_str, re.S)
    avail_text = (
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", avail_m.group(1))).strip()
        if avail_m
        else ""
    )
    avail_clean = avail_text.split("{")[0].strip()

    has_cart_btn = ("add-to-cart-button" in html_str) or ("buy-now-button" in html_str)
    in_stock = (
        has_cart_btn
        and ("Stokta" in avail_clean or "stokta" in avail_clean)
        and ("mevcut değil" not in avail_clean.lower())
        and ("stokta yok" not in avail_clean.lower())
    )

    live_price = 0.0
    ptp_m = re.search(r'apex-pricetopay-value[^>]*>.*?class="a-price-whole">([^<]+)<', html_str, re.S)
    if not ptp_m:
        ptp_m = re.search(r'class="a-price-whole">([^<]+)<', html_str)
    if ptp_m:
        raw_num = re.sub(r"[^0-9]", "", ptp_m.group(1))
        if raw_num:
            try:
                live_price = float(raw_num)
            except ValueError:
                live_price = 0.0

    basis_price = 0.0
    basis_m = re.search(r'apex-basisprice-value[^>]*><span class="a-offscreen">([^<]+)<', html_str)
    if basis_m:
        b_str = basis_m.group(1).split(",")[0]
        b_num = re.sub(r"[^0-9]", "", b_str)
        if b_num:
            try:
                basis_price = float(b_num)
            except ValueError:
                basis_price = 0.0

    savings_pct = 0.0
    sav_m = re.search(r"savingsPercentage[^>]*>-\s*%?\s*(\d+)%?<", html_str)
    if sav_m:
        try:
            savings_pct = float(sav_m.group(1))
        except ValueError:
            savings_pct = 0.0

    prod_title = ""
    t_m = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html_str, re.S)
    if t_m:
        prod_title = html.unescape(re.sub(r"\s+", " ", t_m.group(1))).strip()

    res = {
        "in_stock": in_stock,
        "stock_text": avail_clean[:45] if avail_clean else ("Stokta Var" if in_stock else "Stok Bitti"),
        "live_price": live_price,
        "basis_price": basis_price,
        "savings_pct": savings_pct,
        "product_title": prod_title,
        "ts": now,
    }
    _amazon_stock_cache[amazon_url] = res
    return res


def resolve_direct_store_offer(cimri_url: str, title: str) -> Dict[str, Any]:
    """
    Fetches the Cimri product page JSON-LD and extracts ONLY verified InStock Amazon.com.tr (/dp/)
    offers as the primary link (so every deal earns Amazon Associates commission), while using
    competing merchants (Hepsiburada, n11, Trendyol, etc.) as the reference comparison price.
    """
    now = int(time.time())
    cached = _direct_offer_cache.get(cimri_url)
    if cached and (now - cached.get("ts", 0) < 300):
        return cached

    if cimri_url.startswith("https://www.cimri.com/"):
        try:
            html_str = safe_fetch_html(cimri_url, timeout=7)
            for ld in re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html_str,
                re.S,
            ):
                try:
                    obj = json.loads(ld)
                except Exception:
                    continue
                if isinstance(obj, dict) and obj.get("@type") == "Product":
                    off_list = (obj.get("offers") or {}).get("offers") or []
                    amazon_offers = []
                    competing_offers = []
                    for off in off_list:
                        avail = str(off.get("availability") or "")
                        cand_url = (off.get("url") or "").strip()
                        price_val = float(off.get("price") or 0)
                        seller_name = ((off.get("seller") or {}).get("name") or "Mağaza").split("/")[0].strip()
                        if (
                            "InStock" in avail
                            and cand_url.startswith("https://")
                            and "cimri.com" not in cand_url
                            and price_val > 0
                        ):
                            clean_u = notifier.build_affiliate_url(cand_url, "", "", title, seller_name)
                            if "amazon.com.tr/dp/" in clean_u:
                                amz_check = verify_amazon_live_stock(clean_u)
                                if not amz_check["in_stock"]:
                                    continue
                                if amz_check["live_price"] > 0:
                                    price_val = amz_check["live_price"]
                                amazon_offers.append(
                                    {
                                        "url": clean_u,
                                        "price": price_val,
                                        "merchant": "Amazon TR",
                                    }
                                )
                            else:
                                competing_offers.append(
                                    {
                                        "url": clean_u,
                                        "price": price_val,
                                        "merchant": seller_name,
                                    }
                                )
                    if amazon_offers:
                        amazon_offers.sort(key=lambda x: x["price"])
                        best = amazon_offers[0]
                        higher_competitors = [c for c in competing_offers if c["price"] > best["price"]]
                        higher_competitors.sort(key=lambda x: x["price"])
                        second = higher_competitors[0] if higher_competitors else (competing_offers[0] if competing_offers else None)
                        result = {
                            "ok": True,
                            "url": best["url"],
                            "cheapest_price": best["price"],
                            "cheapest_merchant": "Amazon TR",
                            "second_price": second["price"] if second else 0.0,
                            "second_merchant": second["merchant"] if second else "Piyasa Ort.",
                            "ts": now,
                        }
                        _direct_offer_cache[cimri_url] = result
                        return result
        except Exception:
            pass

    _direct_offer_cache[cimri_url] = {"ok": False, "ts": now}
    return {"ok": False, "ts": now}


def scan_cimri_category(slug: str, category_label: str) -> List[Dict[str, Any]]:
    url = f"https://www.cimri.com/{slug}?sort=discount%2Cdesc"
    html_str = safe_fetch_html(url)
    if not html_str:
        return []

    found_deals: List[Dict[str, Any]] = []
    resolved_in_cat = 0
    for script_body in re.findall(r"<script[^>]*>(.*?)</script>", html_str, re.S):
        s = script_body.strip()
        if not s.startswith('{"props":{"pageProps"'):
            continue
        try:
            payload = json.loads(s)
        except Exception:
            continue

        products = (
            payload.get("props", {})
            .get("pageProps", {})
            .get("data", {})
            .get("search", {})
            .get("products", [])
        )
        for p in products:
            prod_id = p.get("id")
            title = (p.get("title") or "").strip()
            rel_url = (p.get("url") or "").strip()
            if not prod_id or not title:
                continue

            top_offers = p.get("topOffers") or []
            if not top_offers:
                continue

            valid_offers = []
            for off in top_offers:
                price_val = float(off.get("price") or 0)
                merch_name = (off.get("merchant") or {}).get("name") or "Mağaza"
                max_p = float(off.get("maxPrice") or off.get("originalPrice") or price_val)
                if price_val > 0:
                    valid_offers.append(
                        {
                            "merchant": merch_name,
                            "price": round(price_val, 2),
                            "max_price": round(max_p, 2),
                        }
                    )

            if not valid_offers:
                continue

            valid_offers.sort(key=lambda x: x["price"])
            cheapest = valid_offers[0]
            cheapest_price = cheapest["price"]
            cheapest_merchant = cheapest["merchant"]

            second_merchant = ""
            second_price = 0.0
            if len(valid_offers) >= 2:
                second_merchant = valid_offers[1]["merchant"]
                second_price = valid_offers[1]["price"]

            badge_disc = float((p.get("badge") or {}).get("discountRatio") or 0.0)
            implied_orig = (
                cheapest_price / (1.0 - badge_disc / 100.0)
                if 0 < badge_disc < 85
                else cheapest["max_price"]
            )

            cimri_page_url = (
                f"https://www.cimri.com{rel_url}"
                if rel_url.startswith("/")
                else f"https://www.cimri.com/{slug}"
            )

            if resolved_in_cat >= 6 and cimri_page_url not in _direct_offer_cache:
                continue

            resolved = resolve_direct_store_offer(cimri_page_url, title)
            resolved_in_cat += 1
            if not resolved.get("ok"):
                continue

            direct_store_url = resolved["url"]
            cheapest_price = float(resolved["cheapest_price"])
            cheapest_merchant = str(resolved["cheapest_merchant"])
            if resolved.get("second_price", 0) > cheapest_price:
                second_price = float(resolved["second_price"])
                second_merchant = str(resolved["second_merchant"])

            spread_pct = (
                ((second_price - cheapest_price) / second_price) * 100.0
                if second_price > cheapest_price
                else 0.0
            )
            reference_price = max(
                min(second_price, implied_orig * 1.25) if second_price > cheapest_price else cheapest_price,
                implied_orig,
                cheapest_price,
            )
            effective_disc_pct = max(
                badge_disc,
                ((reference_price - cheapest_price) / reference_price * 100.0)
                if reference_price > cheapest_price
                else 0.0,
            )
            suggested_resell = round(reference_price * 0.88, 0)
            estimated_profit = max(0.0, round(suggested_resell - cheapest_price, 0))
            roi_pct = (estimated_profit / cheapest_price * 100.0) if cheapest_price > 0 else 0.0

            if effective_disc_pct < 8.0 and estimated_profit < 150:
                continue

            if spread_pct >= 12.0 and estimated_profit >= 250:
                deal_type = "AL-SAT ARBİTRAJ"
            elif effective_disc_pct >= 25.0:
                deal_type = "DİP FİYAT / HATA"
            else:
                deal_type = "FİYAT DÜŞÜŞÜ"

            found_deals.append(
                {
                    "id": f"cimri_{prod_id}",
                    "source": "Amazon TR Radar",
                    "category": category_label,
                    "title": title,
                    "url": direct_store_url,
                    "cheapest_merchant": cheapest_merchant,
                    "cheapest_price": round(cheapest_price, 2),
                    "second_merchant": second_merchant or "Piyasa Ort.",
                    "second_price": round(second_price if second_price > cheapest_price else reference_price, 2),
                    "reference_price": round(reference_price, 2),
                    "discount_pct": round(effective_disc_pct, 1),
                    "spread_pct": round(spread_pct, 1),
                    "suggested_resell_price": round(suggested_resell, 0),
                    "estimated_profit_tl": round(estimated_profit, 0),
                    "roi_pct": round(roi_pct, 1),
                    "deal_type": deal_type,
                    "offers_json": json.dumps(valid_offers[:4], ensure_ascii=False),
                }
            )
    return found_deals


AMAZON_DIRECT_CATEGORIES = [
    ("/gp/bestsellers/beauty/12571730031", "Dermokozmetik & Cilt Bakımı"),
    ("/gp/bestsellers/beauty/12571731031", "Makyaj & Kozmetik"),
    ("/gp/bestsellers/beauty/12571733031", "Parfüm"),
    ("/gp/bestsellers/beauty/13525990031", "Kişisel Bakım & Epilasyon"),
    ("/gp/bestsellers/beauty/12571734031", "Şampuan & Saç Bakımı"),
    ("/gp/bestsellers/hpc", "Sağlık & Temizlik"),
    ("/gp/bestsellers/grocery", "Süpermarket & Kahve"),
    ("/gp/bestsellers/kitchen", "Ev & Mutfak"),
    ("/gp/bestsellers/baby-products", "Anne & Bebek"),
    ("/gp/bestsellers/home-improvement", "Yapı Market & Hırdavat"),
    ("/gp/bestsellers/electronics/17471820031", "Kulaklık"),
    ("/gp/bestsellers/computers/12601909031", "SSD & Depolama"),
    ("/gp/bestsellers/computers/12601904031", "Monitör"),
    ("/gp/bestsellers/computers/12601894031", "Mouse & Aksesuar"),
    ("/gp/bestsellers/computers/12601898031", "Laptop"),
]


def _parse_tr_price(raw_price_str: str) -> float:
    cleaned = html.unescape(raw_price_str or "").strip()
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?", cleaned)
    if not m:
        return 0.0
    whole = m.group(1).replace(".", "")
    frac = m.group(2) or "0"
    try:
        return round(float(f"{whole}.{frac}"), 2)
    except ValueError:
        return 0.0


def scan_amazon_category_deals() -> List[Dict[str, Any]]:
    """
    Directly scans Amazon.com.tr across 15 high-potential sectors (Cosmetics, Dermocosmetics,
    Perfume, Personal Care, Shampoo, Health/Cleaning, Grocery/Coffee, Home/Kitchen, Baby,
    DIY/Tools, and Electronics) for live in-stock items.
    Every returned URL is 100% Amazon.com.tr (/dp/ASIN?tag=vurgunradari-21).
    """
    results: List[Dict[str, Any]] = []
    for path, cat_label in AMAZON_DIRECT_CATEGORIES:
        html_str = safe_fetch_html(f"https://www.amazon.com.tr{path}", timeout=10)
        if not html_str:
            continue
        cards = re.findall(r'id="gridItemRoot"(.*?)</div></div></div></div>', html_str, re.S)
        added_in_cat = 0
        for idx, card in enumerate(cards):
            if added_in_cat >= 8:
                break
            asin_m = re.search(r"/dp/([A-Z0-9]{10})", card)
            title_m = re.search(r"_cDEzb_p13n-sc-css-line-clamp-[^>]*>([^<]+)<", card)
            price_m = re.search(r"_cDEzb_p13n-sc-price_[^>]*>([^<]+)<", card)
            if not asin_m or not title_m or not price_m:
                continue

            asin = asin_m.group(1)
            card_price = _parse_tr_price(price_m.group(1))
            if card_price <= 0:
                continue

            prod_title = html.unescape(title_m.group(1)).strip()
            raw_dp_url = f"https://www.amazon.com.tr/dp/{asin}"
            clean_url = notifier.build_affiliate_url(raw_dp_url, "")

            live_price = card_price
            basis_price = 0.0
            sav_pct = 0.0
            stock_badge = "Stokta Aktif"

            # Enrich the #1 item per category with /dp/ basisPrice & savingsPercentage if available
            if idx == 0:
                info = verify_amazon_live_stock(clean_url)
                if info.get("in_stock") and info.get("live_price", 0) > 0:
                    live_price = float(info["live_price"])
                    basis_price = float(info.get("basis_price") or 0.0)
                    sav_pct = float(info.get("savings_pct") or 0.0)
                    stock_badge = info.get("stock_text", "Stokta Aktif")
                    if info.get("product_title"):
                        prod_title = info["product_title"]

            if basis_price <= live_price:
                basis_price = round(live_price * 1.24, 0)
            if sav_pct <= 0:
                sav_pct = round(((basis_price - live_price) / basis_price) * 100.0, 1)

            suggested_resell = round(basis_price * 0.90, 0)
            estimated_profit = max(0.0, round(suggested_resell - live_price, 0))
            roi_pct = round((estimated_profit / live_price) * 100.0, 1) if live_price > 0 else 0.0

            added_in_cat += 1
            results.append(
                {
                    "id": f"amz_cat_{asin}",
                    "source": "Amazon TR Direkt",
                    "category": f"{cat_label}",
                    "title": prod_title[:160],
                    "url": clean_url,
                    "cheapest_merchant": "Amazon TR",
                    "cheapest_price": round(live_price, 2),
                    "second_merchant": "Piyasa Ort.",
                    "second_price": round(basis_price, 2),
                    "reference_price": round(basis_price, 2),
                    "discount_pct": round(sav_pct, 1),
                    "spread_pct": round(sav_pct, 1),
                    "suggested_resell_price": suggested_resell,
                    "estimated_profit_tl": estimated_profit,
                    "roi_pct": roi_pct,
                    "deal_type": "DİP FİYAT / HATA" if sav_pct >= 20 else "STOKTA AKTİF",
                    "offers_json": json.dumps(
                        [{"merchant": "Amazon TR", "price": live_price, "max_price": basis_price}],
                        ensure_ascii=False,
                    ),
                }
            )
    return results


def scan_amazon_live_feed() -> List[Dict[str, Any]]:
    """
    Scrapes the latest pages of DonanımHaber's Amazon TR strict link-only threads
    (both General Electronics & Gıda/Temizlik/Kozmetik) and verifies live stock + buybox price on Amazon.com.tr.
    """
    dh_threads = [
        (
            "https://forum.donanimhaber.com/amazon-turkiye-firsatlari-sadece-link-paylasimi-sohbet-yasak--135759219",
            r'href="(/amazon-turkiye-firsatlari-sadece-link-paylasimi-sohbet-yasak--135759219-(\d+))"',
            "Amazon",
        ),
        (
            "https://forum.donanimhaber.com/amazon-gida-temizlik-ve-hijyen-urunleri-firsatlari--148358483",
            r'href="(/amazon-gida-temizlik-ve-hijyen-urunleri-firsatlari--148358483-(\d+))"',
            "Kozmetik & Market",
        ),
    ]

    results: List[Dict[str, Any]] = []
    seen_asins = set()

    for base_thread, page_regex, cat_prefix in dh_threads:
        first_html = safe_fetch_html(base_thread)
        if not first_html:
            continue

        pages = re.findall(page_regex, first_html)
        max_page = max((int(p[1]) for p in pages), default=1)
        pages_to_scan = [max_page]
        if max_page > 1 and cat_prefix == "Amazon":
            pages_to_scan.append(max_page - 1)

        for page_num in pages_to_scan:
            page_url = f"{base_thread}-{page_num}" if page_num > 1 else base_thread
            page_html = safe_fetch_html(page_url)
            if not page_html:
                continue

            matches = list(re.finditer(r'id="message_(\d+)"(.*?)</table>', page_html, re.S))
            for m in reversed(matches[-12:]):
                block = m.group(2)
                clean_text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block)).strip())

                urls = re.findall(
                    r"(https?://(?:www\.)?amazon\.com\.tr/(?:[^\s\"'<>]*/)?(?:dp|gp/product)/([A-Z0-9]{10})[^\s\"'<>]*)",
                    html.unescape(block),
                )
                if not urls:
                    continue

                raw_url, asin = urls[0]
                if asin in seen_asins:
                    continue
                seen_asins.add(asin)

                clean_url = notifier.build_affiliate_url(f"https://www.amazon.com.tr/dp/{asin}", "")

                # Verify live stock and live price directly on Amazon TR!
                stock_info = verify_amazon_live_stock(clean_url)
                if not stock_info["in_stock"]:
                    continue

                price_val = float(stock_info["live_price"] or 0.0)
                if price_val <= 0:
                    pm = re.search(r"(\d{1,3}(?:\.\d{3})+|\d{2,6})(?:,\d{1,2})?\s*TL", clean_text, re.I)
                    if pm:
                        try:
                            price_val = float(pm.group(1).replace(".", ""))
                        except ValueError:
                            price_val = 0.0
                if price_val <= 0:
                    continue

                prod_title = stock_info.get("product_title") or ""
                if not prod_title:
                    og_m = re.search(r'<span class="ql-og-description">(.*?)</span>', block, re.S)
                    if og_m:
                        prod_title = html.unescape(og_m.group(1)).strip()
                    else:
                        prod_title = clean_text.split("https://")[0].lstrip("> ").strip()[:140]

                if not prod_title or len(prod_title) < 5:
                    continue

                basis_price = float(stock_info.get("basis_price") or 0.0)
                sav_pct = float(stock_info.get("savings_pct") or 0.0)
                if basis_price <= price_val:
                    basis_price = round(price_val * 1.25, 0)
                if sav_pct <= 0:
                    sav_pct = round(((basis_price - price_val) / basis_price) * 100.0, 1)

                stock_badge = stock_info.get("stock_text", "Stokta Var")
                suggested_resell = round(basis_price * 0.90, 0)
                estimated_profit = max(0.0, round(suggested_resell - price_val, 0))
                roi_pct = round((estimated_profit / price_val) * 100.0, 1)

                results.append(
                    {
                        "id": f"amz_dh_{asin}",
                        "source": "Amazon TR Canlı",
                        "category": f"{cat_prefix} ({stock_badge})",
                        "title": prod_title[:160],
                        "url": clean_url,
                        "cheapest_merchant": "Amazon TR",
                        "cheapest_price": price_val,
                        "second_merchant": "Piyasa Ort.",
                        "second_price": basis_price,
                        "reference_price": basis_price,
                        "discount_pct": sav_pct,
                        "spread_pct": sav_pct,
                        "suggested_resell_price": suggested_resell,
                        "estimated_profit_tl": estimated_profit,
                        "roi_pct": roi_pct,
                        "deal_type": "STOKTA AKTİF",
                        "offers_json": json.dumps(
                            [{"merchant": "Amazon TR", "price": price_val, "max_price": basis_price}],
                            ensure_ascii=False,
                        ),
                    }
                )
    return results


def scan_dh_hot_threads() -> List[Dict[str, Any]]:
    """
    Scrapes the newest topics on DonanımHaber Sıcak Fırsatlar (sorted by newest topic: ?sira=2)
    and extracts ONLY verified in-stock Amazon.com.tr /dp/ASIN deals so every link earns affiliate commission.
    """
    url = "https://forum.donanimhaber.com/sicak-firsatlar--f193?sira=2"
    html_str = safe_fetch_html(url, timeout=8)
    if not html_str:
        return []

    results: List[Dict[str, Any]] = []
    inspected = 0
    for m in re.finditer(
        r'<a[^>]+href="(/[^\"]+--(\d+))"[^>]*>\s*<h3[^>]*>(.*?)</h3>',
        html_str,
        re.S,
    ):
        if inspected >= 6:
            break
        href = m.group(1)
        tid = int(m.group(2))
        raw_title = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(3))).strip())
        if "Sponsorlu İçerik" in raw_title or tid < 163000000:
            continue

        low_title = raw_title.lower()
        if not any(
            kw in low_title
            for kw in (
                "amazon",
                "indirim",
                "fırsat",
                "tl",
                "₺",
                "ssd",
                "kulaklık",
                "mouse",
                "monitör",
                "laptop",
                "kozmetik",
                "parfüm",
                "krem",
                "serum",
                "şampuan",
                "cerave",
                "la roche",
                "bioderma",
                "loreal",
                "maybelline",
                "philips",
                "braun",
                "kahve",
                "deterjan",
            )
        ):
            continue

        inspected += 1
        thread_html = safe_fetch_html(f"https://forum.donanimhaber.com{href}", timeout=7)
        if not thread_html:
            continue

        amz_matches = re.findall(
            r"https?://(?:www\.)?amazon\.com\.tr/(?:[^\s\"'<>]*/)?(?:dp|gp/product)/([A-Z0-9]{10})",
            html.unescape(thread_html),
        )
        if not amz_matches:
            continue

        asin = amz_matches[0]
        clean_url = notifier.build_affiliate_url(f"https://www.amazon.com.tr/dp/{asin}", "")
        stock_info = verify_amazon_live_stock(clean_url)
        if not stock_info["in_stock"] or stock_info["live_price"] <= 0:
            continue

        price_val = float(stock_info["live_price"])
        basis_price = float(stock_info.get("basis_price") or round(price_val * 1.25, 0))
        if basis_price <= price_val:
            basis_price = round(price_val * 1.25, 0)
        sav_pct = float(stock_info.get("savings_pct") or round(((basis_price - price_val) / basis_price) * 100.0, 1))
        prod_title = stock_info.get("product_title") or raw_title[:160]
        stock_badge = stock_info.get("stock_text", "Stokta Var")

        results.append(
            {
                "id": f"dh_topic_{asin}",
                "source": "Amazon TR Canlı",
                "category": f"Anlık ({stock_badge})",
                "title": prod_title[:160],
                "url": clean_url,
                "cheapest_merchant": "Amazon TR",
                "cheapest_price": price_val,
                "second_merchant": "Piyasa Ort.",
                "second_price": basis_price,
                "reference_price": basis_price,
                "discount_pct": sav_pct,
                "spread_pct": sav_pct,
                "suggested_resell_price": round(basis_price * 0.90, 0),
                "estimated_profit_tl": round(basis_price * 0.90 - price_val, 0),
                "roi_pct": 12.0,
                "deal_type": "ANLIK ALARM",
                "offers_json": json.dumps(
                    [{"merchant": "Amazon TR", "price": price_val, "max_price": basis_price}],
                    ensure_ascii=False,
                ),
            }
        )
    return results


_in_memory_posted_asins: set = set()


def _fetch_already_posted_asins(chat_id: str) -> set:
    """
    Fetches the public Telegram channel web preview (https://t.me/s/vurgunradari)
    and extracts all Amazon ASINs already posted so neither local nor GitHub Cloud
    ever posts the same product twice.
    """
    slug = re.sub(r"[^a-zA-Z0-9_]", "", (chat_id or "vurgunradari").lstrip("@")) or "vurgunradari"
    try:
        html_str = safe_fetch_html(f"https://t.me/s/{slug}", timeout=6)
        if html_str:
            return set(re.findall(r"/dp/([A-Z0-9]{10})", html_str))
    except Exception:
        pass
    return set()


def _dispatch_alerts(candidates_for_alert: List[Dict[str, Any]], settings: Dict[str, str], max_alerts: int = 2) -> int:
    auto_notify = settings.get("auto_notify", "1") == "1"
    if not auto_notify or not candidates_for_alert:
        return 0

    tg_enabled = (
        settings.get("telegram_auto_post", "1") == "1"
        and bool(settings.get("telegram_bot_token", "").strip())
        and bool(settings.get("telegram_chat_id", "").strip())
    )
    x_enabled = settings.get("x_auto_post", "1") == "1" and (
        bool(settings.get("x_auth_token", "").strip())
        or bool(os.environ.get("X_AUTH_TOKEN", "").strip())
        or (
            bool(settings.get("x_api_key", "").strip())
            and bool(settings.get("x_access_token", "").strip())
        )
    )

    live_channel_asins = _fetch_already_posted_asins(settings.get("telegram_chat_id", "@vurgunradari"))
    _in_memory_posted_asins.update(live_channel_asins)

    notified_count = 0
    for alert_deal in candidates_for_alert:
        if notified_count >= max_alerts:
            break
        deal_url = str(alert_deal.get("url") or "")
        # Strict safeguard: only post commissioned Amazon TR (/dp/) product links to Telegram & X
        m_asin = re.search(r"amazon\.com\.tr/dp/([A-Z0-9]{10})", deal_url)
        if not m_asin:
            continue
        asin = m_asin.group(1)

        # Deduplication guard: if this ASIN is already on @vurgunradari or sent in this session, mark and skip!
        if asin in _in_memory_posted_asins:
            db.mark_deal_notified(alert_deal["id"])
            continue

        # Lock/mark BEFORE slow network/Chrome calls so no overlapping thread can pick the same deal
        _in_memory_posted_asins.add(asin)
        db.mark_deal_notified(alert_deal["id"])

        res = notifier.send_ntfy_alert(alert_deal, settings)
        tg_ok = False
        if tg_enabled:
            tg_res = notifier.send_telegram_channel_post(alert_deal, settings, is_test=False)
            tg_ok = bool(tg_res.get("ok"))
        x_ok = False
        if x_enabled:
            x_res = notifier.send_x_auto_tweet(alert_deal, settings)
            x_ok = bool(x_res.get("ok"))
        if res.get("ok") or tg_ok or x_ok:
            notified_count += 1
    return notified_count


def run_sniper_scan(trigger_notifications: bool = True) -> Dict[str, Any]:
    """
    Ultra-fast 20-second sniper scan: checks Amazon TR live link feed, newest Sıcak Fırsatlar threads,
    and also dispatches any queued unnotified dashboard deals so nothing sits unshared.
    """
    settings = db.get_settings()
    discovered: List[Dict[str, Any]] = []
    try:
        discovered.extend(scan_amazon_live_feed())
    except Exception:
        pass
    try:
        discovered.extend(scan_dh_hot_threads())
    except Exception:
        pass

    candidates: List[Dict[str, Any]] = []
    new_count = 0
    for d in discovered:
        meta = db.upsert_deal(d)
        if meta["is_new"] or meta["price_dropped_more"]:
            new_count += 1
            if not meta["already_notified"]:
                candidates.append(d)

    # Also pull unshared deals from the database queue if fewer than 2 fresh alerts triggered
    if len(candidates) < 2:
        seen_ids = {c["id"] for c in candidates}
        queued = db.get_unnotified_deals(min_disc=10.0, min_profit=15.0, limit=2)
        for q in queued:
            if q["id"] not in seen_ids:
                candidates.append(q)
                seen_ids.add(q["id"])

    notified = _dispatch_alerts(candidates, settings, max_alerts=1) if trigger_notifications else 0
    return {
        "mode": "sniper",
        "scanned": len(discovered),
        "new_or_dropped": new_count,
        "notified": notified,
        "timestamp": int(time.time()),
    }


def run_full_scan(trigger_notifications: bool = True) -> Dict[str, Any]:
    settings = db.get_settings()
    min_disc = float(settings.get("min_discount_pct") or 12.0)
    min_profit = float(settings.get("min_profit_tl") or 20.0)

    all_discovered: List[Dict[str, Any]] = []
    try:
        all_discovered.extend(scan_amazon_category_deals())
    except Exception:
        pass
    try:
        all_discovered.extend(scan_amazon_live_feed())
    except Exception:
        pass
    try:
        all_discovered.extend(scan_dh_hot_threads())
    except Exception:
        pass

    for slug, label in CIMRI_CATEGORIES[:4]:
        try:
            deals = scan_cimri_category(slug, label)
            all_discovered.extend(deals)
        except Exception:
            continue

    new_count = 0
    candidates_for_alert: List[Dict[str, Any]] = []

    for d in all_discovered:
        meta = db.upsert_deal(d)
        if meta["is_new"] or meta["price_dropped_more"]:
            new_count += 1
            if not meta["already_notified"]:
                if d["discount_pct"] >= min_disc or d["estimated_profit_tl"] >= min_profit:
                    candidates_for_alert.append(d)

    candidates_for_alert.sort(
        key=lambda x: (x["discount_pct"], x["estimated_profit_tl"]), reverse=True
    )

    if len(candidates_for_alert) < 2:
        seen_ids = {c["id"] for c in candidates_for_alert}
        queued = db.get_unnotified_deals(min_disc=10.0, min_profit=15.0, limit=3)
        for q in queued:
            if q["id"] not in seen_ids:
                candidates_for_alert.append(q)
                seen_ids.add(q["id"])

    notified_count = (
        _dispatch_alerts(candidates_for_alert, settings, max_alerts=2)
        if trigger_notifications
        else 0
    )

    return {
        "mode": "full",
        "scanned": len(all_discovered),
        "new_or_dropped": new_count,
        "notified": notified_count,
        "timestamp": int(time.time()),
    }


