import os
import re
import json
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

IST = timezone(timedelta(hours=5, minutes=30))


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
# RANK CANDIDATES
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

Categories should be one of:

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


    # Remove markdown fences if Gemini adds them

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

        print(
            result_text
        )

        raise


    return result


# ============================================================
# HTML HELPERS
# ============================================================

def html_escape(text):

    if text is None:
        return ""

    text = str(text)

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def get_edition():

    hour = datetime.now(
        IST
    ).hour

    if hour < 15:

        return "MORNING EDITION"

    return "EVENING EDITION"


# ============================================================
# GENERATE HTML EMAIL
# ============================================================

def generate_html_email(result):

    now_ist = datetime.now(
        IST
    )

    edition = get_edition()

    stories = result.get(
        "top_stories",
        []
    )


    story_blocks = []


    for number, story in enumerate(
        stories,
        start=1
    ):

        headline = html_escape(
            story.get(
                "headline",
                ""
            )
        )

        category = html_escape(
            story.get(
                "category",
                "AI"
            )
        )

        what_happened = html_escape(
            story.get(
                "what_happened",
                ""
            )
        )

        why_it_matters = html_escape(
            story.get(
                "why_it_matters",
                ""
            )
        )

        business_impact = html_escape(
            story.get(
                "business_impact",
                ""
            )
        )

        source = html_escape(
            story.get(
                "source",
                ""
            )
        )

        source_link = html_escape(
            story.get(
                "source_link",
                "#"
            )
        )


        block = f"""
        <div style="
            background:#ffffff;
            border:1px solid #e5e7eb;
            border-radius:12px;
            margin:0 0 18px 0;
            padding:22px;
        ">

            <div style="
                font-size:13px;
                font-weight:bold;
                color:#2563eb;
                margin-bottom:8px;
            ">
                #{number} &nbsp; | &nbsp; {category}
            </div>

            <div style="
                font-size:20px;
                line-height:1.35;
                font-weight:700;
                color:#111827;
                margin-bottom:12px;
            ">
                {headline}
            </div>

            <div style="
                font-size:13px;
                color:#6b7280;
                margin-bottom:16px;
            ">
                Source: {source}
            </div>

            <div style="
                font-size:14px;
                line-height:1.65;
                color:#374151;
                margin-bottom:14px;
            ">
                <strong>What happened</strong><br>
                {what_happened}
            </div>

            <div style="
                font-size:14px;
                line-height:1.65;
                color:#374151;
                margin-bottom:14px;
            ">
                <strong>Why it matters</strong><br>
                {why_it_matters}
            </div>

            <div style="
                background:#f3f4f6;
                border-radius:8px;
                padding:12px 14px;
                font-size:14px;
                line-height:1.6;
                color:#374151;
                margin-bottom:16px;
            ">
                <strong>💼 Business impact</strong><br>
                {business_impact}
            </div>

            <a href="{source_link}"
               style="
                   display:inline-block;
                   background:#2563eb;
                   color:#ffffff;
                   text-decoration:none;
                   padding:10px 16px;
                   border-radius:7px;
                   font-size:13px;
                   font-weight:bold;
               ">
                Read original source →
            </a>

        </div>
        """

        story_blocks.append(
            block
        )


    stories_html = "\n".join(
        story_blocks
    )


    overall_trend = html_escape(
        result.get(
            "overall_ai_trend",
            ""
        )
    )

    india_watch = html_escape(
        result.get(
            "india_watch",
            ""
        )
    )

    business_takeaway = html_escape(
        result.get(
            "business_takeaway",
            ""
        )
    )


    html = f"""<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width,
               initial-scale=1.0">

<title>
Global AI Intelligence
</title>

</head>


<body style="
    margin:0;
    padding:0;
    background:#f3f4f6;
    font-family:Arial,
                 Helvetica,
                 sans-serif;
">


<table width="100%"
       cellpadding="0"
       cellspacing="0"
       style="
           background:#f3f4f6;
           padding:25px 10px;
       ">

<tr>

<td align="center">


<table width="700"
       cellpadding="0"
       cellspacing="0"
       style="
           max-width:700px;
           width:100%;
       ">


<!-- HEADER -->

<tr>

<td style="
    background:#111827;
    color:#ffffff;
    border-radius:14px 14px 0 0;
    padding:30px 25px;
">

<div style="
    font-size:12px;
    font-weight:bold;
    letter-spacing:1.5px;
    color:#93c5fd;
    margin-bottom:8px;
">
GLOBAL AI INTELLIGENCE
</div>


<div style="
    font-size:28px;
    font-weight:700;
    line-height:1.25;
">
AI News Briefing
</div>


<div style="
    font-size:14px;
    color:#d1d5db;
    margin-top:10px;
">
{edition}
&nbsp; • &nbsp;
{now_ist.strftime("%d %B %Y")}
&nbsp; • &nbsp;
{now_ist.strftime("%I:%M %p")} IST
</div>

</td>

</tr>


<!-- INTRO -->

<tr>

<td style="
    background:#ffffff;
    padding:25px;
">

<div style="
    font-size:15px;
    line-height:1.6;
    color:#374151;
">
Here are the most important AI developments
identified from global AI sources over the
last 24 hours and analyzed by Gemini.
</div>

</td>

</tr>


<!-- STORIES -->

<tr>

<td style="
    background:#f9fafb;
    padding:10px 15px 5px 15px;
">

<div style="
    font-size:18px;
    font-weight:700;
    color:#111827;
    padding:10px;
">
🔥 Top AI Developments
</div>

</td>

</tr>


<tr>

<td style="
    background:#f9fafb;
    padding:10px 15px 20px 15px;
">

{stories_html}

</td>

</tr>


<!-- OVERALL TREND -->

<tr>

<td style="
    background:#111827;
    color:#ffffff;
    padding:25px;
">

<div style="
    font-size:17px;
    font-weight:bold;
    margin-bottom:10px;
">
📈 Overall AI Trend
</div>

<div style="
    font-size:14px;
    line-height:1.7;
    color:#e5e7eb;
">
{overall_trend}
</div>

</td>

</tr>


<!-- INDIA WATCH -->

<tr>

<td style="
    background:#ffffff;
    padding:25px;
">

<div style="
    font-size:17px;
    font-weight:bold;
    color:#111827;
    margin-bottom:10px;
">
🇮🇳 India AI Watch
</div>

<div style="
    font-size:14px;
    line-height:1.7;
    color:#374151;
">
{india_watch}
</div>

</td>

</tr>


<!-- BUSINESS TAKEAWAY -->

<tr>

<td style="
    background:#eff6ff;
    padding:25px;
">

<div style="
    font-size:17px;
    font-weight:bold;
    color:#1e3a8a;
    margin-bottom:10px;
">
💼 Business Takeaway
</div>

<div style="
    font-size:14px;
    line-height:1.7;
    color:#374151;
">
{business_takeaway}
</div>

</td>

</tr>


<!-- FOOTER -->

<tr>

<td style="
    background:#ffffff;
    border-radius:0 0 14px 14px;
    padding:22px;
    text-align:center;
">

<div style="
    font-size:12px;
    color:#9ca3af;
    line-height:1.6;
">
Generated automatically by
<strong>Global AI Intelligence Engine</strong>
<br>
Sources: Global AI research, technology companies
and leading AI news publications.
</div>

</td>

</tr>


</table>


</td>

</tr>

</table>


</body>

</html>
"""


    return html


# ============================================================
# SAVE HTML EMAIL
# ============================================================

def save_html_email(result):

    html = generate_html_email(
        result
    )


    filename = "ai_briefing.html"


    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            html
        )


    print()
    print(
        "=" * 80
    )

    print(
        f"HTML EMAIL CREATED: {filename}"
    )

    print(
        "=" * 80
    )

    print()


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


    # --------------------------------------------------------
    # STEP 1: COLLECT
    # --------------------------------------------------------

    news = collect_news()


    print()

    print(
        "Recent stories collected:",
        len(news)
    )


    # --------------------------------------------------------
    # STEP 2: DUPLICATES
    # --------------------------------------------------------

    news = remove_duplicates(
        news
    )


    print(
        "After duplicate removal:",
        len(news)
    )


    # --------------------------------------------------------
    # STEP 3: RANK
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
    # STEP 4: GEMINI
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
    # STEP 5: DISPLAY
    # --------------------------------------------------------

    print_gemini_results(
        result
    )


    # --------------------------------------------------------
    # STEP 6: CREATE HTML EMAIL
    # --------------------------------------------------------

    save_html_email(
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
