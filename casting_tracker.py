import os
import feedparser
import requests
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import re

# Load environment variables from .env
load_dotenv()

# Confirm network access to OpenAI before continuing
try:
    test_resp = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
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

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# RSS feeds (casting-specific)
rss_feeds = [
    "https://deadline.com/category/casting/feed/",
    "https://variety.com/v/casting/feed/",
    "https://www.hollywoodreporter.com/topic/casting/feed/",
    "https://collider.com/tag/casting/feed/",
    "https://www.thewrap.com/category/casting/feed/",
    "https://ew.com/tag/casting/feed/"
]

# Define Tier A and Tier B actors (refined household names only)
A_TIER_ACTORS = [
    "Tom Cruise", "Tom Hanks", "Will Ferrell", "Leonardo DiCaprio", "Brad Pitt",
    "Jennifer Lawrence", "Scarlett Johansson", "Zac Efron", "Sandra Bullock", "Denzel Washington",
    "Ryan Gosling", "Emma Stone", "George Clooney", "Julia Roberts", "Natalie Portman", "Chris Hemsworth",
    "Anne Hathaway", "Matt Damon", "Robert Downey Jr.", "Ben Affleck", "Morgan Freeman"
]

B_TIER_ACTORS = [
    "Kieran Culkin", "Jasmine Cephas Jones", "Kyle Chandler", "Garret Dillahunt",
    "Vincent D'Onofrio", "James Van Der Beek", "Evan Peters", "Anya Taylor-Joy",
    "William Moseley", "Mark Valley", "Ted Danson", "Mary Steenburgen"
]

# Parse feeds and collect unique entries
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

# Function to convert the published time to a readable format
def get_readable_published_time(published_parsed):
    try:
        if published_parsed:
            published_time = datetime(*published_parsed[:6])
            return published_time.strftime("%Y-%m-%d %H:%M:%S")
        return "Unknown"
    except Exception as e:
        print(f"Error parsing published date: {e}")
        return "Unknown"

# GPT prompt logic for extraction (no longer includes project title)
prompt_template = """
You are a casting tracker. Your job is to extract casting attachments for actors with the following fame scores:

- **Tier A actors**: Fame score of at least **8** (household names, long career, prestigious awards, high box office recognition)
- **Tier B actors**: Fame score of at least **6.5** (trendiness, rising stars, good industry buzz)
- **Tier C actors**: Fame score lower than **6.4** (lesser-known, emerging actors) – **DO NOT include these actors under any circumstances!**

Return only in this format:

ARTICLE TITLE: {article_title}.
A-TIER ACTORS: {a_tier_actors}.
B-TIER ACTORS: {b_tier_actors}.
Posted Date: {posted_time}.

---

Title: {article_title}
Summary: {summary}
"""

# Process each article using GPT to extract actors and article metadata
results = []

for article in articles:
    posted_time = get_readable_published_time(article['published_parsed'])

    a_tier_actors = [actor for actor in A_TIER_ACTORS if actor in article['title'] or actor in article['summary']]
    b_tier_actors = [actor for actor in B_TIER_ACTORS if actor in article['title'] or actor in article['summary']]

    prompt = prompt_template.format(
        article_title=article['title'],
        summary=article['summary'],
        a_tier_actors=", ".join(a_tier_actors),
        b_tier_actors=", ".join(b_tier_actors),
        posted_time=posted_time
    )

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

# Ensure the output directory exists
output_dir = "reports"
os.makedirs(output_dir, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
output_html_path = f"{output_dir}/casting_report_{today}.html"
latest_html_path = f"{output_dir}/latest_casting_report.html"

# Write directly to HTML
html_template = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Daily Casting Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 2rem; background: #f9f9f9; color: #333; }}
        h1 {{ display: none; }}
        h2 {{ font-size: 1.25rem; color: #444; margin-top: 2rem; }}
        .block {{ padding: 1rem; margin-bottom: 1.5rem; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .block pre {{ white-space: pre-wrap; font-family: inherit; }}
    </style>
</head>
<body>
    <h1>Daily Casting Report – {today}</h1>
"""

# Write both dated and latest HTML reports
for path in [output_html_path, latest_html_path]:
    with open(path, "w") as html_file:
        html_file.write(html_template)
        for result in results:
            html_file.write(f"<div class='block'><pre>{result}</pre></div>\n")
        html_file.write("</body></html>")

print(f"✅ HTML report generated: {output_html_path}")
print(f"✅ Latest HTML report updated: {latest_html_path}")
