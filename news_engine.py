import os
import re
import json
import html
import time
import smtplib
import urllib.request

import feedparser

from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai


# ============================================================
# SETTINGS
# ============================================================

SOURCE_FILE = "sources.json"

LOOKBACK_HOURS = 12
MAX_CANDIDATES = 30
FINAL_STORIES = 15
TOP_STORIES = 5

SOURCE_TIMEOUT_SECONDS = 10

HTML_OUTPUT_FILE = "ai_news_email.html"

GEMINI_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


# ============================================================
# LOAD SOURCES
# ============================================================

def load_sources():

    with open(
        SOURCE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    all_sources = []

    for category, sources in data.items():

        if not isinstance(sources, dict):
            continue

        for source_name, source_url in sources.items():

            all_sources.append(
                {
                    "name": source_name,
                    "url": source_url,
                    "priority": 1,
                    "category": category,
                }
            )

    if not all_sources:

        raise RuntimeError(
            "No valid sources found in sources.json."
        )

    print(
        f"Loaded {len(all_sources)} sources."
    )

    return all_sources


# ============================================================
# DATE HANDLING
# ============================================================

def parse_date(entry):

    date_struct = None

    if (
        hasattr(entry, "published_parsed")
        and entry.published_parsed
    ):

        date_struct = entry.published_parsed

    elif (
        hasattr(entry, "updated_parsed")
        and entry.updated_parsed
    ):

        date_struct = entry.updated_parsed

    if not date_struct:
        return None

    return datetime(
        *date_struct[:6],
        tzinfo=timezone.utc
    )


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):

    if not text:
        return ""

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
# DOWNLOAD RSS WITH TIMEOUT
# ============================================================

def download_feed(
    source_name,
    source_url
):

    try:

        request = urllib.request.Request(
            source_url,
            headers={
                "User-Agent":
                    "Mozilla/5.0 Global-AI-Intelligence/1.0",
                "Accept":
                    "application/rss+xml,"
                    "application/atom+xml,"
                    "application/xml,"
                    "text/xml,*/*",
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=SOURCE_TIMEOUT_SECONDS
        ) as response:

            feed_data = response.read()

        return feedparser.parse(
            feed_data
        )

    except Exception as error:

        print(
            f"⚠️ Skipping {source_name}: {error}",
            flush=True
        )

        return None


# ============================================================
# COLLECT NEWS
# ============================================================

def collect_news(sources):

    stories = []

    now = datetime.now(
        timezone.utc
    )

    cutoff = now - timedelta(
        hours=LOOKBACK_HOURS
    )

    print("\n" + "=" * 80)
    print("COLLECTING GLOBAL AI NEWS")
    print("=" * 80)

    for source in sources:

        source_name = source.get(
            "name",
            "Unknown"
        )

        source_url = source.get(
            "url"
        )

        priority = source.get(
            "priority",
            1
        )

        category = source.get(
            "category",
            "AI"
        )

        if not source_url:
            continue

        print(
            f"\nReading: {source_name}",
            flush=True
        )

        feed = download_feed(
            source_name,
            source_url
        )

        if feed is None:
            continue

        if not feed.entries:

            print(
                "  No feed entries found.",
                flush=True
            )

            continue

        source_count = 0

        for entry in feed.entries:

            try:

                published_date = parse_date(
                    entry
                )

                if not published_date:
                    continue

                if published_date < cutoff:
                    continue

                title = clean_text(
                    entry.get(
                        "title",
                        ""
                    )
                )

                summary = clean_text(
                    entry.get(
                        "summary",
                        entry.get(
                            "description",
                            ""
                        )
                    )
                )

                link = entry.get(
                    "link",
                    ""
                )

                if not title:
                    continue

                stories.append(
                    {
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "published":
                            published_date.isoformat(),
                        "priority": priority,
                        "source_category": category,
                    }
                )

                source_count += 1

            except Exception as error:

                print(
                    f"  Entry skipped: {error}",
                    flush=True
                )

        print(
            f"  Recent stories: {source_count}",
            flush=True
        )

    print("\n" + "=" * 80)

    print(
        f"TOTAL RECENT STORIES: "
        f"{len(stories)}"
    )

    print("=" * 80)

    return stories


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(stories):

    unique = []
    seen_titles = set()

    for story in stories:

        normalized = re.sub(
            r"[^a-z0-9]",
            "",
            story["title"].lower()
        )

        if not normalized:
            continue

        if normalized in seen_titles:
            continue

        seen_titles.add(
            normalized
        )

        unique.append(
            story
        )

    print(
        f"UNIQUE STORIES: {len(unique)}"
    )

    return unique


# ============================================================
# STORY SCORING
# ============================================================

def calculate_score(story):

    text = (
        story.get(
            "title",
            ""
        )
        + " "
        + story.get(
            "summary",
            ""
        )
    ).lower()

    score = (
        story.get(
            "priority",
            1
        )
        * 2
    )

    keywords = {

        "openai": 7,
        "anthropic": 7,
        "gemini": 7,
        "google deepmind": 7,
        "deepmind": 6,
        "microsoft": 5,
        "meta": 5,
        "nvidia": 7,
        "apple": 5,
        "amazon": 4,
        "aws": 4,
        "mistral": 5,
        "hugging face": 5,

        "agent": 6,
        "agents": 6,
        "agentic": 7,

        "robot": 5,
        "robotics": 6,

        "model": 4,
        "reasoning": 5,
        "multimodal": 5,

        "chip": 5,
        "gpu": 6,
        "infrastructure": 5,
        "data center": 5,

        "enterprise": 5,
        "business": 4,

        "safety": 5,
        "security": 5,

        "regulation": 6,
        "government": 4,

        "acquisition": 6,
        "investment": 5,
        "funding": 4,

        "india": 6,
        "indic": 6,

        "research": 4,
        "benchmark": 4,

        "launch": 4,
        "release": 4,
    }

    for keyword, points in keywords.items():

        if keyword in text:
            score += points

    return score


# ============================================================
# RANK NEWS
# ============================================================

def rank_news(stories):

    ranked = []

    for story in stories:

        new_story = story.copy()

        new_story["score"] = (
            calculate_score(
                story
            )
        )

        ranked.append(
            new_story
        )

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    candidates = ranked[
        :MAX_CANDIDATES
    ]

    print("\n" + "=" * 80)

    print(
        f"TOP {len(candidates)} CANDIDATES"
    )

    print("=" * 80)

    for index, story in enumerate(
        candidates,
        start=1
    ):

        print(
            f"{index}. "
            f"[{story['score']}] "
            f"{story['title']} "
            f"— {story['source']}"
        )

    return candidates


# ============================================================
# GEMINI ANALYSIS
# ============================================================

def analyze_with_gemini(
    candidates,
    api_key
):

    client = genai.Client(
        api_key=api_key
    )

    prompt = f"""
You are the editor of a premium executive AI intelligence newsletter.

Your readers are senior executives, finance leaders, business leaders,
strategy teams, technology leaders and AI professionals.

Analyze the AI news candidates below and select up to
{FINAL_STORIES} of the most important stories.

Rank the stories by real-world importance.

The FIRST {TOP_STORIES} stories are the MUST-KNOW executive stories.

For these TOP {TOP_STORIES}, provide:

headline
what_happened
why_it_matters
business_impact
category
source
source_link

Writing rules for TOP {TOP_STORIES}:

- headline should be short and compelling
- what_happened should be maximum 2 short sentences
- why_it_matters should be maximum 1 to 2 short sentences
- business_impact should be maximum 1 to 2 short sentences
- be factual
- avoid hype
- avoid marketing language
- explain significance clearly
- make it easy for an executive to scan

For stories ranked 6 to {FINAL_STORIES},
provide ONLY:

headline
key_insight
category
source
source_link

key_insight must be ONE concise sentence explaining
the most important thing the reader should know.

Prioritize:

Major AI model releases
AI agents
Agentic AI
Enterprise AI
AI infrastructure
GPUs
AI chips
NVIDIA
OpenAI
Anthropic
Google
Google DeepMind
Microsoft
Meta
Apple
Amazon
Mistral
Hugging Face
Robotics
AI safety
AI security
Government regulation
Major investments
Acquisitions
Important AI research
India AI developments
Business implications

Avoid:

Duplicate stories
Minor updates
Promotional content
Low-impact stories
Repeated announcements
Stories without meaningful implications

Also provide three concise executive insights:

overall_ai_trend
india_watch
business_takeaway

Each executive insight should ideally be
1 to 3 concise sentences.

Return ONLY valid JSON.

Do not use markdown.

Required JSON format:

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

  "more_signals": [
    {{
      "headline": "",
      "key_insight": "",
      "category": "",
      "source": "",
      "source_link": ""
    }}
  ],

  "overall_ai_trend": "",
  "india_watch": "",
  "business_takeaway": ""
}}

TOP_STORIES must contain a maximum of {TOP_STORIES} stories.

more_signals can contain the remaining selected stories,
up to a total of {FINAL_STORIES} stories.

AI NEWS CANDIDATES:

{json.dumps(candidates, ensure_ascii=False, indent=2)}
"""

    last_error = None

    print("\n" + "=" * 80)
    print("CONNECTING TO GEMINI")
    print("=" * 80)

    for model in GEMINI_MODELS:

        print(
            f"\nTrying Gemini model: {model}",
            flush=True
        )

        for attempt in range(
            1,
            4
        ):

            try:

                print(
                    f"Attempt {attempt}/3",
                    flush=True
                )

                response = (
                    client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                )

                if not response.text:

                    raise RuntimeError(
                        "Empty Gemini response."
                    )

                text = (
                    response.text
                    .strip()
                )

                if text.startswith(
                    "```json"
                ):

                    text = text[7:]

                elif text.startswith(
                    "```"
                ):

                    text = text[3:]

                if text.endswith(
                    "```"
                ):

                    text = text[:-3]

                text = text.strip()

                result = json.loads(
                    text
                )

                if not isinstance(
                    result,
                    dict
                ):

                    raise RuntimeError(
                        "Gemini response is not a JSON object."
                    )

                if "top_stories" not in result:

                    raise RuntimeError(
                        "top_stories missing from Gemini result."
                    )

                if "more_signals" not in result:

                    result["more_signals"] = []

                print(
                    f"✅ Gemini succeeded using {model}",
                    flush=True
                )

                print(
                    f"🔥 Top stories: "
                    f"{len(result.get('top_stories', []))}"
                )

                print(
                    f"📡 More signals: "
                    f"{len(result.get('more_signals', []))}"
                )

                return result

            except Exception as error:

                last_error = error

                print(
                    f"⚠️ Gemini error: {error}",
                    flush=True
                )

                if attempt < 3:

                    wait_seconds = (
                        attempt * 5
                    )

                    print(
                        f"Retrying in "
                        f"{wait_seconds} seconds...",
                        flush=True
                    )

                    time.sleep(
                        wait_seconds
                    )

        print(
            f"❌ {model} failed.",
            flush=True
        )

        print(
            "Trying next model...",
            flush=True
        )

    raise RuntimeError(
        "All Gemini models failed. "
        f"Last error: {last_error}"
    )


# ============================================================
# SAFE HTML
# ============================================================

def safe_text(value):

    return html.escape(
        str(
            value or ""
        )
    )


def safe_url(value):

    return html.escape(
        str(
            value or "#"
        ),
        quote=True
    )


# ============================================================
# CATEGORY ICON
# ============================================================

def category_icon(category):

    category = str(
        category or ""
    ).lower()

    if (
        "agent" in category
        or "agentic" in category
    ):
        return "🤖"

    if (
        "chip" in category
        or "gpu" in category
        or "infrastructure" in category
    ):
        return "⚡"

    if (
        "security" in category
        or "safety" in category
    ):
        return "🛡️"

    if (
        "research" in category
        or "science" in category
    ):
        return "🔬"

    if "robot" in category:
        return "🦾"

    if (
        "regulation" in category
        or "government" in category
        or "policy" in category
    ):
        return "🏛️"

    if (
        "investment" in category
        or "funding" in category
        or "business" in category
    ):
        return "💼"

    if "india" in category:
        return "🇮🇳"

    if (
        "model" in category
        or "llm" in category
    ):
        return "🧠"

    return "✨"


# ============================================================
# CREATE HTML EMAIL
# ============================================================

def create_html_email(result):

    top_stories = result.get(
        "top_stories",
        []
    )[:TOP_STORIES]

    more_signals = result.get(
        "more_signals",
        []
    )

    india_time = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=5,
            minutes=30
        )
    )

    hour = india_time.hour

    if hour < 15:

        edition = "Morning Edition"
        edition_icon = "☀️"

    else:

        edition = "Evening Edition"
        edition_icon = "🌙"

    generated_time = (
        india_time.strftime(
            "%d %b %Y • %I:%M %p IST"
        )
    )

    top_story_html = ""

    rank_icons = [
        "🔥",
        "🚀",
        "⚡",
        "🎯",
        "💡",
    ]

    rank_labels = [
        "LEAD STORY",
        "MUST KNOW",
        "MUST KNOW",
        "MUST KNOW",
        "MUST KNOW",
    ]

    for index, story in enumerate(
        top_stories,
        start=1
    ):

        headline = safe_text(
            story.get(
                "headline",
                ""
            )
        )

        category = safe_text(
            story.get(
                "category",
                "AI"
            )
        )

        what_happened = safe_text(
            story.get(
                "what_happened",
                ""
            )
        )

        why_it_matters = safe_text(
            story.get(
                "why_it_matters",
                ""
            )
        )

        business_impact = safe_text(
            story.get(
                "business_impact",
                ""
            )
        )

        source = safe_text(
            story.get(
                "source",
                ""
            )
        )

        source_link = safe_url(
            story.get(
                "source_link",
                "#"
            )
        )

        cat_icon = category_icon(
            story.get(
                "category",
                ""
            )
        )

        rank_icon = rank_icons[
            index - 1
        ]

        rank_label = rank_labels[
            index - 1
        ]

        top_story_html += f"""
        <div style="
            background:#ffffff;
            border:1px solid #dce3ee;
            border-radius:16px;
            overflow:hidden;
            margin-bottom:22px;
            box-shadow:0 5px 18px rgba(15,23,42,0.07);
        ">

            <div style="
                height:5px;
                background:#6366f1;
            ">
            </div>

            <div style="
                padding:25px;
            ">

                <table
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                >
                    <tr>

                        <td>

                            <span style="
                                font-size:22px;
                            ">
                                {rank_icon}
                            </span>

                            <span style="
                                font-size:12px;
                                font-weight:700;
                                color:#6d28d9;
                                letter-spacing:0.8px;
                                margin-left:5px;
                            ">
                                #{index} {rank_label}
                            </span>

                        </td>

                        <td
                            align="right"
                        >

                            <span style="
                                display:inline-block;
                                background:#f1f5f9;
                                color:#334155;
                                padding:6px 11px;
                                border-radius:20px;
                                font-size:11px;
                                font-weight:700;
                            ">
                                {cat_icon} {category}
                            </span>

                        </td>

                    </tr>
                </table>

                <h2 style="
                    margin:17px 0 20px 0;
                    color:#0f172a;
                    font-size:22px;
                    line-height:1.38;
                ">
                    {headline}
                </h2>

                <div style="
                    background:#eff6ff;
                    border-left:4px solid #2563eb;
                    border-radius:8px;
                    padding:15px 17px;
                    margin-bottom:14px;
                ">

                    <div style="
                        color:#1d4ed8;
                        font-weight:700;
                        font-size:13px;
                        margin-bottom:6px;
                    ">
                        📰 WHAT HAPPENED
                    </div>

                    <div style="
                        color:#1e293b;
                        font-size:15px;
                        line-height:1.65;
                    ">
                        {what_happened}
                    </div>

                </div>

                <div style="
                    background:#fff7ed;
                    border-left:4px solid #f97316;
                    border-radius:8px;
                    padding:15px 17px;
                    margin-bottom:14px;
                ">

                    <div style="
                        color:#c2410c;
                        font-weight:700;
                        font-size:13px;
                        margin-bottom:6px;
                    ">
                        🎯 WHY IT MATTERS
                    </div>

                    <div style="
                        color:#1e293b;
                        font-size:15px;
                        line-height:1.65;
                    ">
                        {why_it_matters}
                    </div>

                </div>

                <div style="
                    background:#f0fdf4;
                    border-left:4px solid #22c55e;
                    border-radius:8px;
                    padding:15px 17px;
                ">

                    <div style="
                        color:#15803d;
                        font-weight:700;
                        font-size:13px;
                        margin-bottom:6px;
                    ">
                        💼 BUSINESS IMPACT
                    </div>

                    <div style="
                        color:#1e293b;
                        font-size:15px;
                        line-height:1.65;
                    ">
                        {business_impact}
                    </div>

                </div>

                <table
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    style="
                        margin-top:20px;
                    "
                >

                    <tr>

                        <td style="
                            color:#64748b;
                            font-size:12px;
                        ">
                            🗞️ {source}
                        </td>

                        <td
                            align="right"
                        >

                            <a
                                href="{source_link}"
                                style="
                                    display:inline-block;
                                    background:#2563eb;
                                    color:#ffffff;
                                    text-decoration:none;
                                    font-size:13px;
                                    font-weight:700;
                                    padding:10px 16px;
                                    border-radius:8px;
                                "
                            >
                                Read Story →
                            </a>

                        </td>

                    </tr>

                </table>

            </div>

        </div>
        """

    signals_html = ""

    for index, story in enumerate(
        more_signals,
        start=6
    ):

        headline = safe_text(
            story.get(
                "headline",
                ""
            )
        )

        key_insight = safe_text(
            story.get(
                "key_insight",
                ""
            )
        )

        category = safe_text(
            story.get(
                "category",
                "AI"
            )
        )

        source = safe_text(
            story.get(
                "source",
                ""
            )
        )

        source_link = safe_url(
            story.get(
                "source_link",
                "#"
            )
        )

        cat_icon = category_icon(
            story.get(
                "category",
                ""
            )
        )

        signals_html += f"""
        <div style="
            background:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:12px;
            padding:18px 20px;
            margin-bottom:12px;
        ">

            <table
                width="100%"
                cellspacing="0"
                cellpadding="0"
            >

                <tr>

                    <td
                        width="42"
                        valign="top"
                    >

                        <div style="
                            width:32px;
                            height:32px;
                            line-height:32px;
                            text-align:center;
                            border-radius:50%;
                            background:#eef2ff;
                            color:#4338ca;
                            font-size:12px;
                            font-weight:700;
                        ">
                            {index}
                        </div>

                    </td>

                    <td valign="top">

                        <div style="
                            margin-bottom:5px;
                        ">

                            <span style="
                                font-size:11px;
                                font-weight:700;
                                color:#7c3aed;
                            ">
                                {cat_icon} {category}
                            </span>

                        </div>

                        <div style="
                            color:#0f172a;
                            font-size:16px;
                            font-weight:700;
                            line-height:1.45;
                        ">
                            {headline}
                        </div>

                        <div style="
                            color:#475569;
                            font-size:14px;
                            line-height:1.6;
                            margin-top:6px;
                        ">
                            💡 {key_insight}
                        </div>

                        <div style="
                            margin-top:10px;
                            font-size:12px;
                            color:#94a3b8;
                        ">

                            {source}

                            &nbsp;•&nbsp;

                            <a
                                href="{source_link}"
                                style="
                                    color:#2563eb;
                                    font-weight:700;
                                    text-decoration:none;
                                "
                            >
                                Read →
                            </a>

                        </div>

                    </td>

                </tr>

            </table>

        </div>
        """

    overall_trend = safe_text(
        result.get(
            "overall_ai_trend",
            ""
        )
    )

    india_watch = safe_text(
        result.get(
            "india_watch",
            ""
        )
    )

    business_takeaway = safe_text(
        result.get(
            "business_takeaway",
            ""
        )
    )

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
Global AI Intelligence
</title>

</head>


<body style="
    margin:0;
    padding:0;
    background:#eef2f7;
    font-family:Arial, Helvetica, sans-serif;
">


<div style="
    display:none;
    max-height:0;
    overflow:hidden;
">
    Your executive AI intelligence briefing —
    Top 5 must-know stories plus key signals.
</div>


<div style="
    max-width:780px;
    margin:auto;
    padding:22px 12px 35px 12px;
">


    <!-- HEADER -->

    <div style="
        background:#eef4ff;
        border:1px solid #c7d7fe;
        border-radius:18px;
        padding:34px 30px;
        margin-bottom:22px;
        box-shadow:0 8px 22px rgba(15,23,42,0.08);
    ">

        <div style="
            color:#2563eb;
            font-size:12px;
            font-weight:700;
            letter-spacing:1.6px;
        ">
            🌍 GLOBAL AI INTELLIGENCE
        </div>

        <h1 style="
            color:#0f172a;
            margin:10px 0 8px 0;
            font-size:31px;
            line-height:1.2;
        ">
            Executive AI Brief
        </h1>

        <div style="
            color:#334155;
            font-size:15px;
            line-height:1.6;
        ">
            {edition_icon}
            <strong>
                {edition}
            </strong>
            &nbsp; • &nbsp;
            {generated_time}
        </div>

        <div style="
            margin-top:20px;
        ">

            <span style="
                display:inline-block;
                background:#dbeafe;
                color:#1d4ed8;
                padding:7px 12px;
                border-radius:20px;
                font-size:12px;
                font-weight:700;
                margin-right:6px;
            ">
                🔥 Top 5 Must-Know
            </span>

            <span style="
                display:inline-block;
                background:#ede9fe;
                color:#6d28d9;
                padding:7px 12px;
                border-radius:20px;
                font-size:12px;
                font-weight:700;
            ">
                📡 Global AI Signals
            </span>

        </div>

    </div>


    <!-- INTRO -->

    <div style="
        background:#ffffff;
        border-radius:12px;
        padding:18px 22px;
        margin-bottom:25px;
        border:1px solid #e2e8f0;
        color:#475569;
        font-size:14px;
        line-height:1.65;
    ">

        <strong style="
            color:#0f172a;
        ">
            ⚡ In this briefing:
        </strong>

        The five AI developments that matter most,
        followed by additional signals worth watching.

    </div>


    <!-- TOP 5 TITLE -->

    <div style="
        margin-bottom:14px;
    ">

        <div style="
            color:#7c3aed;
            font-size:12px;
            font-weight:700;
            letter-spacing:1.1px;
        ">
            PRIORITY INTELLIGENCE
        </div>

        <div style="
            color:#0f172a;
            font-size:24px;
            font-weight:700;
            margin-top:4px;
        ">
            🔥 Top 5 — Must Know
        </div>

    </div>


    {top_story_html}


    <!-- MORE SIGNALS -->

    <div style="
        margin:34px 0 16px 0;
        padding-top:6px;
    ">

        <div style="
            color:#2563eb;
            font-size:12px;
            font-weight:700;
            letter-spacing:1.1px;
        ">
            SIGNAL SCAN
        </div>

        <div style="
            color:#0f172a;
            font-size:24px;
            font-weight:700;
            margin-top:4px;
        ">
            📡 More Signals Worth Watching
        </div>

        <div style="
            color:#64748b;
            font-size:13px;
            margin-top:6px;
        ">
            The rest of the developments —
            condensed to the insight that matters.
        </div>

    </div>


    {signals_html}


    <!-- EXECUTIVE RADAR -->

    <div style="
        margin-top:35px;
        background:#ffffff;
        border:1px solid #dbe3ef;
        border-radius:18px;
        padding:30px 26px;
        box-shadow:0 8px 24px rgba(15,23,42,0.08);
    ">

        <div style="
            color:#2563eb;
            font-size:12px;
            font-weight:700;
            letter-spacing:1.2px;
        ">
            EXECUTIVE RADAR
        </div>

        <h2 style="
            color:#0f172a;
            margin:7px 0 22px 0;
            font-size:24px;
        ">
            🧭 What It All Means
        </h2>


        <div style="
            background:#eff6ff;
            border:1px solid #bfdbfe;
            border-radius:12px;
            padding:18px;
            margin-bottom:14px;
        ">

            <div style="
                color:#1d4ed8;
                font-size:13px;
                font-weight:700;
                margin-bottom:7px;
            ">
                🌍 GLOBAL AI TREND
            </div>

            <div style="
                color:#1e293b;
                font-size:15px;
                line-height:1.65;
            ">
                {overall_trend}
            </div>

        </div>


        <div style="
            background:#fff7ed;
            border:1px solid #fed7aa;
            border-radius:12px;
            padding:18px;
            margin-bottom:14px;
        ">

            <div style="
                color:#c2410c;
                font-size:13px;
                font-weight:700;
                margin-bottom:7px;
            ">
                🇮🇳 INDIA WATCH
            </div>

            <div style="
                color:#1e293b;
                font-size:15px;
                line-height:1.65;
            ">
                {india_watch}
            </div>

        </div>


        <div style="
            background:#f0fdf4;
            border:1px solid #bbf7d0;
            border-radius:12px;
            padding:18px;
        ">

            <div style="
                color:#15803d;
                font-size:13px;
                font-weight:700;
                margin-bottom:7px;
            ">
                💼 BUSINESS TAKEAWAY
            </div>

            <div style="
                color:#1e293b;
                font-size:15px;
                line-height:1.65;
            ">
                {business_takeaway}
            </div>

        </div>

    </div>


    <!-- FOOTER -->

    <div style="
        text-align:center;
        padding:28px 15px 10px 15px;
        color:#64748b;
        font-size:11px;
        line-height:1.7;
    ">

        🤖 Generated automatically by
        <strong style="
            color:#334155;
        ">
            Global AI Intelligence Engine
        </strong>

        <br>

        AI signals • Executive relevance • Business impact

    </div>


</div>

</body>

</html>
"""


# ============================================================
# SAVE HTML
# ============================================================

def save_html_email(
    email_html
):

    with open(
        HTML_OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            email_html
        )

    print(
        f"\n✅ HTML email saved as: "
        f"{HTML_OUTPUT_FILE}",
        flush=True
    )


# ============================================================
# SEND GMAIL
# ============================================================

def send_gmail(
    email_html
):

    gmail_username = os.environ.get(
        "GMAIL_USERNAME"
    )

    gmail_app_password = os.environ.get(
        "GMAIL_APP_PASSWORD"
    )

    gmail_to = os.environ.get(
        "GMAIL_TO"
    )

    if not gmail_username:

        raise RuntimeError(
            "GMAIL_USERNAME is missing."
        )

    if not gmail_app_password:

        raise RuntimeError(
            "GMAIL_APP_PASSWORD is missing."
        )

    if not gmail_to:

        raise RuntimeError(
            "GMAIL_TO is missing."
        )

    recipients = [
        address.strip()
        for address in gmail_to.split(",")
        if address.strip()
    ]

    if not recipients:

        raise RuntimeError(
            "No valid recipient found in GMAIL_TO."
        )

    india_time = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=5,
            minutes=30
        )
    )

    if india_time.hour < 15:

        edition = "☀️ Morning"

    else:

        edition = "🌙 Evening"

    subject = (
        "⚡ AI Intelligence | "
        + edition
        + " Brief | "
        + india_time.strftime(
            "%d %b %Y"
        )
    )

    message = MIMEMultipart(
        "alternative"
    )

    message["Subject"] = subject
    message["From"] = f"Global AI Intelligence <{gmail_username}>"

    message["To"] = ", ".join(
        recipients
    )

    plain_text = """
GLOBAL AI INTELLIGENCE

Your latest executive AI briefing is ready.

This edition contains:

- Top 5 must-know AI developments
- What happened
- Why they matter
- Business impact
- Additional AI signals
- Global AI trend
- India watch
- Business takeaway
"""

    message.attach(
        MIMEText(
            plain_text,
            "plain",
            "utf-8"
        )
    )

    message.attach(
        MIMEText(
            email_html,
            "html",
            "utf-8"
        )
    )

    print("\n" + "=" * 80)
    print("CONNECTING TO GMAIL")
    print("=" * 80)

    try:

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=60
        ) as server:

            print(
                "Logging into Gmail...",
                flush=True
            )

            server.login(
                gmail_username,
                gmail_app_password
            )

            print(
                "Sending AI Intelligence email...",
                flush=True
            )

            server.sendmail(
                gmail_username,
                recipients,
                message.as_string()
            )

        print(
            "✅ AI Intelligence email sent successfully.",
            flush=True
        )

    except Exception as error:

        raise RuntimeError(
            f"Gmail sending failed: {error}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 80)

    print(
        "GLOBAL AI INTELLIGENCE ENGINE"
    )

    print("=" * 80)

    gemini_api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not gemini_api_key:

        raise RuntimeError(
            "GEMINI_API_KEY is missing."
        )

    sources = load_sources()

    stories = collect_news(
        sources
    )

    if not stories:

        raise RuntimeError(
            "No recent AI stories found."
        )

    unique_stories = (
        remove_duplicates(
            stories
        )
    )

    candidates = rank_news(
        unique_stories
    )

    if not candidates:

        raise RuntimeError(
            "No candidate stories found."
        )

    result = (
        analyze_with_gemini(
            candidates,
            gemini_api_key
        )
    )

    email_html = (
        create_html_email(
            result
        )
    )

    save_html_email(
        email_html
    )

    send_gmail(
        email_html
    )

    print("\n" + "=" * 80)

    print(
        "✅ GLOBAL AI INTELLIGENCE "
        "ENGINE COMPLETED"
    )

    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
