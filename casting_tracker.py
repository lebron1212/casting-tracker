TEST_MODE = True  # Set to False for normal filtering

import os
import feedparser
import requests
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

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

# Parse feeds and collect unique entries
seen_titles = set()
articles = []

for feed_url in rss_feeds:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        title = entry.title.strip()
        link = entry.link
        summary = entry.get("summary", "")
        if title not in seen_titles:
            seen_titles.add(title)
            articles.append({"title": title, "link": link, "summary": summary})

# Prompt logic
if TEST_MODE:
    prompt_template = """
Extract the actor name(s), project title, and create a 40-character industry-style descriptor. Format your output as:
ATTACHED: **[Actor Name]**, [Project Title] ([Descriptor])
"""
else:
    prompt_template = """
Evaluate the following casting article. If it includes a Tier A or B actor, or a lesser-known actor in a major project (franchise, major director, major streamer), include it.

Return the result in this format ONLY:
ATTACHED: **[Actor Name]**, [Project Title] ([<40 character descriptor])

If not relevant, reply with: SKIP

---

Title: {title}
Summary: {summary}
"""

# Process each article
results = []

for article in articles:
    prompt = prompt_template.format(title=article['title'], summary=article['summary'])
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
        if not reply.startswith("SKIP"):
            results.append(f"{reply} – [Source]({article['link']})")
    except Exception as e:
        print(f"Error processing article: {article['title']} | {e}")

# Output to markdown
if results:
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/casting_report_{today}.md"

    with open(output_path, "w") as f:
        f.write("# Daily Casting Report\n\n")
        for line in results:
            f.write(f"- {line}\n")

    print(f"✅ Report generated: {output_path}")
else:
    print("No relevant casting news found today.")
