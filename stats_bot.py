import os
import io
import json
import time
import datetime
import feedparser
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from google import genai

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@LiverpoollIran"

client = genai.Client(api_key=GEMINI_API_KEY)

STATS_HISTORY_FILE = "stats_history.json"

TACTICAL_RSS_FEEDS = [
    ("This Is Anfield Tactics", "https://www.thisisanfield.com/category/season/tactics-analysis/feed/"),
    ("This Is Anfield Main", "https://www.thisisanfield.com/feed/"),
    ("Empire of the Kop", "https://www.empireofthekop.com/feed/"),
    ("Liverpool.com", "https://www.liverpool.com/liverpool-fc-news/?service=rss")
]

def generate_ai_text(prompt):
    candidate_models = [
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest"
    ]
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                return response.text.strip()
        except Exception:
            continue
    return None

def load_history():
    default_data = {
        "posted_links": [],
        "last_standings_date": "",
        "last_radar_date": ""
    }
    if os.path.exists(STATS_HISTORY_FILE):
        try:
            with open(STATS_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return default_data
    return default_data

def save_history(data):
    data["posted_links"] = data.get("posted_links", [])[-200:]
    with open(STATS_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def download_and_watermark_image(photo_url):
    """دانلود عکس و حک کردن واترمارک گرافیکی @LiverpoollIran"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get(photo_url, headers=headers, timeout=12)
        if res.status_code != 200:
            return None
        img = Image.open(io.BytesIO(res.content)).convert("RGBA")
        w, h = img.size
        if w < 250 or h < 200:
            return None

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = max(18, int(w * 0.028))
        font = load_font(font_size)
        watermark_text = "LFC IRAN | @LiverpoollIran"

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x = int(font_size * 0.7)
        pad_y = int(font_size * 0.45)
        margin = int(w * 0.025)

        x1 = w - tw - (pad_x * 2) - margin
        y1 = h - th - (pad_y * 2) - margin
        x2 = w - margin
        y2 = h - margin

        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=(15, 15, 20, 215))
        draw.rounded_rectangle([x1, y1, x1 + 6, y2], radius=3, fill=(200, 16, 46, 255))
        draw.text((x1 + pad_x + 4, y1 + pad_y - 2), watermark_text, font=font, fill=(255, 255, 255, 250))

        final_img = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        final_img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        return buf
    except Exception:
        return None

def create_standings_image_card(teams_data):
    """ساخت پوستر گرافیکی اختصاصی جدول لیگ برتر با تم قرمز آنفیلد"""
    W, H = 1080, 1320
    img = Image.new("RGB", (W, H), (16, 16, 22))
    draw = ImageDraw.Draw(img)

    # هدر قرمز باشگاه لیورپول
    draw.rectangle([0, 0, W, 185], fill=(185, 15, 42))
    draw.rectangle([0, 180, W, 190], fill=(245, 196, 48))  # خط طلایی

    font_title = load_font(46)
    font_sub = load_font(26)
    font_header = load_font(26)
    font_row = load_font(28)
    font_pts = load_font(31)

    draw.text((60, 42), "PREMIER LEAGUE STANDINGS", font=font_title, fill=(255, 255, 255))
    today_str = datetime.date.today().strftime("%d %b %Y")
    draw.text((60, 112), f"LIVERPOOL IRAN MEDIA  |  {today_str}", font=font_sub, fill=(255, 230, 230))

    # سرستون‌های جدول
    y_head = 230
    draw.rounded_rectangle([40, y_head - 12, W - 40, y_head + 48], radius=8, fill=(32, 32, 42))
    draw.text((65, y_head), "#", font=font_header, fill=(180, 180, 195))
    draw.text((135, y_head), "CLUB", font=font_header, fill=(180, 180, 195))
    draw.text((590, y_head), "MP", font=font_header, fill=(180, 180, 195))
    draw.text((685, y_head), "W-D-L", font=font_header, fill=(180, 180, 195))
    draw.text((845, y_head), "GD", font=font_header, fill=(180, 180, 195))
    draw.text((945, y_head), "PTS", font=font_header, fill=(245, 196, 48))

    y = 305
    row_h = 84

    for item in teams_data[:10]:
        is_lfc = "liverpool" in item["team"].lower()
        bg_color = (200, 16, 46) if is_lfc else (26, 26, 35)
        border_color = (245, 196, 48) if is_lfc else (42, 42, 55)

        draw.rounded_rectangle([40, y, W - 40, y + row_h - 10], radius=12, fill=bg_color, outline=border_color, width=2 if is_lfc else 1)

        # نوار نشانگر سهمیه لیگ قهرمانان (رتبه‌های ۱ تا ۴)
        rank_num = int(item["rank"]) if str(item["rank"]).isdigit() else 99
        if rank_num <= 4 and not is_lfc:
            draw.rounded_rectangle([40, y, 50, y + row_h - 10], radius=4, fill=(0, 195, 115))

        text_color = (255, 255, 255)
        pts_color = (255, 255, 255) if is_lfc else (245, 196, 48)

        draw.text((65, y + 22), str(item["rank"]), font=font_row, fill=text_color)
        draw.text((135, y + 22), item["team"][:20], font=font_row, fill=text_color)
        draw.text((595, y + 22), str(item["gp"]), font=font_row, fill=text_color)
        draw.text((675, y + 22), f"{item['w']}-{item['d']}-{item['l']}", font=font_row, fill=text_color)
        draw.text((845, y + 22), str(item["gd"]), font=font_row, fill=text_color)
        draw.text((950, y + 20), str(item["pts"]), font=font_pts, fill=pts_color)

        y += row_h

    # فوتر و واترمارک اختصاصی کانال
    draw.rectangle([0, H - 85, W, H], fill=(10, 10, 14))
    draw.text((60, H - 58), "YOU'LL NEVER WALK ALONE", font=font_sub, fill=(200, 16, 46))
    draw.text((W - 390, H - 58), "Telegram: @LiverpoollIran", font=font_sub, fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def send_to_telegram(text, photo_url=None, image_buffer=None):
    full_text = f"{text}\n\n🆔 {CHANNEL_USERNAME}"
    
    # ۱. اگر پوستر گرافیکی تولید شده در حافظه داریم، مستقیم آپلود کن
    if image_buffer:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        data = {
            "chat_id": CHAT_ID,
            "caption": full_text,
            "parse_mode": "HTML"
        }
        files = {"photo": ("lfc_graphic.jpg", image_buffer, "image/jpeg")}
        res = requests.post(url, data=data, files=files)
        if res.status_code == 200:
            return

    # ۲. اگر لینک عکس داریم، ابتدا واترمارک بزن و بفرست
    if photo_url:
        watermarked_buf = download_and_watermark_image(photo_url)
        if watermarked_buf:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            data = {
                "chat_id": CHAT_ID,
                "caption": full_text,
                "parse_mode": "HTML"
            }
            files = {"photo": ("lfc_radar.jpg", watermarked_buf, "image/jpeg")}
            res = requests.post(url, data=data, files=files)
            if res.status_code == 200:
                return

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": full_text,
            "parse_mode": "HTML"
        }
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            return
            
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": full_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def scrape_article_data(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    photo_url = None
    article_text = ""
    try:
        res = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_img and og_img.get("content"):
                img_candidate = og_img["content"]
                if "lh3.googleusercontent.com" not in img_candidate and "google.com" not in img_candidate:
                    photo_url = img_candidate
            paragraphs = soup.find_all("p")
            valid_p = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 60]
            article_text = "\n".join(valid_p[:6])
    except Exception:
        pass
    return photo_url, article_text

def extract_rss_image(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'url' in media:
                return media['url']
    if 'media_thumbnail' in entry:
        for thumb in entry.media_thumbnail:
            if 'url' in thumb:
                return thumb['url']
    if 'links' in entry:
        for link in entry.links:
            if 'type' in link and 'image' in link['type']:
                return link['href']
    return None

def is_entry_recent(entry, max_hours=36):
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return True
    entry_timestamp = time.mktime(parsed_time)
    diff_hours = (time.time() - entry_timestamp) / 3600.0
    return -2 <= diff_hours <= max_hours

def check_matchday_events(history):
    match_keywords = [
        "confirmed liverpool lineup", "starting xi", "team news",
        "player ratings", "talking points", "full-time", "match report"
    ]
    
    for source_name, feed_url in TACTICAL_RSS_FEEDS[1:]:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:4]:
            if entry.link in history["posted_links"]:
                continue
            if not is_entry_recent(entry, max_hours=6):
                continue
                
            title_lower = entry.title.lower()
            if any(k in title_lower for k in match_keywords):
                scraped_photo, scraped_text = scrape_article_data(entry.link)
                photo_url = extract_rss_image(entry) or scraped_photo
                summary_clean = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()
                full_content = f"{summary_clean}\n{scraped_text}".strip()
                
                if len(full_content) < 100:
                    continue

                prompt = f"""
                تو گزارشگر تخصصی مسابقات کانال هواداری لیورپول در سال 2026 هستی (سرمربی فعلی: آندونی ایرائولا).
                این گزارش تازه منتشر شده از بازی امروز را بررسی کن:
                تیتر: {entry.title}
                متن: {full_content}

                دستورالعمل:
                1. اگر این متن واقعاً شامل «ترکیب رسمی اعلام شده لیورپول برای بازی امروز» یا «نتیجه، آمار و نمرات بازیکنان پس از پایان بازی امروز» است، آن را به یک پست فوق‌العاده جذاب و مرتب تبدیل کن.
                2. اگر فقط یک پیش‌بینی، شایعه یا خبر عادی است، فقط و فقط کلمه SKIP را برگردان.
                3. در صورت تایید:
                   - خط اول با ایموجی 📋 (برای ترکیب) یا 📊 (برای آمار و نمرات پایان بازی) و تگ <b> یک تیتر جذاب بنویس.
                   - اطلاعات را با بولت‌پوینت‌های مرتب بنویس.
                   - اصلاً از حافظه قدیمی خودت بازیکن اضافه نکن (فقط طبق متن بالا).
                   - فقط از تگ <b> استفاده کن (بدون **).
                   - خط آخر: 🔴 #Matchday #LFC #YNWA
                """
                res = generate_ai_text(prompt)
                history["posted_links"].append(entry.link)
                if res and "SKIP" not in res[:15]:
                    send_to_telegram(res, photo_url=photo_url)
                    return True
    return False

def post_league_standings():
    url = "https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return False
        data = res.json()
        entries = data.get("children", [{}])[0].get("standings", {}).get("entries", [])
        if not entries:
            return False

        teams_for_image = []
        lfc_stats_line = ""
        for item in entries:
            team_name = item.get("team", {}).get("displayName", "")
            stats = {s.get("name"): s.get("displayValue") for s in item.get("stats", [])}
            rank = stats.get("rank", "")
            pts = stats.get("points", "")
            gp = stats.get("gamesPlayed", "")
            gd = stats.get("pointDifferential", "")
            w = stats.get("wins", "")
            d = stats.get("ties", "")
            l = stats.get("losses", "")
            
            row_dict = {
                "rank": rank,
                "team": team_name,
                "gp": gp,
                "w": w,
                "d": d,
                "l": l,
                "gd": gd,
                "pts": pts
            }
            teams_for_image.append(row_dict)
            if "Liverpool" in team_name:
                lfc_stats_line = f"رتبه: {rank} | بازی: {gp} | امتیاز: {pts} | تفاضل گل: {gd} (برد: {w}، مساوی: {d}، باخت: {l})"

        # در صورتی که لیورپول پایین‌تر از رتبه ۱۰ باشد، جایگزین ردیف آخر پوستر شود تا همیشه دیده شود
        top_10 = teams_for_image[:10]
        if not any("liverpool" in t["team"].lower() for t in top_10):
            for t in teams_for_image:
                if "liverpool" in t["team"].lower():
                    top_10[-1] = t
                    break

        # ساخت پوستر گرافیکی اختصاصی جدول
        poster_buf = create_standings_image_card(top_10)

        caption = (
            f"📊 <b>جدول به‌روز لیگ برتر انگلیس و جایگاه قرمزها</b>\n\n"
            f"🔴 <b>وضعیت لیورپول در جدول:</b>\n"
            f"🔹 {lfc_stats_line}\n\n"
            f"🔴 #PremierLeague #Standings #LFC #YNWA"
        )
        send_to_telegram(caption, image_buffer=poster_buf)
        return True
    except Exception:
        pass
    return False

def post_tactical_player_radar(history):
    for source_name, feed_url in TACTICAL_RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            if entry.link in history["posted_links"]:
                continue
            if not is_entry_recent(entry, max_hours=36):
                continue

            scraped_photo, scraped_text = scrape_article_data(entry.link)
            photo_url = extract_rss_image(entry) or scraped_photo
            summary_clean = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()
            full_content = f"{summary_clean}\n{scraped_text}".strip()

            if len(full_content) < 150:
                continue

            prompt = f"""
            تو تحلیلگر تاکتیکی و مسئول بخش «رادار ستاره‌ها» در کانال هواداری لیورپول هستی (سال 2026 - سرمربی فعلی: آندونی ایرائولا).
            این مقاله را بررسی کن:
            منبع: {source_name}
            تیتر: {entry.title}
            متن کامل: {full_content}

            قوانین:
            1. اگر این مطلب حاوی «تحلیل فنی/تاکتیکی تیم»، «بررسی آمار و عملکرد یکی از بازیکنان فعلی لیورپول» یا «نکات فنی بازی» است، آن را به یک پست تحلیلی جذاب تبدیل کن.
            2. اگر یک خبر کوتاه حاشیه‌ای یا شایعه است، فقط کلمه SKIP را برگردان.
            3. مطلقاً از حافظه قدیمی خودت (مثل اسلوت، صلاح یا آرنولد در گذشته) چیزی اضافه نکن و فقط بر اساس متن بالا بنویس.
            4. قالب پست:
               - خط اول: 🎯 <b>رادار فنی و آماری | [عنوان جذاب تحلیل]</b>
               - خط دوم: 📰 <b>منبع تحلیل: {source_name}</b>
               - در ۳ یا ۴ بولت‌پوینت جذاب (با ایموجی ⚡️ یا 🔹)، نکات کلیدی، آمارهای ذکر شده در متن و تحلیل عملکرد بازیکن یا سیستم ایرائولا را به فارسی روان بنویس.
               - فقط از تگ <b> استفاده کن (بدون **).
               - خط آخر: 🔴 #Tactics #PlayerRadar #LFC #YNWA
            """
            res = generate_ai_text(prompt)
            history["posted_links"].append(entry.link)
            if res and "SKIP" not in res[:15]:
                send_to_telegram(res, photo_url=photo_url)
                return True
    return False

def main():
    history = load_history()
    now_utc = datetime.datetime.utcnow()
    today_str = now_utc.strftime("%Y-%m-%d")

    # ۱. بررسی زنده روز بازی (ترکیب رسمی یا آمار پایان بازی همراه با واترمارک)
    if check_matchday_events(history):
        save_history(history)
        return

    # ۲. ارسال پوستر گرافیکی جدول لیگ برتر (روزی یک بار)
    if history.get("last_standings_date") != today_str:
        if post_league_standings():
            history["last_standings_date"] = today_str
            save_history(history)
            return

    # ۳. ارسال رادار فنی و ستاره‌ها همراه با عکس واترمارک‌شده (روزی یک بار)
    if history.get("last_radar_date") != today_str:
        if post_tactical_player_radar(history):
            history["last_radar_date"] = today_str
            save_history(history)
            return

    save_history(history)

if __name__ == "__main__":
    main()
