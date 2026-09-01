import os
import re
import json
import html
import time
import smtplib
import feedparser
import httpx

from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google import genai


# ============================================================
# SETTINGS
# ============================================================

SOURCE_FILE = "sources.json"

LOOKBACK_HOURS = 24
MAX_CANDIDATES = 30
FINAL_STORIES = 15

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

    # -----------------------------------------
    # FORMAT 1:
    # [
    #   {"name": "...", "url": "..."}
    # ]
    # -----------------------------------------

    if isinstance(data, list):

        return data

    # -----------------------------------------
    # FORMAT 2:
    # {
    #   "sources": [
    #       {"name": "...", "url": "..."}
    #   ]
    # }
    # -----------------------------------------

    if isinstance(data, dict):

        if (
            "sources" in data
            and isinstance(
                data["sources"],
                list
            )
        ):

            return data["sources"]

        # -------------------------------------
        # FORMAT 3:
        # {
        #   "official": [...],
        #   "research": [...],
        #   "media": [...]
        # }
        # -------------------------------------

        all_sources = []

        for key, value in data.items():

            if isinstance(value, list):

                for source in value:

                    if isinstance(
                        source,
                        dict
                    ):

                        all_sources.append(
                            source
                        )

        if all_sources:

            return all_sources

    raise RuntimeError(
        "Unable to understand sources.json structure."
    )


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

        if not source_url:
            continue

        print(
            f"\nReading: {source_name}"
        )

        try:

            feed = feedparser.parse(
                source_url
            )

            if not feed.entries:

                print(
                    "  No feed entries found."
                )

                continue

            source_count = 0

            for entry in feed.entries:

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
                        "published": published_date.isoformat(),
                        "priority": priority,
                    }
                )

                source_count += 1

            print(
                f"  Recent stories: {source_count}"
            )

        except Exception as error:

            print(
                f"  Feed error: {error}"
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
You are a senior global AI intelligence analyst.

Prepare a professional executive AI intelligence briefing.

Select the 10 to {FINAL_STORIES} MOST IMPORTANT stories.

Prioritize:

Major AI model releases
AI agents
Agentic AI
Enterprise AI
AI infrastructure
GPUs and AI chips
NVIDIA
OpenAI
Google
Google DeepMind
Microsoft
Meta
Anthropic
Mistral
Hugging Face
Robotics
AI safety
AI security
Government regulation
Major AI investments
Acquisitions
Important AI research
India AI developments
Business implications

Avoid:

Duplicate stories
Minor product updates
Promotional content
Low-impact stories

For every story provide:

headline
what_happened
why_it_matters
business_impact
category
source
source_link

Also provide:

overall_ai_trend
india_watch
business_takeaway

Return ONLY valid JSON.

Required format:

{{
  "stories": [
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

AI NEWS CANDIDATES:

{json.dumps(candidates, ensure_ascii=False, indent=2)}
"""

    last_error = None

    print("\n" + "=" * 80)

    print(
        "CONNECTING TO GEMINI"
    )

    print("=" * 80)

    for model in GEMINI_MODELS:

        print(
            f"\nTrying Gemini model: {model}"
        )

        for attempt in range(
            1,
            4
        ):

            try:

                print(
                    f"Attempt {attempt}/3"
                )

                response = (
                    client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                )

                if not response.text:

                    raise RuntimeError(
                        "Empty Gemini response"
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

                if "stories" not in result:

                    raise RuntimeError(
                        "Stories missing from Gemini result"
                    )

                print(
                    f"✅ Gemini succeeded using {model}"
                )

                return result

            except Exception as error:

                last_error = error

                print(
                    f"⚠️ Gemini error: {error}"
                )

                if attempt < 3:

                    wait_seconds = (
                        attempt * 5
                    )

                    print(
                        f"Retrying in "
                        f"{wait_seconds} seconds..."
                    )

                    time.sleep(
                        wait_seconds
                    )

        print(
            f"❌ {model} failed."
        )

        print(
            "Trying next model..."
        )

    raise RuntimeError(
        "All Gemini models failed. "
        f"Last error: {last_error}"
    )


# ============================================================
# CREATE HTML EMAIL
# ============================================================

def create_html_email(result):

    stories = result.get(
        "stories",
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

    generated_time = (
        india_time.strftime(
            "%d %b %Y | %I:%M %p IST"
        )
    )

    story_html = ""

    for index, story in enumerate(
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
                    "AI"
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

        source_link = html.escape(
            str(
                story.get(
                    "source_link",
                    "#"
                )
            ),
            quote=True
        )

        story_html += f"""
        <div style="
            background:#ffffff;
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:24px;
            margin-bottom:20px;
        ">

            <div style="
                font-size:12px;
                font-weight:bold;
                color:#64748b;
            ">
                STORY {index}
            </div>

            <div style="
                display:inline-block;
                background:#eef2ff;
                color:#3730a3;
                padding:5px 10px;
                border-radius:20px;
                font-size:12px;
                font-weight:bold;
                margin-top:8px;
            ">
                {category}
            </div>

            <h2 style="
                color:#111827;
                font-size:21px;
                line-height:1.4;
            ">
                {headline}
            </h2>

            <strong>
                What happened
            </strong>

            <p style="
                color:#374151;
                line-height:1.7;
            ">
                {what_happened}
            </p>

            <strong>
                Why it matters
            </strong>

            <p style="
                color:#374151;
                line-height:1.7;
            ">
                {why_it_matters}
            </p>

            <strong>
                Business impact
            </strong>

            <p style="
                color:#374151;
                line-height:1.7;
            ">
                {business_impact}
            </p>

            <div style="
                color:#6b7280;
                font-size:13px;
            ">
                Source: {source}
            </div>

            <div style="
                margin-top:12px;
            ">

                <a
                    href="{source_link}"
                    style="
                        color:#2563eb;
                        font-weight:bold;
                        text-decoration:none;
                    "
                >
                    Read Full Story →
                </a>

            </div>

        </div>
        """

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

    return f"""
<!DOCTYPE html>

<html>

<body style="
    margin:0;
    background:#f4f6f8;
    font-family:Arial, Helvetica, sans-serif;
">

<div style="
    max-width:760px;
    margin:auto;
    padding:25px 15px;
">

    <div style="
        background:#111827;
        border-radius:14px;
        padding:32px;
        margin-bottom:24px;
    ">

        <div style="
            color:#93c5fd;
            font-size:13px;
            font-weight:bold;
        ">
            GLOBAL AI INTELLIGENCE
        </div>

        <h1 style="
            color:white;
            margin-bottom:8px;
        ">
            AI Intelligence Brief
        </h1>

        <div style="
            color:#d1d5db;
        ">
            {generated_time}
        </div>

    </div>

    {story_html}

    <div style="
        background:#111827;
        color:white;
        padding:28px;
        border-radius:12px;
    ">

        <h2>
            Executive Intelligence Summary
        </h2>

        <h3 style="
            color:#93c5fd;
        ">
            Overall AI Trend
        </h3>

        <p style="
            line-height:1.7;
        ">
            {overall_trend}
        </p>

        <h3 style="
            color:#93c5fd;
        ">
            India Watch
        </h3>

        <p style="
            line-height:1.7;
        ">
            {india_watch}
        </p>

        <h3 style="
            color:#93c5fd;
        ">
            Business Takeaway
        </h3>

        <p style="
            line-height:1.7;
        ">
            {business_takeaway}
        </p>

    </div>

    <div style="
        text-align:center;
        color:#9ca3af;
        font-size:12px;
        padding:25px;
    ">
        Generated automatically by
        Global AI Intelligence Engine
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
        f"{HTML_OUTPUT_FILE}"
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

    india_time = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=5,
            minutes=30
        )
    )

    subject = (
        "🌎 Global AI Intelligence Brief | "
        + india_time.strftime(
            "%d %b %Y"
        )
    )

    message = MIMEMultipart(
        "alternative"
    )

    message["Subject"] = subject

    message["From"] = (
        gmail_username
    )

    message["To"] = ", ".join(
        recipients
    )

    message.attach(
        MIMEText(
            email_html,
            "html",
            "utf-8"
        )
    )

    print("\n" + "=" * 80)

    print(
        "CONNECTING TO GMAIL"
    )

    print("=" * 80)

    try:

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=60
        ) as server:

            print(
                "Logging into Gmail..."
            )

            server.login(
                gmail_username,
                gmail_app_password
            )

            print(
                "Sending AI Intelligence email..."
            )

            server.sendmail(
                gmail_username,
                recipients,
                message.as_string()
            )

        print(
            "✅ AI Intelligence email sent successfully."
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
