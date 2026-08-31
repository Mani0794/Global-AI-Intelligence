import os
import re
import json
import html
import feedparser

from datetime import datetime, timezone, timedelta
from google import genai


# ============================================================
# GLOBAL AI INTELLIGENCE ENGINE
# ============================================================

SOURCE_FILE = "sources.json"

LOOKBACK_HOURS = 24

MAX_CANDIDATES = 30

FINAL_STORIES = 15

GEMINI_MODEL = "gemini-3.7-flash"

HTML_OUTPUT_FILE = "ai_news_email.html"


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

    text = html.unescape(text)

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


                    # ONLY RECENT NEWS

                    if published_date < cutoff_time:

                        continue


                    all_news.append({

                        "category": category,

                        "source": source_name,

                        "title": title,

                        "link": link,

                        "summary": summary,

                        "published": (
                            published_date.isoformat()
                        )

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
# PRELIMINARY IMPORTANCE SCORE
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


SOURCE_POINTS = {

    "OpenAI": 8,

    "Google AI": 7,

    "Google DeepMind": 8,

    "Microsoft AI": 7,

    "NVIDIA": 8,

    "TechCrunch AI": 5,

    "MIT Technology Review AI": 6,

    "Anthropic": 8
}


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

IMPORTANT:

Use only information supported by the supplied news.

Do not invent facts.

Return ONLY valid JSON.

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


    response = client.models.generate_content(

        model=GEMINI_MODEL,

        contents=prompt
    )


    result_text = response.text.strip()


    # --------------------------------------------------------
    # REMOVE MARKDOWN JSON FENCES
    # --------------------------------------------------------

    if result_text.startswith(
        "```json"
    ):

        result_text = result_text[
            7:
        ]


    if result_text.startswith(
        "```"
    ):

        result_text = result_text[
            3:
        ]


    if result_text.endswith(
        "```"
    ):

        result_text = result_text[
            :-3
        ]


    result_text = result_text.strip()


    try:

        result = json.loads(
            result_text
        )

    except json.JSONDecodeError:

        print()

        print(
            "❌ Gemini returned invalid JSON"
        )

        print()

        print(
            result_text
        )

        raise


    return result


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
# CREATE HTML EMAIL
# ============================================================

def create_html_email(result):

    stories = result.get(
        "top_stories",
        []
    )


    html_content = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>
Global AI Intelligence Brief
</title>

<style>

body {

    margin: 0;

    padding: 0;

    background: #f3f4f6;

    font-family:
    Arial,
    Helvetica,
    sans-serif;

    color: #1f2937;

}

.container {

    max-width: 900px;

    margin: 20px auto;

    background: #ffffff;

    padding: 30px;

}

.header {

    background:
    linear-gradient(
        135deg,
        #111827,
        #374151
    );

    color: white;

    padding: 30px;

    border-radius: 10px;

    margin-bottom: 25px;

}

.header h1 {

    margin: 0;

    font-size: 28px;

}

.header p {

    margin: 8px 0 0 0;

    color: #d1d5db;

    font-size: 14px;

}

.story {

    border: 1px solid #e5e7eb;

    border-radius: 10px;

    padding: 20px;

    margin-bottom: 18px;

    background: #ffffff;

}

.story-number {

    font-size: 12px;

    font-weight: bold;

    color: #6b7280;

    text-transform: uppercase;

}

.story h2 {

    margin: 8px 0 12px 0;

    font-size: 20px;

    line-height: 1.4;

    color: #111827;

}

.category {

    display: inline-block;

    background: #eef2ff;

    color: #3730a3;

    padding: 5px 10px;

    border-radius: 20px;

    font-size: 12px;

    font-weight: bold;

}

.section-title {

    margin-top: 16px;

    margin-bottom: 5px;

    font-size: 14px;

    font-weight: bold;

    color: #111827;

}

.section-text {

    font-size: 14px;

    line-height: 1.65;

    color: #4b5563;

}

.source {

    margin-top: 18px;

    font-size: 12px;

    color: #6b7280;

}

.read-more {

    display: inline-block;

    margin-top: 10px;

    padding: 9px 15px;

    background: #2563eb;

    color: #ffffff !important;

    text-decoration: none;

    border-radius: 6px;

    font-size: 12px;

    font-weight: bold;

}

.summary-box {

    margin-top: 25px;

    padding: 22px;

    background: #f9fafb;

    border: 1px solid #e5e7eb;

    border-radius: 10px;

}

.summary-box h2 {

    margin-top: 0;

    color: #111827;

    font-size: 20px;

}

.summary-section {

    margin-top: 22px;

}

.summary-section h3 {

    font-size: 15px;

    margin-bottom: 6px;

    color: #111827;

}

.summary-section p {

    font-size: 14px;

    line-height: 1.65;

    color: #4b5563;

}

.footer {

    text-align: center;

    margin-top: 30px;

    padding-top: 20px;

    border-top: 1px solid #e5e7eb;

    font-size: 11px;

    color: #9ca3af;

}

</style>

</head>


<body>


<div class="container">


<div class="header">

<h1>
🌎 Global AI Intelligence Brief
</h1>

<p>
Top AI developments from around the world
</p>

<p>
Generated:
"""

    html_content += datetime.now(
        timezone.utc
    ).strftime(
        "%d %b %Y, %H:%M UTC"
    )


    html_content += """

</p>

</div>

"""


    # ========================================================
    # STORIES
    # ========================================================

    for number, story in enumerate(
        stories,
        start=1
    ):

        headline = html.escape(
            str(
                story.get(
                    "headline",
                    ""
                )
            )
        )

        category = html.escape(
            str(
                story.get(
                    "category",
                    ""
                )
            )
        )

        what_happened = html.escape(
            str(
                story.get(
                    "what_happened",
                    ""
                )
            )
        )

        why_it_matters = html.escape(
            str(
                story.get(
                    "why_it_matters",
                    ""
                )
            )
        )

        business_impact = html.escape(
            str(
                story.get(
                    "business_impact",
                    ""
                )
            )
        )

        source = html.escape(
            str(
                story.get(
                    "source",
                    ""
                )
            )
        )

        link = html.escape(
            str(
                story.get(
                    "source_link",
                    "#"
                )
            ),
            quote=True
        )


        html_content += f"""

<div class="story">


<div class="story-number">

AI STORY #{number}

</div>


<h2>

{headline}

</h2>


<span class="category">

{category}

</span>


<div class="section-title">

What happened

</div>


<div class="section-text">

{what_happened}

</div>


<div class="section-title">

Why it matters

</div>


<div class="section-text">

{why_it_matters}

</div>


<div class="section-title">

Business impact

</div>


<div class="section-text">

{business_impact}

</div>


<div class="source">

Source:
<b>{source}</b>

</div>


<a

class="read-more"

href="{link}"

target="_blank"

rel="noopener">

Read Full Story →

</a>


</div>

"""


    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    overall_trend = html.escape(
        str(
            result.get(
                "overall_ai_trend",
                ""
            )
        )
    )

    india_watch = html.escape(
        str(
            result.get(
                "india_watch",
                ""
            )
        )
    )

    business_takeaway = html.escape(
        str(
            result.get(
                "business_takeaway",
                ""
            )
        )
    )


    html_content += f"""

<div class="summary-box">


<h2>

📊 Executive Intelligence Summary

</h2>


<div class="summary-section">

<h3>

🌐 Overall AI Trend

</h3>

<p>

{overall_trend}

</p>

</div>


<div class="summary-section">

<h3>

🇮🇳 India Watch

</h3>

<p>

{india_watch}

</p>

</div>


<div class="summary-section">

<h3>

💼 Business Takeaway

</h3>

<p>

{business_takeaway}

</p>

</div>


</div>


<div class="footer">

Global AI Intelligence Engine

<br>

Automated AI news intelligence

</div>


</div>


</body>

</html>

"""


    return html_content


# ============================================================
# SAVE HTML EMAIL
# ============================================================

def save_html_email(result):

    html_email = create_html_email(
        result
    )


    with open(
        HTML_OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            html_email
        )


    print()

    print(
        "=" * 80
    )

    print(
        "HTML EMAIL CREATED"
    )

    print(
        "=" * 80
    )

    print()

    print(
        "File:",
        HTML_OUTPUT_FILE
    )

    print()

    print(
        "Stories in email:",
        len(
            result.get(
                "top_stories",
                []
            )
        )
    )

    print()


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


    # --------------------------------------------------------
    # STEP 1
    # COLLECT NEWS
    # --------------------------------------------------------

    news = collect_news()


    print()

    print(
        "Recent stories collected:",
        len(news)
    )


    # --------------------------------------------------------
    # STEP 2
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    news = remove_duplicates(
        news
    )


    print(
        "After duplicate removal:",
        len(news)
    )


    # --------------------------------------------------------
    # STEP 3
    # RANK NEWS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # STEP 4
    # GEMINI ANALYSIS
    # --------------------------------------------------------

    if not candidates:

        print()

        print(
            "⚠️ No recent AI stories found."
        )

        return


    result = analyze_with_gemini(
        candidates
    )


    # --------------------------------------------------------
    # STEP 5
    # PRINT RESULTS
    # --------------------------------------------------------

    print_gemini_results(
        result
    )


    # --------------------------------------------------------
    # STEP 6
    # CREATE HTML EMAIL
    # --------------------------------------------------------

    save_html_email(
        result
    )


    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()

    print("=" * 80)

    print(
        "GEMINI ANALYSIS COMPLETE"
    )

    print("=" * 80)

    print()

    print(
        "News engine completed successfully."
    )

    print(
        f"HTML email saved as: "
        f"{HTML_OUTPUT_FILE}"
    )

    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
