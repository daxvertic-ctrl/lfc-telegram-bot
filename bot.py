import os
import json
import random
import datetime
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
    1. اول بررسی کن آیا این خبر مهم، رسمی یا جذاب برای هواداران است؟ اگر خبر زرد یا بی‌ارزش بود، کلمه "SKIP" را برگردان.
    2. متن را به شدت **خلاصه و کوتاه** (حداکثر ۲ تا ۳ خط یا بولت‌پوینت) به زبان فارسی روان بنویس.
    3. خط اول یک تیتر جذاب با ایموجی 🔴 و داخل تگ <b> باشد.
    4. هشتگ‌ها در انتها: 🔴 #Liverpool #LFC #YNWA
    5. هیچ‌گونه لینک یا نام منبع خارجی قرار نده.
    """
    return generate_ai_text(prompt)

def generate_history_post():
    today_date = datetime.date.today().strftime("%B %d")
    prompt = f"""
    تو ادمین کانال لیورپول هستی. یک رویداد یا افتخار مهم تاریخی باشگاه در روز {today_date} را در حد **یک پاراگراف بسیار کوتاه** به زبان فارسی بنویس.
    نکته: فقط از تگ <b> استفاده کن. هشتگ #LFCHistory #YNWA بگذار و هیچ لینکی نگذار.
    """
    return generate_ai_text(prompt)

def generate_match_preview_or_prediction(summaries_text):
    prompt = f"""
    تو ادمین کانال لیورپول هستی. از داخل متن‌های زیر بررسی کن آیا خبر یا اطلاعیه‌ای درباره «بازی امشب یا فردای لیورپول» وجود دارد یا خیر:
    {summaries_text}
    
    اگر در این اخبار اطلاعاتی درباره بازی پیش‌رو (حریف، ساعت یا تورنمنت) هست، یک پست بسیار کوتاه و جذاب بنویس که شامل:
    - ساعت بازی به وقت ایران و نام حریف
    - از هواداران بخواه نتیجه بازی و گلزن اول را در کامنت پیش‌بینی کنند.
    اگر هیچ خبری درباره بازی امروز نبود، به عنوان تنها خروجی کلمه "SKIP" را برگردان.
    
    نکته: متن خیلی کوتاه باشد. فقط از تگ <b> استفاده کن و هشتگ #MatchDay #YNWA بگذار.
    """
    return generate_ai_text(prompt)

def main():
    posted_links = load_posted_links()
    posts_sent_count = 0
    recent_summaries = ""

    # ۱. بررسی اخبار جدید و مهم
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            if entry.link not in posted_links:
                summary_text = entry.get("summary", "")
                recent_summaries += f" - {entry.title}: {summary_text}\n"
                
                post_text = generate_news_post(entry.title, summary_text)
                
                if post_text and "SKIP" not in post_text:
                    photo_url = extract_image_url(entry)
                    send_to_telegram(post_text, photo_url)
                    posts_sent_count += 1
                
                posted_links.append(entry.link)
                save_posted_links(posted_links)
                
                if posts_sent_count >= 1:
                    break
        if posts_sent_count >= 1:
            break

    # ۲. بررسی اینکه آیا خبر بازی امروز در میان اخبار هست یا خیر؛ اگر نبود، پست تاریخی کوتاه بفرست
    if posts_sent_count == 0:
        match_post = generate_match_preview_or_prediction(recent_summaries)
        if match_post and "SKIP" not in match_post:
            send_to_telegram(match_post, photo_url=None)
        else:
            # اگر روز مسابقه نبود، یک فکت کوتاه از تاریخچه باشگاه بفرست
            history_text = generate_history_post()
            if history_text and "SKIP" not in history_text:
                send_to_telegram(history_text, photo_url=None)

if __name__ == "__main__":
    main()
