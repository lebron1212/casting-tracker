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

# GPT prompt logic
prompt_template = """
You are a casting tracker. Your job is to extract casting attachments for actors with the following fame scores:

- **Tier A actors**: Fame score of at least **8** (high name recognition, long career, prestigious awards, etc.)
- **Tier B actors**: Fame score of at least **6.5** (trendiness, rising stars, good industry buzz)
- **Tier C actors**: Fame score lower than **6.4** (lesser-known, emerging actors) – **DO NOT include these actors under any circumstances!**

You are to list the actors, the project title, and generate a short industry tag, using the following rules.

List **all Tier A actors first**! If there are Tier A actors, list only those and **no others**. If there are no Tier A actors, you may include **1 Tier B actor** with the highest fame score, but **do not include more than 1 Tier B actor** in any listing. There should **never be more than 2 actors listed**, unless all of them are **Tier A**.

Return only in this format:

ATTACHED: Actor Name(s). PROJECT TITLE (SHORT INDUSTRY TAG).

Rules:
- **DO NOT include any Tier C actors**.
- End actor list with a period.
- Project title in ALL CAPS.
- Descriptor in ALL CAPS, ≤ 27 characters, industry-abbreviated (e.g., SQL TO $300M BO HIT, MCU PH4).
- End the entire line with a period.
- No commentary, labels, fame scores, or source links. The output should match exactly this format: ATTACHED: Actor Name(s). PROJECT TITLE (SHORT INDUSTRY TAG).

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

        # Post-process the GPT response to ensure proper formatting
        if not reply.startswith("SKIP"):
            # Extract actor names and split them into a list
            actors_start = reply.find("ATTACHED:") + len("ATTACHED: ")
            actors_end = reply.find(".", actors_start)
            actors_str = reply[actors_start:actors_end].strip()

            if not actors_str:
                actors_str = "UNKNOWN ACTORS"  # Set a default if actors list is empty

            actors_list = [actor.strip() for actor in actors_str.split(",")]

            # Define Tier A and Tier B actors (example list)
            A_TIER_ACTORS = ["Billy Eichner", "Will Ferrell", "Zac Efron", "Regina Hall", "Josh Brolin", "Max Irons"]
            B_TIER_ACTORS = ["Kyle Chandler", "Aaron Pierre", "Garret Dillahunt", "Poorna Jagannathan", "Jasmine Cephas Jones", "Ulrich Thomsen"]

            # Filter out Tier C actors and ensure only Tier A or Tier B actors are included
            valid_actors = [actor for actor in actors_list if actor in A_TIER_ACTORS or actor in B_TIER_ACTORS]

            # If there are more than 2 A-tier actors, list them all, else list up to 2
            a_tier_actors = [actor for actor in valid_actors if actor in A_TIER_ACTORS]
            if len(a_tier_actors) > 2:
                filtered_actors = a_tier_actors
            else:
                filtered_actors = a_tier_actors[:2]  # Limit to 2 if more than 2 A-tier actors

            # Ensure we only have 1 B-tier actor, but if no A-tier actors exist, include the highest ranked B-tier actor
            if len(a_tier_actors) == 0 and len(filtered_actors) < 2:
                b_tier_actors = [actor for actor in valid_actors if actor in B_TIER_ACTORS]
                filtered_actors.append(b_tier_actors[0] if b_tier_actors else "")

            # Properly handle project title, remove any unwanted formatting
            title_str = article["title"].strip().upper()  # Ensure title is clean and uppercased
            if not title_str:
                title_str = "UNKNOWN PROJECT TITLE"  # Handle missing titles

            # Remove extraneous " . ." if present
            filtered_reply = f"ATTACHED: {', '.join(filtered_actors)}. {title_str} ({article['summary'][:27].upper()})"

            results.append(f"{filtered_reply} – [Source]({article['link']})")
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
