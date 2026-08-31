import os
import re
import json
import time
import feedparser

from datetime import datetime, timezone, timedelta
from google import genai


# ============================================================
# GLOBAL AI INTELLIGENCE ENGINE
# ============================================================

SOURCE_FILE = "sources.json"

LOOKBACK_HOURS = 24
MAX_CANDIDATES = 30

GEMINI_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

GEMINI_MAX_RETRIES = 3


# ============================================================
# LOAD SOURCES
# ============================================================

def load_sources():

    with open(
        SOURCE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# PARSE DATE
# ============================================================

def parse_date(entry):

    for field in [
        "published_parsed",
        "updated_parsed"
    ]:

        parsed = entry.get(field)

        if parsed:

            try:

                return datetime(
                    *parsed[:6],
                    tzinfo=timezone.utc
                )

            except Exception:

                pass

    return None


# ============================================================
# CLEAN TEXT
# ============================================================

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


# ============================================================
# COLLECT NEWS
# ============================================================

def collect_news():

    sources = load_sources()

    all_news = []

    current_time = datetime.now(
        timezone.utc
    )

    cutoff_time = (
        current_time
        - timedelta(
            hours=LOOKBACK_HOURS
        )
    )

    print()

    print(
        "Looking for articles since:",
        cutoff_time
    )

    print()

    for category, category_sources in sources.items():

        for source_name, url in category_sources.items():

            print(
                f"Reading: {source_name}"
            )

            try:

                feed = feedparser.parse(
                    url
                )

                if (
                    feed.bozo
                    and not feed.entries
                ):

                    print(
                        "  ⚠️ Feed unavailable"
                    )

                    continue


                for entry in feed.entries[:20]:

                    title = entry.get(
                        "title",
                        ""
                    ).strip()

                    link = entry.get(
                        "link",
                        ""
                    ).strip()

                    summary = clean_text(
                        entry.get(
                            "summary",
                            ""
                        )
                    )

                    if not title or not link:

                        continue


                    published_date = parse_date(
                        entry
                    )

                    if published_date is None:

                        continue


                    if published_date < cutoff_time:

                        continue


                    all_news.append({

                        "category": category,

                        "source": source_name,

                        "title": title,

                        "link": link,

                        "summary": summary,

                        "published":
                            published_date.isoformat()

                    })


            except Exception as error:

                print(
                    f"  ❌ Error reading "
                    f"{source_name}: {error}"
                )


    return all_news


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(news):

    seen = set()

    unique_news = []

    for item in news:

        normalized = (
            item["title"]
            .lower()
        )

        normalized = re.sub(
            r"[^a-z0-9 ]",
            "",
            normalized
        )

        normalized = normalized.replace(
            " ",
            ""
        )

        if normalized in seen:

            continue

        seen.add(
            normalized
        )

        unique_news.append(
            item
        )


    return unique_news


# ============================================================
# IMPORTANCE KEYWORDS
# ============================================================

KEYWORDS = {

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
    "regulatory": 6,

    "security": 5,
    "cybersecurity": 5,

    "breakthrough": 6,

    "research": 3,

    "india": 5,
    "indian": 5
}


# ============================================================
# SOURCE IMPORTANCE
# ============================================================

SOURCE_POINTS = {

    "OpenAI": 8,
    "Google AI": 7,
    "Google DeepMind": 8,
    "Google Research": 6,

    "Microsoft AI": 7,
    "Microsoft Research": 7,

    "NVIDIA": 8,
    "NVIDIA Developer": 7,

    "Anthropic": 8,

    "TechCrunch AI": 5,

    "MIT Technology Review AI": 6,

    "VentureBeat": 5,

    "The Decoder": 5,

    "Ars Technica": 5,

    "The Verge AI": 5,

    "Hugging Face": 6,

    "arXiv AI": 3,

    "Apple Machine Learning": 6,

    "AWS AI": 6,

    "AMD": 6,

    "Intel AI": 6
}


# ============================================================
# CALCULATE SCORE
# ============================================================

def calculate_score(item):

    text = (
        item["title"]
        + " "
        + item["summary"]
    ).lower()

    score = 0

    for keyword, points in KEYWORDS.items():

        if keyword in text:

            score += points


    score += SOURCE_POINTS.get(
        item["source"],
        0
    )


    return score


# ============================================================
# RANK NEWS
# ============================================================

def rank_news(news):

    for item in news:

        item["score"] = calculate_score(
            item
        )


    news.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    return news


# ============================================================
# GEMINI ANALYSIS
# ============================================================

def analyze_with_gemini(news):

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GEMINI_API_KEY was not found."
        )


    print()
    print("=" * 80)
    print("CONNECTING TO GEMINI")
    print("=" * 80)
    print()


    client = genai.Client(
        api_key=api_key
    )


    stories = []


    for number, item in enumerate(
        news,
        start=1
    ):

        stories.append(

            f"""
STORY {number}

Title:
{item['title']}

Source:
{item['source']}

Published:
{item['published']}

Summary:
{item['summary']}

Link:
{item['link']}
"""
        )


    news_text = "\n".join(
        stories
    )


    prompt = f"""

You are a senior GLOBAL AI INTELLIGENCE analyst.

Analyze the following recent AI news.

Select the 10 to 15 MOST IMPORTANT stories.

Do NOT simply follow the preliminary score.

Evaluate:

1. Global AI significance
2. Business impact
3. Technology impact
4. AI industry impact
5. Potential disruption
6. New AI model launches
7. AI agents
8. AI infrastructure
9. AI chips
10. Robotics
11. AI research
12. AI regulation
13. AI safety/security
14. Funding/acquisitions
15. India relevance

IMPORTANT:

Remove stories that are:

- General technology news
- Gaming news unrelated to AI
- Politics unrelated to AI
- Minor product updates
- Promotional announcements with little significance
- Low-impact research papers

If multiple articles discuss the SAME event,
combine them into ONE story.

Prioritize major developments over quantity.

IMPORTANT ACCURACY RULES:

- Do NOT invent facts.
- Do NOT invent numbers.
- Do NOT invent companies.
- Do NOT invent events.
- Only use information contained in the supplied stories.
- Preserve the original source and source link.
- If a story contains uncertain claims, describe them carefully.
- Do not present speculation as confirmed fact.

For every selected story provide:

headline
what_happened
why_it_matters
business_impact
category
source
source_link

Categories must be one of:

AI Models
AI Agents
AI Infrastructure
AI Chips
AI Research
Robotics
AI Business
AI Regulation
AI Safety
India AI
Enterprise AI

Also provide:

overall_ai_trend
india_watch
business_takeaway

Return ONLY valid JSON.

Do not use markdown.

Use exactly this structure:

{{
    "top_stories": [
        {{
            "headline": "",
            "what_happened": "",
            "why_it_matters": "",
            "business_impact": "",
            "category": "",
            "source": "",
            "source_link": ""
        }}
    ],
    "overall_ai_trend": "",
    "india_watch": "",
    "business_takeaway": ""
}}

RECENT AI NEWS:

{news_text}

"""


    # ========================================================
    # TRY GEMINI MODELS
    # ========================================================

    last_error = None


    for model in GEMINI_MODELS:

        print()

        print(
            f"Trying Gemini model: {model}"
        )


        for attempt in range(
            1,
            GEMINI_MAX_RETRIES + 1
        ):

            try:

                print(
                    f"Attempt {attempt}/"
                    f"{GEMINI_MAX_RETRIES}"
                )


                response = client.models.generate_content(

                    model=model,

                    contents=prompt
                )


                result_text = response.text.strip()


                # =================================================
                # REMOVE MARKDOWN FENCES
                # =================================================

                if result_text.startswith(
                    "```json"
                ):

                    result_text = result_text[7:]


                elif result_text.startswith(
                    "```"
                ):

                    result_text = result_text[3:]


                if result_text.endswith(
                    "```"
                ):

                    result_text = result_text[:-3]


                result_text = result_text.strip()


                # =================================================
                # PARSE JSON
                # =================================================

                try:

                    result = json.loads(
                        result_text
                    )


                    if not isinstance(
                        result,
                        dict
                    ):

                        raise ValueError(
                            "Gemini response "
                            "was not a JSON object."
                        )


                    if "top_stories" not in result:

                        raise ValueError(
                            "Gemini response "
                            "does not contain "
                            "top_stories."
                        )


                    print()

                    print(
                        "✅ Gemini analysis "
                        "successful using",
                        model
                    )

                    return result


                except (
                    json.JSONDecodeError,
                    ValueError
                ) as json_error:

                    print()

                    print(
                        "⚠️ Gemini returned "
                        "invalid JSON."
                    )

                    print(
                        "Trying again..."
                    )

                    last_error = json_error


            except Exception as error:

                error_text = str(error)

                last_error = error


                print()

                print(
                    "⚠️ Gemini error:",
                    error_text
                )


                # =================================================
                # TEMPORARY 503 ERROR
                # =================================================

                if (
                    "503" in error_text
                    or
                    "UNAVAILABLE" in error_text
                    or
                    "high demand" in error_text
                    or
                    "temporarily unavailable"
                    in error_text.lower()
                ):

                    print()

                    print(
                        "⚠️ Gemini is temporarily "
                        "unavailable."
                    )


                    if attempt < GEMINI_MAX_RETRIES:

                        wait_seconds = (
                            attempt * 10
                        )


                        print(
                            f"Waiting "
                            f"{wait_seconds} seconds "
                            f"before retry..."
                        )


                        time.sleep(
                            wait_seconds
                        )


                    continue


                # =================================================
                # RATE LIMIT
                # =================================================

                if (
                    "429" in error_text
                    or
                    "RESOURCE_EXHAUSTED"
                    in error_text
                ):

                    print()

                    print(
                        "⚠️ Gemini rate limit "
                        "reached."
                    )


                    if attempt < GEMINI_MAX_RETRIES:

                        wait_seconds = (
                            attempt * 15
                        )


                        print(
                            f"Waiting "
                            f"{wait_seconds} seconds..."
                        )


                        time.sleep(
                            wait_seconds
                        )


                    continue


                # =================================================
                # OTHER ERROR
                # =================================================

                print()

                print(
                    "⚠️ Non-retryable "
                    "Gemini error."
                )

                break


        print()

        print(
            f"⚠️ Model {model} failed."
        )

        print(
            "Trying next Gemini model..."
        )


    # ========================================================
    # ALL MODELS FAILED
    # ========================================================

    print()

    print("=" * 80)

    print(
        "❌ GEMINI ANALYSIS FAILED"
    )

    print("=" * 80)

    print()

    print(
        "All configured Gemini models "
        "were unavailable."
    )

    print()

    raise RuntimeError(
        f"Gemini analysis failed: {last_error}"
    )


# ============================================================
# PRINT GEMINI RESULTS
# ============================================================

def print_gemini_results(result):

    stories = result.get(
        "top_stories",
        []
    )


    print()

    print("=" * 80)

    print(
        f"TOP {len(stories)} AI STORIES"
    )

    print("=" * 80)

    print()


    for number, story in enumerate(
        stories,
        start=1
    ):

        print(
            f"{number}. "
            f"{story.get('headline', '')}"
        )

        print()

        print(
            "   Category:",
            story.get(
                "category",
                ""
            )
        )

        print()

        print(
            "   What happened:"
        )

        print(
            "   ",
            story.get(
                "what_happened",
                ""
            )
        )

        print()

        print(
            "   Why it matters:"
        )

        print(
            "   ",
            story.get(
                "why_it_matters",
                ""
            )
        )

        print()

        print(
            "   Business impact:"
        )

        print(
            "   ",
            story.get(
                "business_impact",
                ""
            )
        )

        print()

        print(
            "   Source:",
            story.get(
                "source",
                ""
            )
        )

        print()

        print(
            "   Link:",
            story.get(
                "source_link",
                ""
            )
        )

        print()

        print("-" * 80)


    print()

    print(
        "OVERALL AI TREND:"
    )

    print(
        result.get(
            "overall_ai_trend",
            ""
        )
    )


    print()

    print(
        "INDIA WATCH:"
    )

    print(
        result.get(
            "india_watch",
            ""
        )
    )


    print()

    print(
        "BUSINESS TAKEAWAY:"
    )

    print(
        result.get(
            "business_takeaway",
            ""
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)

    print(
        "GLOBAL AI INTELLIGENCE ENGINE"
    )

    print("=" * 80)

    print()


    print(
        "Current time:",
        datetime.now(
            timezone.utc
        )
    )

    print()


    # ========================================================
    # STEP 1 - COLLECT NEWS
    # ========================================================

    news = collect_news()


    print()

    print(
        "Recent stories collected:",
        len(news)
    )


    # ========================================================
    # STEP 2 - REMOVE DUPLICATES
    # ========================================================

    news = remove_duplicates(
        news
    )


    print(
        "After duplicate removal:",
        len(news)
    )


    # ========================================================
    # STEP 3 - RANK
    # ========================================================

    news = rank_news(
        news
    )


    candidates = news[
        :MAX_CANDIDATES
    ]


    print(
        f"Candidates sent to Gemini: "
        f"{len(candidates)}"
    )


    # ========================================================
    # STEP 4 - GEMINI
    # ========================================================

    if not candidates:

        print()

        print(
            "⚠️ No recent AI stories found."
        )

        return


    result = analyze_with_gemini(
        candidates
    )


    # ========================================================
    # STEP 5 - DISPLAY
    # ========================================================

    print_gemini_results(
        result
    )


    print()

    print("=" * 80)

    print(
        "GEMINI ANALYSIS COMPLETE"
    )

    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
