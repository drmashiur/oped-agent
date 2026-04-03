import os
import json
from google import genai
from google.genai import types
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize API Clients
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

if AI_PROVIDER == "openai":
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elif AI_PROVIDER == "gemini":
    gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_PROMPT = """
You are a research assistant curating global editorial articles for a Bengali science and technology platform.

Your job:
1. Determine whether an article is an editorial, op-ed, or high-level analysis relevant to any of these themes:
   - technology trends and internet culture
   - science and scientific breakthroughs
   - research, development, and innovation
   - tech-focused education
   (Note: Reject dry, bureaucratic policy documents. We want engaging, opinionated, or analytical journalism.)
2. Return strict JSON with the following structure:
   {
     "relevant": true or false,
     "score": integer from 0 to 100 (higher for deep, thought-provoking op-eds),
     "primary_category": "technology" | "science" | "research and innovation" | "education" | "other",
     "keywords": ["array", "of", "up", "to", "5"],
     "bangla_summary": "2 short, engaging sentences in Bangla written in an editorial, journalistic tone.",
     "reason": "1 short sentence in English explaining why it fits the editorial criteria."
   }
"""

def clean_json_output(output_text: str) -> dict:
    """Helper to strip Markdown formatting from LLM JSON outputs."""
    output_text = output_text.strip()
    if output_text.startswith("```json"):
        output_text = output_text[7:]
    if output_text.startswith("```"):
        output_text = output_text[3:]
    if output_text.endswith("```"):
        output_text = output_text[:-3]
    
    try:
        return json.loads(output_text.strip())
    except Exception as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw output: {output_text[:200]}")

def classify_article(title: str, url: str, text: str) -> dict:
    trimmed = text[:12000]
    prompt = f"{SYSTEM_PROMPT}\n\nTitle: {title}\nURL: {url}\n\nArticle text:\n{trimmed}"

    try:
        if AI_PROVIDER == "openai":
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={ "type": "json_object" },
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            raw_output = response.choices[0].message.content
            
        elif AI_PROVIDER == "gemini":
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            raw_output = response.text
            
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {AI_PROVIDER}")

        return clean_json_output(raw_output)

    except Exception as e:
        return {
            "relevant": False,
            "score": 0,
            "primary_category": "other",
            "keywords": [],
            "bangla_summary": "",
            "reason": f"Classification failed ({AI_PROVIDER}): {str(e)}"
        }
