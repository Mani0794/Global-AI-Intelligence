import os
import json
from google import genai


MODEL = "gemini-3.7-flash"


def analyze_news(news):

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY secret was not found."
        )

    client = genai.Client(
        api_key=api_key
    )

    news_text = []

    for number, item in enumerate(
        news,
        start=1
    ):

        news_text.append(
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

    combined_news = "\n".join(
        news_text
    )


    prompt = f"""
You are a senior global AI intelligence analyst.

You are given a list of recent AI news stories.

Your job is to select the 10 to 15 MOST IMPORTANT
stories for a senior business professional who wants
to understand what is happening in global AI.

Do NOT simply select stories with the highest keyword
score.

Evaluate each story based on:

1. Global significance
2. Business impact
3. Technology significance
4. AI industry impact
5. Potential disruption
6. New model/product/research importance
7. Investment/funding/acquisition significance
8. AI agents impact
9. AI infrastructure/chip significance
10. Regulation/safety significance
11. India relevance

Avoid:

- General technology stories that are not substantially
  about AI
- Minor product updates
- Promotional corporate announcements with little
  significance
- Duplicate stories covering the same event
- Low-impact academic papers

If multiple articles cover the same event, combine them
into ONE story.

For each selected story produce:

- headline
- what_happened
- why_it_matters
- business_impact
- category
- source
- source_link

Also produce:

- overall_ai_trend
- india_watch
- business_takeaway

Return ONLY valid JSON.

Required JSON structure:

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

Here are the news stories:

{combined_news}
"""


    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )


    text = response.text.strip()


    # Remove markdown JSON fences if Gemini adds them

    if text.startswith("```json"):

        text = text[7:]

    if text.startswith("```"):

        text = text[3:]

    if text.endswith("```"):

        text = text[:-3]


    text = text.strip()


    try:

        result = json.loads(text)

    except json.JSONDecodeError:

        raise RuntimeError(
            "Gemini returned invalid JSON:\n"
            + text
        )


    return result
