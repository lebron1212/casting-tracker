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
        published = entry.get("published", "")  # Fetching published time
        if title not in seen_titles:
            seen_titles.add(title)
            articles.append({"title": title, "link": link, "summary": summary, "published": published})

# Function to convert the published time to a readable format
def get_readable_published_time(published_str):
    try:
        # Parse the published time into a datetime object using feedparser
        parsed_time = feedparser.parse(published_str)
        # Extract the full date and time as available
        published_time = datetime(*parsed_time['published_parsed'][:6])  # Convert the parsed time tuple to datetime
        
        # Fallback to just hour and date if minutes or seconds are missing
        if len(parsed_time['published_parsed']) < 6:
            return published_time.strftime("%Y-%m-%d %H:00")  # Fallback to hour-only format
        return published_time.strftime("%Y-%m-%d %H:%M:%S")  # Full format with minutes and seconds
    except Exception as e:
        print(f"Error parsing published date: {e}")
        return "Unknown"

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
Article Posted: {posted_time}.

---

Title: {title}
Summary: {summary}
"""

# Process each article using GPT to extract actors, project titles, and industry tags
results = []

for article in articles:
    # Get the exact published time of the article
    posted_time = get_readable_published_time(article['published'])

    # Extract actors from the article title
    a_tier_actors = [actor for actor in A_TIER_ACTORS if actor in article['title']]
    b_tier_actors = [actor for actor in B_TIER_ACTORS if actor in article['title']]

    # Assign industry tag (this is hardcoded for simplicity, you can adjust this logic based on content)
    industry_tag = "NTFLX CRIME DRAMA"  # Example industry tag; you can modify this logic based on article content

    # Ask GPT to extract the project title from the article's title and summary
    prompt = prompt_template.format(
        title=article['title'],
        summary=article['summary'],
        a_tier_actors=", ".join(a_tier_actors),
        b_tier_actors=", ".join(b_tier_actors),
        industry_tag=industry_tag,
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
