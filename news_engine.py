import json
import feedparser
import re
from datetime import datetime, timezone, timedelta


SOURCE_FILE = "sources.json"

LOOKBACK_HOURS = 24
MAX_AI_ARTICLES = 30


# ---------------------------------------------------------
# LOAD SOURCES
# ---------------------------------------------------------

def load_sources():

    with open(SOURCE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------
# PARSE PUBLICATION DATE
# ---------------------------------------------------------

def parse_date(entry):

    # RSS feeds normally provide published_parsed
    # or updated_parsed.

    if entry.get("published_parsed"):

        try:

            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            )

        except Exception:
            pass


    if entry.get("updated_parsed"):

        try:

            return datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            )

        except Exception:
            pass


    return None


# ---------------------------------------------------------
# COLLECT NEWS
# ---------------------------------------------------------

def collect_news():

    sources = load_sources()

    all_news = []

    current_time = datetime.now(timezone.utc)

    cutoff_time = (
        current_time
        - timedelta(hours=LOOKBACK_HOURS)
    )

    print()
    print(
        f"Looking for articles since: "
        f"{cutoff_time}"
    )

    print()

    for category, category_sources in sources.items():

        for source_name, url in category_sources.items():

            print(f"Reading: {source_name}")

            try:

                feed = feedparser.parse(url)

                if feed.bozo and not feed.entries:

                    print(
                        "  ⚠️ Feed unavailable"
                    )

                    continue


                for entry in feed.entries[:15]:

                    title = entry.get(
                        "title",
                        ""
                    ).strip()

                    link = entry.get(
                        "link",
                        ""
                    ).strip()

                    summary = entry.get(
                        "summary",
                        ""
                    ).strip()


                    if not title or not link:

                        continue


                    published_date = parse_date(
                        entry
                    )


                    # Ignore articles where
                    # publication date cannot
                    # be determined.

                    if published_date is None:

                        continue


                    # IMPORTANT:
                    # Ignore old articles.

                    if published_date < cutoff_time:

                        continue


                    all_news.append({

                        "category": category,

                        "source": source_name,

                        "title": title,

                        "link": link,

                        "summary": summary,

                        "published": published_date.isoformat()

                    })


            except Exception as error:

                print(
                    f"  ❌ Error reading "
                    f"{source_name}: {error}"
                )


    return all_news


# ---------------------------------------------------------
# CLEAN TEXT
# ---------------------------------------------------------

def clean_text(text):

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ---------------------------------------------------------
# REMOVE DUPLICATES
# ---------------------------------------------------------

def remove_duplicates(news):

    seen = set()

    unique_news = []

    for item in news:

        title = item["title"].lower()

        title = re.sub(
            r"[^a-z0-9 ]",
            "",
            title
        )

        title = title.replace(
            " ",
            ""
        )


        if title in seen:

            continue


        seen.add(title)

        unique_news.append(item)


    return unique_news


# ---------------------------------------------------------
# IMPORTANCE KEYWORDS
# ---------------------------------------------------------

IMPORTANT_KEYWORDS = {

    "launch": 5,
    "launched": 5,
    "released": 5,
    "release": 5,

    "model": 4,
    "models": 4,

    "acquisition": 7,
    "acquires": 7,
    "acquired": 7,

    "funding": 6,
    "investment": 6,

    "billion": 6,
    "million": 3,

    "partnership": 4,

    "chip": 5,
    "chips": 5,
    "gpu": 5,

    "nvidia": 6,

    "openai": 6,
    "anthropic": 6,
    "google": 5,
    "gemini": 6,
    "microsoft": 5,
    "meta": 5,
    "deepmind": 6,

    "agent": 5,
    "agents": 5,

    "robot": 4,
    "robotics": 4,

    "regulation": 6,
    "law": 5,
    "government": 4,

    "security": 5,
    "cybersecurity": 5,

    "breakthrough": 6,

    "research": 3
}


# ---------------------------------------------------------
# IMPORTANT SOURCES
# ---------------------------------------------------------

IMPORTANT_SOURCES = {

    "OpenAI": 8,
    "Google AI": 7,
    "Google DeepMind": 8,

    "Microsoft AI": 7,

    "NVIDIA": 8,

    "TechCrunch AI": 5,

    "MIT Technology Review AI": 6,

    "Reuters": 9,

    "Financial Times AI": 9,

    "Anthropic": 8
}


# ---------------------------------------------------------
# CALCULATE SCORE
# ---------------------------------------------------------

def calculate_score(item):

    score = 0

    title = item["title"].lower()

    summary = clean_text(
        item["summary"]
    ).lower()

    combined_text = (
        title
        + " "
        + summary
    )


    # Keyword score

    for keyword, points in IMPORTANT_KEYWORDS.items():

        if keyword in combined_text:

            score += points


    # Source score

    source = item["source"]

    score += IMPORTANT_SOURCES.get(
        source,
        0
    )


    # Small title quality bonus

    if len(item["title"]) < 120:

        score += 1


    return score


# ---------------------------------------------------------
# RANK
# ---------------------------------------------------------

def rank_news(news):

    for item in news:

        item["importance_score"] = (
            calculate_score(item)
        )


    news.sort(

        key=lambda x:
        x["importance_score"],

        reverse=True

    )


    return news


# ---------------------------------------------------------
# SELECT TOP NEWS
# ---------------------------------------------------------

def select_top_news(news):

    return news[
        :MAX_AI_ARTICLES
    ]


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print("=" * 80)

    print(
        "GLOBAL AI INTELLIGENCE ENGINE"
    )

    print("=" * 80)

    print()

    print(
        "Current time:",
        datetime.now(timezone.utc)
    )

    print()


    # 1. Collect recent news

    news = collect_news()


    print()

    print(
        f"Recent stories collected: "
        f"{len(news)}"
    )


    # 2. Clean summaries

    for item in news:

        item["summary"] = clean_text(
            item["summary"]
        )


    # 3. Remove duplicates

    news = remove_duplicates(
        news
    )


    print(
        f"After duplicate removal: "
        f"{len(news)}"
    )


    # 4. Rank

    news = rank_news(
        news
    )


    # 5. Select top 30

    top_news = select_top_news(
        news
    )


    print()

    print("=" * 80)

    print(
        f"TOP {len(top_news)} RECENT AI STORIES"
    )

    print("=" * 80)

    print()


    for number, item in enumerate(
        top_news,
        start=1
    ):

        print(
            f"{number}. "
            f"{item['title']}"
        )

        print(
            f"   Source: "
            f"{item['source']}"
        )

        print(
            f"   Published: "
            f"{item['published']}"
        )

        print(
            f"   Score: "
            f"{item['importance_score']}"
        )

        print(
            f"   Link: "
            f"{item['link']}"
        )

        print()


    print("=" * 80)

    print(
        "Ready for Gemini AI analysis."
    )

    print("=" * 80)


if __name__ == "__main__":

    main()
