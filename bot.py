import os
import json
import random
import feedparser
import requests
from google import genai

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

RSS_FEEDS = [
    "https://www.thisisanfield.com/feed/",
    "https://www.empireofthekop.com/feed/",
    "https://www.liverpool.com/liverpool-fc-news/?service=rss"
]

HISTORY_FILE = "posted_links.json"

def generate_ai_text(prompt):
    # لیست مدل‌های جدید به ترتیب اولویت
    candidate_models = [
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest"
    ]
    
    # اضافه کردن سایر مدل‌های موجود در اکانت به انتهای لیست
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" in name.lower() and "2.5-flash" not in name.lower() and "2.0" not in name.lower() and "1.5" not in name.lower():
                if name not in candidate_models:
                    candidate_models.append(name)
    except Exception as e:
        print(f"List models warning: {e}")

    # تست یکی‌یکی مدل‌ها تا اولین مدلی که کار می‌کند پیدا شود
    for model_name in candidate_models:
        try:
            print(f"Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                print(f"Success with model: {model_name}!")
                return response.text
        except Exception as e:
            print(f"Model {model_name} skipped: {e}")
            continue
            
    raise Exception("No working Gemini model found!")

def load_posted_links():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted_links(links):
    with open(HISTORY_FILE, "w") as f:
        json.dump(links[-100:], f)

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(url, json=payload)
    print("Telegram status:", res.status_code, res.text)

def generate_news_post(title, summary, link):
    prompt = f"""
    تو ادمین یک کانال تلگرامی پرشور و حرفه‌ای هواداری باشگاه لیورپول (Liverpool FC) هستی.
    این خبر/گزارش جدید را بخوان و به یک پست تلگرامی جذاب به زبان فارسی روان تبدیل کن:
    
    تیتر: {title}
    خلاصه: {summary}
    
    قوانین خروجی:
    1. فقط از تگ‌های مجاز HTML تلگرام مثل <b>برای بولد کردن</b> استفاده کن (اصلاً از ستاره ** استفاده نکن).
    2. خط اول یک تیتر جذاب با ایموجی قرمز (🔴 یا 🔥) و داخل تگ <b> باشد.
    3. متن خبر یا آمار بازی را در ۲ تا ۳ پاراگراف کوتاه یا بولت‌پوینت (•) با ادبیات فوتبالی و هواداری بنویس.
    4. در انتهای پست یک سوال کوتاه مرتبط با همین خبر از هواداران بپرس تا کامنت بگذارند.
    5. خط آخر: 🔴 #Liverpool #LFC #YNWA
    """
    ai_text = generate_ai_text(prompt)
    return f"{ai_text}\n\n🔗 <a href='{link}'>منبع خبر</a>"

def generate_interactive_post():
    prompt = """
    تو ادمین کانال تلگرام هواداران لیورپول هستی.
    به صورت تصادفی یکی از این ۳ مورد را انتخاب کن و یک پست جذاب فارسی بنویس:
    1. یک فکت تاریخی و آمار شگفت‌انگیز از تاریخ باشگاه لیورپول یا اسطوره‌های باشگاه (مثل استیون جرارد، یورگن کلوپ، ویرجیل فن دایک یا سادیو مانه).
    2. یک سوال چهارگزینه‌ای (کوییز هواداری) چالشی درباره بازی‌های خاطره‌انگیز یا آمار بازیکنان لیورپول (جواب را آخر پست در تگ اسپویلر <tg-spoiler>بنویس</tg-spoiler>).
    3. یک پست بحث و تبادل نظر (مثلاً مقایسه دو بازیکن یا نظرخواهی درباره ترکیب تیم).
    
    نکته: فقط از تگ <b> برای بولد کردن استفاده کن و از ** استفاده نکن. انتهای پست هشتگ #YNWA بگذار.
    """
    return generate_ai_text(prompt)

def main():
    posted_links = load_posted_links()
    new_post_sent = False

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            if entry.link not in posted_links:
                post_text = generate_news_post(entry.title, entry.get("summary", ""), entry.link)
                send_to_telegram(post_text)
                posted_links.append(entry.link)
                save_posted_links(posted_links)
                new_post_sent = True
                break
        if new_post_sent:
            break

    if not new_post_sent and random.random() < 0.3:
        interactive_text = generate_interactive_post()
        send_to_telegram(interactive_text)

if __name__ == "__main__":
    main()
