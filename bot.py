import os
import json
import random
import feedparser
import requests
from google import genai

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@LiverpoollIran"

client = genai.Client(api_key=GEMINI_API_KEY)

RSS_FEEDS = [
    "https://www.thisisanfield.com/feed/",
    "https://www.empireofthekop.com/feed/",
    "https://www.liverpool.com/liverpool-fc-news/?service=rss"
]

# لیست عکس‌های باکیفیت پشتیبان از اسطوره‌ها و بازیکنان لیورپول برای زمانی که خبری نیست
BACKUP_PHOTOS = [
    ("https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1200", "🔴 شب‌های جادویی آنفیلد و عظمتی که تمامی ندارد... یس آر یو نه تنها یک شعار، بلکه یک سبک زندگی است! #YNWA"),
    ("https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1200", "🔴 قلب تپنده مرسی‌ساید؛ جایی که تاریخ با فوتبال معنا پیدا می‌کند. #LFC"),
    ("https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200", "🔴 مبارزه تا آخرین ثانیه، این رسم قرمزهای آنفیلد است! #Liverpool")
]

HISTORY_FILE = "posted_links.json"

def generate_ai_text(prompt):
    candidate_models = [
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest"
    ]
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" in name.lower() and "2.5-flash" not in name.lower() and "2.0" not in name.lower() and "1.5" not in name.lower():
                if name not in candidate_models:
                    candidate_models.append(name)
    except Exception:
        pass

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception:
            continue
    return None

def load_posted_links():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted_links(links):
    with open(HISTORY_FILE, "w") as f:
        json.dump(links[-150:], f)

def send_to_telegram(text, photo_url=None):
    full_text = f"{text}\n\n{CHANNEL_USERNAME}"
    
    if photo_url:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": full_text,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": full_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
    requests.post(url, json=payload)

def extract_image_url(entry):
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

def generate_news_post(title, summary):
    prompt = f"""
    تو سردبیر یک کانال هواداری لیورپول هستی. این خبر را بررسی کن:
    تیتر: {title}
    خلاصه: {summary}
    
    دستورالعمل‌ها:
    1. اول بررسی کن آیا این خبر مهم یا جذاب برای هواداران لیورپول است یا خیر؟ اگر خبر زرد یا بی‌ارزش بود، کلمه "SKIP" را برگردان.
    2. اگر مهم است، آن را به شدت **خلاصه و کوتاه** (حداکثر در ۳ خط) به زبان فارسی روان ترجمه کن.
    3. خط اول یک تیتر جذاب با ایموجی 🔴 و داخل تگ <b> باشد.
    4. هشتگ‌ها در انتها: 🔴 #Liverpool #LFC #YNWA
    5. هیچ‌گونه لینک یا نام منبع خارجی قرار نده.
    """
    return generate_ai_text(prompt)

def main():
    posted_links = load_posted_links()
    posts_sent_count = 0

    # بررسی فیدها برای پیدا کردن خبر جدید
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            if entry.link not in posted_links:
                post_text = generate_news_post(entry.title, entry.get("summary", ""))
                
                if post_text and "SKIP" not in post_text:
                    photo_url = extract_image_url(entry)
                    send_to_telegram(post_text, photo_url)
                    posts_sent_count += 1
                
                posted_links.append(entry.link)
                save_posted_links(posted_links)
                
                if posts_sent_count >= 1: # در هر بار اجرا حداکثر ۱ خبر مهم یا ۱ عکس ویژه
                    break
        if posts_sent_count >= 1:
            break

    # اگر در این نیم ساعت خبر مهمی نبود، یک عکس باکیفیت همراه با متن کوتاه هواداری بفرست
    if posts_sent_count == 0:
        photo_url, caption_text = random.choice(BACKUP_PHOTOS)
        send_to_telegram(caption_text, photo_url)

if __name__ == "__main__":
    main()
