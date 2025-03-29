import os
import feedparser
import requests
from openai import OpenAI
from datetime import datetime
import re

# Pull API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Pre-check OpenAI access
try:
    test_resp = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        timeout=10
    )
    if test_resp.status_code != 200:
        print(f"❌ OpenAI pre-check failed: Status code {test_resp.status_code}")
        exit(1)
    else:
        print("✅ Network access to OpenAI confirmed")
except Exception as e:
    print(f"❌ Failed to connect to OpenAI API: {e}")
    exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# RSS feeds
rss_feeds = [
    "https://deadline.com/category/casting/feed/",
    "https://variety.com/v/casting/feed/",
    "https://www.hollywoodreporter.com/topic/casting/feed/",
    "https://collider.com/tag/casting/feed/",
    "https://www.thewrap.com/category/casting/feed/",
    "https://ew.com/tag/casting/feed/"
]

# Parse RSS feeds
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
            articles.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "published_parsed": published_parsed
            })

# Parse published date
def get_readable_published_time(published_parsed):
    try:
        if published_parsed:
            published_time = datetime(*published_parsed[:6])
            return published_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"
    except Exception as e:
        print(f"Error parsing published date: {e}")
        return "Unknown"

# Query TMDb popularity score
def get_tmdb_popularity(name):
    try:
        url = "https://api.themoviedb.org/3/search/person"
        params = {"query": name, "api_key": TMDB_API_KEY}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data["results"]:
            return data["results"][0]["popularity"]
    except Exception as e:
        print(f"TMDb error for {name}: {e}")
    return 0



results = []

for article in articles:
    posted_time = get_readable_published_time(article['published_parsed'])

    # Extract possible actor names from title and summary
    name_pattern = re.compile(r"\b[A-Z][a-zA-ZéÉ'’\-]+(?:\s+[A-Z][a-zA-ZéÉ'’\-]+)+\b")
    possible_names = name_pattern.findall(article["title"] + " " + article["summary"])
    unique_names = list(set(possible_names))

    actor_popularity = {}

    for name in unique_names:
        popularity = get_tmdb_popularity(name)
        actor_popularity[name] = popularity
        if popularity == 0:
            print(f"⚠️ No TMDb result for: {name}")

    actor_lines = [f"{name}: {score:.1f}" for name, score in actor_popularity.items()]
    actor_block = "\n".join(actor_lines)
    prompt = f"""
You are a casting tracker. Classify each actor into A-tier or B-tier using their TMDb popularity **and** whether they are widely known household names.

- Tier A = popularity ≥ 80 **or** undeniably famous
- Tier B = popularity 40–79 and solid industry presence
- Ignore names that are unrecognizable, few small credits, or irrelevant (Tier C)

Return only this format:

ARTICLE TITLE: {article['title']}.
A-TIER ACTORS: [names]
B-TIER ACTORS: [names]
Posted Date: {posted_time}.

---

Title: {article['title']}
Summary: {article['summary']}

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
        if reply:
            results.append(reply)
    except Exception as e:
        print(f"Error processing article: {article['title']} | {e}")

# Save output
os.makedirs("reports", exist_ok=True)
output_path = "reports/latest_casting_report.txt"

with open(output_path, "w") as f:
    for r in results:
        f.write(r + "\n\n")

print(f"✅ Report written to {output_path}")
