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

# Function to extract project title from the article title and summary
def extract_project_title(title, summary):
    # Step 1: Extract from text inside single quotes (' ') or double quotes (" ")
    quote_pattern = r"['\"](.*?)['\"]"
    quotes_match = re.findall(quote_pattern, title + summary)

    if quotes_match:
        return quotes_match[0].strip()

    # Step 2: If no quotes are found, try extracting the most relevant project detail
    # Find key words like "project", "movie", "series", or names like "Scorsese", "Spielberg"
    fallback_keywords = ["project", "movie", "series", "film", "show"]
    for keyword in fallback_keywords:
        if keyword in title.lower():
            # Using the most relevant part (first few words) as the fallback title
            words = title.split()
            return "UNT " + " ".join(words[:5])  # Example: "UNT MARTIN SCORSESE MOVIE"

    # If still no match, return a generic UNT title
    return "UNT **BIG NAME MOVIE/SERIES PROJECT**"

# GPT prompt logic for extraction with Few-Shot Learning
few_shot_examples = """
1. Headline: Jennifer Lopez Reunites with Edward James Olmos in ‘Office Romance’ 28 Years After ‘Selena’
   Project Title: Office Romance
2. Headline: John Lithgow Cast as Albus Dumbledore in New ‘Harry Potter’ Series
   Project Title: Harry Potter (TV Series)
3. Headline: Matthew Lillard Joins ‘Daredevil: Born Again’ Season 2
   Project Title: Daredevil: Born Again
4. Headline: Bradley Whitford Joins ‘The Diplomat’ Season 3
   Project Title: The Diplomat
5. Headline: Jared Padalecki to Star in New CBS Medical Drama Set in Rural Texas
   Project Title: UNT CBS Medical Drama
6. Headline: Stephen Amell to Lead NBC’s ‘Suits’ Spinoff ‘Suits: LA’
   Project Title: Suits: LA
7. Headline: Tye Sheridan Joins Jude Law and Nicholas Hoult in ‘The Order’
   Project Title: The Order
8. Headline: André Holland and Gemma Chan to Star in ‘The Actor’
   Project Title: The Actor
9. Headline: Paapa Essiedu Nears Deal to Play Severus Snape in ‘Harry Potter’ Series
   Project Title: Harry Potter (TV Series)
10. Headline: Nick Frost Rumored to Portray Rubeus Hagrid in Upcoming ‘Harry Potter’ Series
    Project Title: Harry Potter (TV Series)
"""

prompt_template = f"""
You are a casting tracker. Your job is to extract casting attachments for actors with the following fame scores:

- **Tier A actors**: Fame score of at least **8** (high name recognition, long career, prestigious awards, etc.)
- **Tier B actors**: Fame score of at least **6.5** (trendiness, rising stars, good industry buzz)
- **Tier C actors**: Fame score lower than **6.4** (lesser-known, emerging actors) – **DO NOT include these actors under any circumstances!**

Please extract the project title from the following headlines, using the example patterns provided.

### Examples:
{few_shot_examples}

---

Title: {title}
Summary: {summary}

Extract the project title:
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

    # Extract the project title reliably using the function
    project_title = extract_project_title(article['title'], article['summary'])

    # Ask GPT to extract the project title from the article's title and summary
    prompt = prompt_template.format(
        title=project_title,
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
