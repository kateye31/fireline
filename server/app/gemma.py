"""Incident write-ups from Gemma, served through an OpenAI-compatible API (Ollama in deploy/).

Everything here is best effort: if Gemma is not configured or does not answer, the
template summary built in ground.py stays on the incident and the demo keeps working.
"""
import base64
import logging

import httpx

from . import config

log = logging.getLogger("fireline.gemma")

SYSTEM_PROMPT = (
    "You are the dispatcher assistant for Fireline, a network of solar camera units that "
    "detect wildfire smoke in remote Florida forest. Given one incident, write 2 or 3 short "
    "sentences for a fire crew: what was seen, how confident the unit is, how dangerous the "
    "weather is, and one concrete next step. If an image is attached, say briefly whether it "
    "looks like smoke, cloud, fog or dust. Plain text only, no lists, no speculation beyond the data."
)


def enabled() -> bool:
    return bool(config.GEMMA_BASE_URL)


def _facts(incident: dict, nearest: str | None) -> str:
    lines = [
        f"Unit: {incident['unit_id']}",
        f"Frames with smoke: {incident.get('fr')} of 6",
        f"Average detector confidence: {incident.get('conf')}",
        f"Interest score (0 to 1, alert at {config.INCIDENT_THRESHOLD}): {incident.get('peak_interest')}",
        f"Fire-risk tier: {incident.get('risk')}",
        f"Temperature: {incident.get('temp')} C, humidity: {incident.get('rh')} %",
        f"Location: {incident.get('lat')}, {incident.get('lon')}",
        f"Events in this incident: {incident.get('event_count')}",
    ]
    if nearest:
        lines.append(f"Nearest other unit: {nearest}")
    return "\n".join(lines)


async def summarize(incident: dict, nearest: str | None, image: tuple[bytes, str] | None) -> str | None:
    if not enabled():
        return None
    content: list[dict] = [{"type": "text", "text": _facts(incident, nearest)}]
    if image and config.GEMMA_VISION:
        data, ctype = image
        url = f"data:{ctype};base64,{base64.b64encode(data).decode()}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    body = {
        "model": config.GEMMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "max_tokens": 160,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=config.GEMMA_TIMEOUT_S) as client:
            r = await client.post(
                f"{config.GEMMA_BASE_URL}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {config.GEMMA_API_KEY}"},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # network, auth, model not loaded, bad JSON
        log.warning("Gemma summary failed: %s", e)
        return None


async def health() -> dict:
    if not enabled():
        return {"enabled": False}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{config.GEMMA_BASE_URL}/models",
                headers={"Authorization": f"Bearer {config.GEMMA_API_KEY}"},
            )
            r.raise_for_status()
            models = [m["id"] for m in r.json().get("data", [])]
            return {"enabled": True, "ok": True, "model": config.GEMMA_MODEL, "served": models}
    except Exception as e:
        return {"enabled": True, "ok": False, "model": config.GEMMA_MODEL, "error": str(e)}
