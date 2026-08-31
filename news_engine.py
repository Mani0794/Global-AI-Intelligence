import json
import feedparser
from datetime import datetime, timezone


SOURCE_FILE = "sources.json"


def load_sources():
    with open(SOURCE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def collect_news():
    sources = load_sources()
    all_news = []

    for category, category_sources in sources.items():

        for source_name, url in category_sources.items():

            print(f"Reading: {source_name}")

            try:
                feed = feedparser.parse(url)

                if feed.bozo and not feed.entries:
                    print(f"  ⚠️ Feed unavailable")
                    continue

                for entry in feed.entries[:10]:

                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()

                    if not title or not link:
                        continue

                    published = (
                        entry.get("published")
                        or entry.get("updated")
                        or ""
                    )

                    summary = entry.get("summary", "").strip()

                    all_news.append({
                        "category": category,
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "published": published,
                        "summary": summary
                    })

            except Exception as error:

                print(
                    f"  ❌ Error reading "
                    f"{source_name}: {error}"
                )

    return all_news


def remove_duplicates(news):

    seen_titles = set()
    unique_news = []

    for item in news:

        normalized_title = (
            item["title"]
            .lower()
            .replace(" ", "")
            .replace("-", "")
            .replace(":", "")
        )

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)
        unique_news.append(item)

    return unique_news


def main():

    print("=" * 80)
    print("GLOBAL AI INTELLIGENCE ENGINE")
    print("=" * 80)

    print(
        f"Run time: "
        f"{datetime.now(timezone.utc)} UTC"
    )

    print()

    news = collect_news()

    print()
    print(f"Stories collected: {len(news)}")

    news = remove_duplicates(news)

    print(
        f"Stories after duplicate removal: "
        f"{len(news)}"
    )

    print()
    print("=" * 80)
    print("LATEST AI NEWS")
    print("=" * 80)

    for number, item in enumerate(news, start=1):

        print()
        print(f"{number}. {item['title']}")
        print(f"   Source: {item['source']}")
        print(f"   Category: {item['category']}")
        print(f"   Published: {item['published']}")
        print(f"   Link: {item['link']}")


if __name__ == "__main__":
    main()
