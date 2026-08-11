"""
Turns a transcript + sampled frames into a structured briefing via the Grok API.
Grok's API is OpenAI-schema-compatible: https://api.x.ai/v1/chat/completions
"""
import json
import os
import re

import requests

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
# xAI periodically renames model slugs. If this 404s, check console.x.ai for the
# current recommended flagship (vision-capable) model and update here or via env.
GROK_MODEL = os.environ.get("GROK_MODEL", "grok-4.3")

SYSTEM_PROMPT = """You are a filter for a busy AI engineer who cannot watch every video \
a channel publishes. Your job is NOT to summarize. A summary compresses information the \
reader still has to read and process line by line, which is nearly as slow as watching. \
Your job is triage: tell them fast whether it's worth their time, and if so, exactly what \
to pay attention to.

You will get: the video title, a timestamped transcript, and descriptions of a few frames \
sampled at scene changes (likely slides, code, or diagrams).

Return ONLY valid JSON, no markdown fences, matching this exact shape:

{
  "verdict": "watch" | "skim" | "skip",
  "verdict_reason": "one sentence, plain language, specific to this video",
  "novelty_score": 1-5,  // 1 = entirely restates common knowledge, 5 = genuinely new technique/finding
  "novelty_reason": "one sentence justifying the score",
  "insight_cards": [
    {"claim": "...", "evidence": "...", "why_it_matters": "..."}
    // 3-5 of these. Each field one sentence. Only include claims with real substance -
    // specific numbers, techniques, or arguments, not vague enthusiasm.
  ],
  "entities": ["tool/repo/paper/model names actually mentioned, deduped, max 10"],
  "highlights": [
    {"timestamp": "MM:SS or HH:MM:SS", "what": "why this moment specifically is worth jumping to"}
    // only include if verdict is "watch" or "skim"; omit or leave empty for "skip"
  ]
}

Calibrate honestly: most conference/podcast-style AI content is 70% context-setting and \
30% substance. Be willing to say "skip" or give a novelty_score of 1-2 when a video is \
mostly hype, recap, or thing you'd already know from following the field. Do not be \
diplomatic for its own sake - the whole point is saving the reader time."""


def _frame_content_blocks(frames):
    blocks = []
    for f in frames:
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{f['base64_jpeg']}"},
        })
    return blocks


def analyze_video(api_key, title, transcript, frames, video_url):
    if not transcript:
        transcript = "(No transcript available for this video.)"

    user_content = [
        {
            "type": "text",
            "text": f"Title: {title}\nURL: {video_url}\n\nTranscript:\n{transcript[:60000]}",
        }
    ]
    if frames:
        user_content.append({"type": "text", "text": "Sampled frames follow, in order:"})
        user_content.extend(_frame_content_blocks(frames))

    payload = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(
        GROK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]

    # Grok occasionally wraps JSON in markdown fences despite instructions; strip if present.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "verdict": "skim",
            "verdict_reason": "Could not parse model output automatically — check manually.",
            "novelty_score": None,
            "novelty_reason": "",
            "insight_cards": [],
            "entities": [],
            "highlights": [],
            "_raw_output": raw,
        }
