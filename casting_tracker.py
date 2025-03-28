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

# Define Tier A and Tier B actors (example list)
A_TIER_ACTORS = ["Adam Driver", "Tom Hanks", "Will Ferrell", "Regina Hall"]
B_TIER_ACTORS = ["Kieran Culkin", "Jasmine Cephas Jones", "Kyle Chandler", "Garret Dillahunt"]

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

# GPT prompt logic for extraction
prompt_template = """
You are a casting tracker. Your job is to extract casting attachments for actors with the following fame scores:

- **Tier A actors**: Fame score of at least **8** (high name recognition, long career, prestigious awards, etc.)
- **Tier B actors**: Fame score of at least **6.5** (trendiness, rising stars, good industry buzz)
- **Tier C actors**: Fame score lower than **6.4** (lesser-known, emerging actors) – **DO NOT include these actors under any circumstances!**

You are to list the actors, the project title, and generate a short industry tag, using the following rules.

Return only in this format:

PROJECT TITLE: {title}.
A Tier Actors: {a_tier_actors}.
B Tier Actors: {b_tier_actors}.
Industry Tag: {industry_tag}.

---

Title: {title}
Summary: {summary}
"""

# Function to extract project title from the article title
def extract_project_title(title):
    # Try to extract from text inside single quotes
    if "'" in title:
        start = title.find("'") + 1
        end = title.find("'", start)
        if start != -1 and end != -1:
            return title[start:end]
    
    # If no quotes, build a default project title
    default_title = "UNT **BIG NAME/OTHER DETAIL** **GENRE/TYPE (MOVIE/SERIES)**"
    return default_title

# Process each article using GPT to extract actors, project titles, and industry tags
results = []

for article in articles:
    # Extract project title using the function
    project_title = extract_project_title(article['title'])

    # Extract actors from the article title
    a_tier_actors = [actor for actor in A_TIER_ACTORS if actor in article['title']]
    b_tier_actors = [actor for actor in B_TIER_ACTORS if actor in article['title']]

    # Assign industry tag (this is hardcoded for simplicity, you can adjust this logic based on content)
    industry_tag = "NTFLX CRIME DRAMA"  # Example industry tag; you can modify this logic based on article content

    # Format the prompt for GPT
    prompt = prompt_template.format(
        title=project_title,
        summary=article['summary'],
        a_tier_actors=", ".join(a_tier_actors),
        b_tier_actors=", ".join(b_tier_actors),
        industry_tag=industry_tag
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
        
        # Process the GPT response
        if reply:
            results.append(reply)
    except Exception as e:
        print(f"Error processing article: {article['title']} | {e}")

# Ensure the output directory exists
output_dir = "reports"
os.makedirs(output_dir, exist_ok=True)

# Define the output path and write the results to the Markdown file
today = datetime.now().strftime("%Y-%m-%d")
output_path = f"{output_dir}/casting_report_{today}.md"

with open(output_path, "w") as f:
    f.write("# Daily Casting Report\n\n")
    for result in results:
        f.write(f"## {result}\n\n")

print(f"✅ Report generated: {output_path}")
