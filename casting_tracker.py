import os
import feedparser
import requests
from openai import OpenAI
from datetime import datetime
import re
from newspaper import Article

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

rss_feeds = [
    "https://deadline.com/category/casting/feed/",
    "https://variety.com/v/casting/feed/",
    "https://www.hollywoodreporter.com/topic/casting/feed/",
    "https://collider.com/tag/casting/feed/",
    "https://www.thewrap.com/category/casting/feed/",
    "https://ew.com/tag/casting/feed/"
]

def extract_project_title(title, text):
    title = title.strip()
    match = re.search(r'["\'“‘](.+?)["\'”’]', title)
    if match:
        return match.group(1).upper()
    match = re.search(r'([A-Z0-9:&\'\-\+ ]+)[\'"]?\s+(?:series|movie|project|feature|reboot|prequel)', title, re.I)
    if match:
        return match.group(1).upper()
    caps = re.findall(r'[A-Z][A-Z0-9 :&\'\-]{4,}', title)
    blacklist = {'AND','THE','WITH','JOINS','CAST','OF','IN','TO','ON','BY','FROM','FOR','NEW','SERIES','MOVIE','PROJECT'}
    clean = [c.strip() for c in caps if c not in blacklist and not re.match(r'^([A-Z]{2,4})$', c)]
    if clean:
        return max(clean, key=len)
    return 'UNTITLED PROJECT'

def get_readable_published_time(published_parsed):
    try:
        if published_parsed:
            published_time = datetime(*published_parsed[:6])
            return published_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"
    except Exception:
        return "Unknown"

def get_tmdb_popularity(name):
    try:
        url = "https://api.themoviedb.org/3/search/person"
        params = {"query": name, "api_key": TMDB_API_KEY}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data["results"]:
            return data["results"][0]["popularity"]
    except Exception:
        pass
    return 0

def get_stylized_tag(article_text, project_title):
    prompt = f"""
You are a Hollywood trade analyst creating a verbose, stylized tag describing the most notable *non-cast* differentiator of a film/TV project.

RULES:
- Avoid mentioning actors or characters
- Disregard anything with words 'joins,' 'cast,' 'acts'
- Describe the most *trade-relevant hook*: IP, platform, creator, studio, adaptation, awards, bestseller source, etc.

ARTICLE:
{article_text}

PROJECT TITLE:
{project_title}

TAG:"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a Hollywood trade analyst generating stylized metadata tags."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"GPT TAG ERROR: {e}")
        return "UNKNOWN"

seen_titles = set()
articles = []

for feed_url in rss_feeds:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        title = entry.title.strip()
        link = entry.link
        summary = entry.get("summary", "")
        published = entry.get("published", "")
        published_parsed = entry.get("published_parsed")
        if title not in seen_titles:
            seen_titles.add(title)
            try:
                article_obj = Article(link)
                article_obj.download()
                article_obj.parse()
                full_text = article_obj.text.strip()
            except Exception:
                full_text = ""

            articles.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "published_parsed": published_parsed,
                "full_text": full_text
            })

results = []

for article in articles:
    posted_time = get_readable_published_time(article['published_parsed'])
    name_pattern = re.compile(r"\b[A-Z][a-zA-ZéÉ'’\-]+(?:\s+[A-Z][a-zA-ZéÉ'’\-]+)+\b")
    possible_names = name_pattern.findall(article["title"] + " " + article["summary"])
    unique_names = list(set(possible_names))

    actor_popularity = {name: get_tmdb_popularity(name) for name in unique_names}

    actor_lines = [f"{name}: {score:.1f}" for name, score in actor_popularity.items()]
    actor_block = "\n".join(actor_lines)

    prompt = f"""
You are a casting tracker. Classify only the actors who are newly joining the project — not producers, not existing stars. Use the article title, summary, and full article text to identify which names are being cast.

- Tier A = popularity ≥ 80 or widely famous
- Tier B = popularity 25–79, rising, trending, or buzzworthy
- Tier C = below 25 or unrecognizable — skip

Return in this exact format:

ARTICLE TITLE: {article['title']}.
A-TIER ACTORS: [names]
B-TIER ACTORS: [names]

BLURBS:
Name: 130-char-max context blurb
Name: 130-char-max context line

Posted Date: {posted_time}.

---

Title: {article['title']}
Summary: {article['summary']}

Full Article Text:
{article['full_text']}

Actors:
{actor_block}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert entertainment news analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            timeout=30
        )
        reply = response.choices[0].message.content.strip()
        if not reply.startswith("ARTICLE TITLE:"):
            reply = f"ARTICLE TITLE: {article['title']}\n" + reply

        project_title = extract_project_title(article["title"], article["full_text"])
        tag = get_stylized_tag(article["full_text"], project_title)
        reply += f"\n\nTAG: {tag}\n\nFULL ARTICLE TEXT:\n{article['full_text']}"

        results.append(reply)
    except Exception as e:
        print(f"Error processing article: {article['title']} | {e}")

os.makedirs("reports", exist_ok=True)
with open("reports/latest_casting_report.txt", "w") as f:
    for r in results:
        f.write(r + "\n\n")

print("✅ Report written to reports/latest_casting_report.txt")
