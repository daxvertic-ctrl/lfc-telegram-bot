import os
import json
import time
import datetime
import urllib.parse
import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@LiverpoollIran"

client = genai.Client(api_key=GEMINI_API_KEY)

STATS_HISTORY_FILE = "stats_history.json"

# فیدهای تخصصی تحلیل تاکتیکی، آمار بازیکنان و گزارش بازی
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

def send_to_telegram(text, photo_url=None):
    full_text = f"{text}\n\n🆔 {CHANNEL_USERNAME}"
    
    if photo_url:
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

# ==========================================================
# بخش ۱: گزارشگر زنده روز بازی (ترکیب رسمی و آمار پایان بازی)
# ==========================================================
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
                   - اطلاعات (اسامی بازیکنان ترکیب یا آمار و نمرات کلیدی موجود در متن) را با بولت‌پوینت‌های مرتب بنویس.
                   - اصلاً از حافظه قدیمی خودت بازیکن اضافه نکن (فقط طبق متن بالا).
                   - فقط از تگ <b> استفاده کن (بدون **).
                   - خط آخر: 🔴 #Matchday #LFC #YNWA
                """
                res = generate_ai_text(prompt)
                history["posted_links"].append(entry.link)
                if res and "SKIP" not in res[:15]:
                    send_to_telegram(res, photo_url)
                    return True
    return False

# ==========================================================
# بخش ۲: دریافت جدول زنده لیگ برتر از API ورزشی
# ==========================================================
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

        table_summary = []
        lfc_stats = ""
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
            
            line = f"{rank}. {team_name} | بازی: {gp} | امتیاز: {pts} | تفاضل: {gd} (برد:{w} مساوی:{d} باخت:{l})"
            if int(rank) <= 6 or "Liverpool" in team_name:
                table_summary.append(line)
            if "Liverpool" in team_name:
                lfc_stats = line

        raw_table_text = "\n".join(table_summary)
        prompt = f"""
        تو مسئول آمار کانال تلگرام لیورپول هستی. بر اساس این آمار زنده و رسمی جدول لیگ برتر انگلیس در فصل جاری (2026):
        {raw_table_text}
        وضعیت دقیق لیورپول: {lfc_stats}

        یک پست گرافیکی، شیک و منظم از «📊 وضعیت جدول لیگ برتر و جایگاه لیورپول» به فارسی بنویس:
        - خط اول: 📊 <b>جدول به‌روز لیگ برتر انگلیس و وضعیت قرمزها</b>
        - ۶ تیم بالای جدول (و جایگاه لیورپول) را با ایموجی‌های مناسب (مثل 🥇، 🔴 و...) و اعداد واضح به صورت لیست مرتب بنویس.
        - در پایین جدول، آمار دقیق لیورپول (تعداد بازی، برد، مساوی، باخت، تفاضل گل و امتیاز) را در ۲ خط خلاصه کن.
        - فقط از تگ <b> استفاده کن و از ** استفاده نکن.
        - خط آخر: 🔴 #PremierLeague #LFC #YNWA
        """
        post_text = generate_ai_text(prompt)
        if post_text:
            send_to_telegram(post_text, photo_url=None)
            return True
    except Exception:
        pass
    return False

# ==========================================================
# بخش ۳: رادار ستاره‌ها و تحلیل تاکتیکی شبانه (بات ۳)
# ==========================================================
def post_tactical_player_radar(history):
    # جستجو در فید تخصصی تاکتیک و مقالات تحلیلی
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
                send_to_telegram(res, photo_url)
                return True
    return False

def main():
    history = load_history()
    now_utc = datetime.datetime.utcnow()
    today_str = now_utc.strftime("%Y-%m-%d")

    # ۱. اولویت اول در هر اجرا: بررسی زنده روز بازی (آیا ترکیب رسمی یا آمار پایان بازی اعلام شده؟)
    match_event_sent = check_matchday_events(history)
    if match_event_sent:
        save_history(history)
        return

    # ۲. اگر هنوز امروز «رادار فنی و ستاره‌ها» ارسال نشده (اجرا در نوبت عصر/شب یا اولین اجرای دستی امروز)
    if history.get("last_radar_date") != today_str and (now_utc.hour >= 16 or history.get("last_standings_date") == today_str):
        if post_tactical_player_radar(history):
            history["last_radar_date"] = today_str
            save_history(history)
            return

    # ۳. ارسال گزارش روزانه جدول لیگ برتر (روزی یک بار)
    if history.get("last_standings_date") != today_str and now_utc.hour >= 7:
        if post_league_standings():
            history["last_standings_date"] = today_str
            save_history(history)
            return

    # ۴. اگر در ساعات اولیه روز کاربر دستی تست کرد، یکی از دو گزارش بالا را بفرست تا عملکرد بات را ببیند
    if history.get("last_radar_date") != today_str:
        if post_tactical_player_radar(history):
            history["last_radar_date"] = today_str
            save_history(history)
            return

    save_history(history)

if __name__ == "__main__":
    main()
