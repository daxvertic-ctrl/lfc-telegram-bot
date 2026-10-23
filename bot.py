import os
import json
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
    1. اول بررسی کن آیا این خبر مهم، رسمی یا جذاب برای هواداران لیورپول است یا خیر؟ اگر خبر زرد، بی‌ارزش یا حاشیه پیش پاافتاده‌ای بود، کلمه "SKIP" را به عنوان تنها خروجی برگردان.
    2. اگر خبر مهمی است، آن را به شدت **خلاصه، مفید و کوتاه** (حداکثر در ۳ خط یا ۳ بولت‌پوینت بسیار کوتاه) به زبان فارسی روان ترجمه کن.
    3. خط اول یک تیتر جذاب با ایموجی 🔴 و داخل تگ <b> باشد.
    4. هشتگ‌ها در انتها: 🔴 #Liverpool #LFC #YNWA
    5. هیچ‌گونه لینک یا نام منبع خارجی قرار نده.
    """
    return generate_ai_text(prompt)

def main():
    posted_links = load_posted_links()
    posts_sent_count = 0

    # بررسی فیدها برای پیدا کردن خبر جدید و مهم
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
                
                if posts_sent_count >= 2: # حداکثر 2 خبر در هر بار اجرا
                    break
        if posts_sent_count >= 2:
            break

if __name__ == "__main__":
    main()
