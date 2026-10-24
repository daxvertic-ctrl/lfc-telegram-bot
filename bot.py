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

# منابع مستقیم و به‌روز که هم عکس دارند و هم متن کامل
MAIN_RSS_FEEDS = [
    ("This Is Anfield", "https://www.thisisanfield.com/feed/"),
    ("Empire of the Kop", "https://www.empireofthekop.com/feed/"),
    ("Liverpool.com", "https://www.liverpool.com/liverpool-fc-news/?service=rss"),
    ("Liverpool Echo", "https://www.liverpoolecho.co.uk/all-about/liverpool-fc?service=rss"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/football/teams/liverpool/rss.xml")
]

# جستجوی خبرنگاران معتبر و مصاحبه‌ها فقط برای ۲۴ ساعت گذشته
JOURNALIST_QUERIES = [
    'Liverpool ("Fabrizio Romano" OR "David Ornstein" OR "Florian Plettenberg" OR "Di Marzio" OR "Ben Jacobs" OR "Matteo Moretto" OR "Simon Stone" OR "Gerard Romero") when:1d',
    'Liverpool ("Andoni Iraola" OR "press conference" OR interview) when:1d'
]

HISTORY_FILE = "posted_links.json"
QUEUE_FILE = "post_queue.json"

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

def load_json_file(filename, default_val):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val

def save_json_file(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_entry_recent(entry, max_hours=24):
    """بررسی دقیق تاریخ خبر: اگر قدیمی‌تر از ۲۴ ساعت باشد رد می‌شود"""
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return True
    entry_timestamp = time.mktime(parsed_time)
    now_timestamp = time.time()
    diff_hours = (now_timestamp - entry_timestamp) / 3600.0
    return -2 <= diff_hours <= max_hours

def scrape_article_data(url):
    """باز کردن لینک خبر برای استخراج عکس باکیفیت و متن واقعی مقاله"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    photo_url = None
    article_text = ""
    try:
        res = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # ۱. پیدا کردن عکس اصلی و باکیفیت خبر (og:image)
            og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og_img and og_img.get("content"):
                img_candidate = og_img["content"]
                if "lh3.googleusercontent.com" not in img_candidate and "google.com" not in img_candidate:
                    photo_url = img_candidate
                    
            # ۲. استخراج پاراگراف‌های اول متن واقعی خبر
            paragraphs = soup.find_all("p")
            valid_p = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 60]
            article_text = "\n".join(valid_p[:5])
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

def evaluate_and_format_item(title, full_content, source_name):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""
    تو سردبیر ارشد کانال تلگرامی هواداران لیورپول هستی.
    تاریخ امروز: {today_str} (سال 2026).
    
    ⚠️ قوانین بسیار مهم (خط قرمز):
    1. الان سال 2026 است! سرمربی فعلی لیورپول «آندونی ایرائولا» (Andoni Iraola) است. آرنه اسلوت دیگر مربی لیورپول نیست و محمد صلاح و ترنت الکساندر آرنولد دیگر در تیم نیستند.
    2. **مطلقاً از حافظه قدیمی خودت هیچ اسم، بازیکن، مربی یا داستانی را به خبر اضافه نکن!** فقط و فقط بر اساس متن زیر ترجمه و خلاصه‌نویسی کن.
    3. اگر دیدی متن خبر ناقص است، یا مربوط به سال‌های گذشته است، یا درباره اسلوت/صلاح در گذشته است، یا ارزش خبری ندارد، فقط کلمه SKIP را برگردان.

    منبع خبر: {source_name}
    تیتر: {title}
    متن کامل دریافتی از سایت:
    {full_content}

    دستورالعمل خروجی:
    - به اهمیت خبر از 1 تا 10 امتیاز بده.
    - خط اول خروجی فقط عدد امتیاز باشد: SCORE: [عدد]
    - از خط دوم متن پست تلگرام را بنویس:
      * خط اول پست: 🔴 <b>تیتر جذاب خبر</b>
      * خط دوم: 📰 <b>منبع: {source_name}</b> (اگر نام خبرنگار خاصی مثل فابریتزیو رومانو، دیوید اورنشتاین، پلتنبرگ، دی‌مارتزیو و... در متن هست نام او را هم بنویس)
      * در 2 تا 3 خط، اصل خبر و جزئیات واقعی موجود در متن بالا را به فارسی روان و دقیق بنویس تا خبر کاملاً واضح باشد.
      * فقط از تگ <b> استفاده کن (از ** استفاده نکن).
      * خط آخر: 🔴 #Liverpool #LFC #YNWA
    """
    res = generate_ai_text(prompt)
    if not res or "SKIP" in res[:20]:
        return 0, None

    lines = res.split("\n")
    score = 5
    post_lines = []
    for i, line in enumerate(lines):
        if i == 0 and "SCORE:" in line.upper():
            try:
                score_str = line.upper().replace("SCORE:", "").strip()
                score = int(''.join(filter(str.isdigit, score_str)))
            except Exception:
                score = 5
        else:
            post_lines.append(line)

    final_text = "\n".join(post_lines).strip()
    if not final_text:
        return 0, None
    return score, final_text

def process_entry(entry, default_source, posted_links):
    if entry.link in posted_links:
        return None
    if not is_entry_recent(entry, max_hours=24):
        posted_links.append(entry.link)
        return None

    scraped_photo, scraped_text = scrape_article_data(entry.link)
    photo_url = extract_rss_image(entry) or scraped_photo
    
    summary_clean = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()
    full_content = f"{summary_clean}\n{scraped_text}".strip()

    if len(full_content) < 80:
        posted_links.append(entry.link)
        return None

    source_title = default_source
    if "source" in entry and "title" in entry.source:
        source_title = entry.source.title

    score, text = evaluate_and_format_item(entry.title, full_content, source_title)
    posted_links.append(entry.link)

    if text and score >= 7:
        return {
            "score": score,
            "text": text,
            "photo": photo_url,
            "v": 2  # برچسب نسخه جدید برای حذف خودکار خبرهای قدیمی از صف
        }
    return None

def main():
    posted_links = load_json_file(HISTORY_FILE, [])
    raw_queue = load_json_file(QUEUE_FILE, [])
    
    # پاکسازی خودکار خبرهای قدیمی از صف انتظار قبلی
    post_queue = [item for item in raw_queue if item.get("v") == 2]
    
    now = datetime.datetime.utcnow()
    is_full_hour_check = (now.minute < 30)

    new_candidates = []

    # ۱. بررسی فیدهای اصلی لیورپول (همراه با عکس و متن کامل)
    if is_full_hour_check or len(post_queue) == 0:
        for source_name, feed_url in MAIN_RSS_FEEDS:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:
                item = process_entry(entry, source_name, posted_links)
                if item:
                    new_candidates.append(item)

    # ۲. بررسی خبرنگاران و مصاحبه‌های روز
    for q in JOURNALIST_QUERIES:
        encoded = urllib.parse.quote(q)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-GB&gl=GB&ceid=GB:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:2]:
            item = process_entry(entry, "رسانه‌های ورزشی انگلیس", posted_links)
            if item:
                new_candidates.append(item)

    all_items = post_queue + new_candidates
    # اولویت با بالاترین امتیاز و خبرهایی که عکس دارند
    all_items.sort(key=lambda x: (x["score"], 1 if x.get("photo") else 0), reverse=True)

    if len(all_items) > 0:
        top_post = all_items.pop(0)
        send_to_telegram(top_post["text"], top_post.get("photo"))
        post_queue = all_items[:3]
    else:
        post_queue = []

    save_json_file(HISTORY_FILE, posted_links[-250:])
    save_json_file(QUEUE_FILE, post_queue)

if __name__ == "__main__":
    main()
