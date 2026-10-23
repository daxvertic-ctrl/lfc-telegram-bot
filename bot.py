import os
import json
import random
import datetime
import urllib.parse
import feedparser
import requests
from google import genai

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@LiverpoollIran"

client = genai.Client(api_key=GEMINI_API_KEY)

MAIN_RSS_FEEDS = [
    "https://www.thisisanfield.com/feed/",
    "https://www.empireofthekop.com/feed/",
    "https://www.liverpool.com/liverpool-fc-news/?service=rss"
]

JOURNALIST_QUERIES = [
    'Liverpool ("Fabrizio Romano" OR @FabrizioRomano OR "David Ornstein" OR @David_Ornstein)',
    'Liverpool ("Florian Plettenberg" OR @Plettigoal OR "Di Marzio" OR @DiMarzio)',
    'Liverpool ("Ben Jacobs" OR @JacobsBen OR "Matteo Moretto" OR @MatteMoretto)',
    'Liverpool ("Simon Stone" OR @sistoney67 OR "Gerard Romero" OR @gerardromero)',
    'Liverpool (site:skysports.com OR site:bbc.co.uk/sport OR site:nytimes.com/athletic OR site:espn.com)'
]

INTERVIEW_QUERY = 'Liverpool ("press conference" OR interview OR quotes OR "Arne Slot" OR "Van Dijk" OR Salah) when:2h'

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

def build_google_news_rss(query):
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-GB&gl=GB&ceid=GB:en"

def evaluate_and_format_item(title, summary, category="news"):
    prompt = f"""
    تو سردبیر ارشد کانال تلگرامی هواداران لیورپول هستی.
    این اطلاعات خبر را بررسی کن:
    دسته: {category}
    تیتر اصلی: {title}
    متن یا خلاصه خبر: {summary}

    دستورالعمل‌ها و خط قرمزهای بسیار مهم:
    1. اگر خبر زرد، شایعه بی‌اساس، تکراری یا نامرتبط با لیورپول است، فقط و فقط کلمه SKIP را برگردان.
    2. **به هیچ وجه به گفتن یک تیتر خالی اکتفا نکن!** حتماً در قالب ۲ تا ۳ خط، جزئیات، نام بازیکنان، نام تیم‌ها و اصل ماجرا را به زبان فارسی روان توضیح بده تا کامل و قابل فهم باشد (هیچ ابهامی در متن نباشد).
    3. اگر خبر مربوط به خبرنگاران سرشناس (مثل فابریتزیو رومانو، دیوید اورنشتاین، اسکای اسپورتس و...) است، حتماً **نام منبع یا خبرنگار** را در خط اول ذکر کن (مثلاً: 🚨 <b>به گزارش فابریتزیو رومانو:</b> یا <b>به نقل از دیوید اورنشتاین:</b>).
    4. به اهمیت خبر از 1 تا 10 امتیاز بده.
    5. خروجی باید دقیقاً در این قالب باشد:
    SCORE: [عدد امتیاز 1 تا 10]
    [متن کامل و جذاب خبر برای تلگرام]

    قوانین نگارش:
    - فقط از تگ <b> استفاده کن و اصلاً از ستاره ** استفاده نکن.
    - هیچ لینک یا آدرس سایتی قرار نده.
    - خط آخر هشتگ‌ها: 🔴 #Liverpool #LFC #YNWA
    """
    res = generate_ai_text(prompt)
    if not res or "SKIP" in res[:15]:
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

def collect_journalist_updates(posted_links):
    candidates = []
    selected_queries = random.sample(JOURNALIST_QUERIES, min(3, len(JOURNALIST_QUERIES)))
    for q in selected_queries:
        rss_url = build_google_news_rss(q + " when:1h")
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:2]:
            if entry.link not in posted_links:
                score, text = evaluate_and_format_item(entry.title, entry.get("summary", ""), category="x_journalist")
                posted_links.append(entry.link)
                if text and score >= 6:
                    candidates.append({
                        "score": score,
                        "text": text,
                        "photo": extract_image_url(entry)
                    })
    return candidates

def collect_hourly_news_and_interviews(posted_links):
    candidates = []
    
    interview_rss = build_google_news_rss(INTERVIEW_QUERY)
    int_feed = feedparser.parse(interview_rss)
    for entry in int_feed.entries[:2]:
        if entry.link not in posted_links:
            score, text = evaluate_and_format_item(entry.title, entry.get("summary", ""), category="interview")
            posted_links.append(entry.link)
            if text and score >= 6:
                candidates.append({
                    "score": score + 1,
                    "text": text,
                    "photo": extract_image_url(entry)
                })

    for feed_url in MAIN_RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            if entry.link not in posted_links:
                score, text = evaluate_and_format_item(entry.title, entry.get("summary", ""), category="news")
                posted_links.append(entry.link)
                if text and score >= 6:
                    candidates.append({
                        "score": score,
                        "text": text,
                        "photo": extract_image_url(entry)
                    })
                    
    return candidates

def main():
    posted_links = load_json_file(HISTORY_FILE, [])
    post_queue = load_json_file(QUEUE_FILE, [])
    
    now = datetime.datetime.utcnow()
    is_full_hour_check = (now.minute < 30)

    new_candidates = []

    journalist_items = collect_journalist_updates(posted_links)
    new_candidates.extend(journalist_items)

    if is_full_hour_check or len(post_queue) == 0:
        hourly_items = collect_hourly_news_and_interviews(posted_links)
        new_candidates.extend(hourly_items)

    all_items = post_queue + new_candidates
    all_items.sort(key=lambda x: x["score"], reverse=True)

    if len(all_items) > 0:
        top_post = all_items.pop(0)
        send_to_telegram(top_post["text"], top_post.get("photo"))
        post_queue = all_items[:3]
    else:
        post_queue = []

    save_json_file(HISTORY_FILE, posted_links[-200:])
    save_json_file(QUEUE_FILE, post_queue)

if __name__ == "__main__":
    main()
