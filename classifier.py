import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a research assistant helping a Bengali writer.

Your job:
1. Determine whether an article is relevant to any of these themes:
   - education policy
   - science and technology policy
   - research and development
2. Return strict JSON with:
   - relevant: true or false
   - score: integer from 0 to 100
   - primary_category: one of
     ["education policy", "science and technology policy", "research and development", "other"]
   - keywords: array of up to 5 short keywords
   - bangla_summary: 2 short sentences in Bangla
   - reason: 1 short sentence in English
"""

def classify_article(title: str, url: str, text: str) -> dict:
    trimmed = text[:12000]

    response = client.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Title: {title}\nURL: {url}\n\nArticle text:\n{trimmed}"
            }
        ]
    )

    output_text = response.output_text.strip()

    try:
        return json.loads(output_text)
    except Exception:
        return {
            "relevant": False,
            "score": 0,
            "primary_category": "other",
            "keywords": [],
            "bangla_summary": "",
            "reason": f"Failed to parse model output: {output_text[:200]}"
        }
