"""Ollama bridge: ask a local model what one citizen does this tick.

Every failure mode (Ollama down, slow, non-JSON reply, unknown action) returns
a rest action so the simulation keeps running without an LLM.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).with_name("config.json")


def _load_config() -> dict[str, Any]:
    """Read config.json once; missing or malformed files fall back to defaults."""

    try:
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")
        return data
    except FileNotFoundError:
        _LOGGER.warning("config.json missing at %s; using built-in defaults", CONFIG_PATH)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        _LOGGER.warning("config.json unreadable (%s); using built-in defaults", error)
    return {}


CONFIG = _load_config()
_OLLAMA_CONFIG = CONFIG.get("ollama") if isinstance(CONFIG.get("ollama"), dict) else {}

OLLAMA_URL = os.environ.get(
    "OLLAMA_URL", str(_OLLAMA_CONFIG.get("base_url", "http://localhost:11434"))
).rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", str(_OLLAMA_CONFIG.get("model", "qwen2.5-coder:7b")))
try:
    OLLAMA_TIMEOUT_SECONDS = float(
        os.environ.get("OLLAMA_TIMEOUT_SECONDS", _OLLAMA_CONFIG.get("timeout_seconds", 5.0))
    )
except (TypeError, ValueError):
    _LOGGER.warning("ollama.timeout_seconds is invalid; using 5.0")
    OLLAMA_TIMEOUT_SECONDS = 5.0

VALID_ACTIONS = ("buy", "sell", "trade", "gather", "wander", "rest", "build", "socialize")
VALID_RESOURCES = ("grain", "wood")
VALID_BUILDINGS = ("shelter", "granary")

SYSTEM_PROMPT = (
    "You are {name}. Personality: {personality}. "
    'Reply with ONLY valid JSON: {{"action":"buy"|"sell"|"trade"|"gather"|"wander"|"rest"|"build"|"socialize",'
    '"resource":"grain"|"wood"|"shelter"|"granary",'
    '"offer":"grain"|"wood","amount":2,"want":1,"reason":"<10 words>"}} '
    "You can work as a Farmer or Woodcutter. Your routine is Work -> Market -> Home. "
    "Wood is found in Tile 1 (West). Grain is found in Tile 2 (East). "
    "You must travel between tiles to get what you need. "
    "Wood rots over time. If you have more than 10 wood, sell it immediately. "
    "FOOD IS LIFE. If the village is large, you MUST gather grain and sell it. "
    "If wood_supply is below 100, go gather wood. Do not stand in the market queue "
    "if you do not have grain or wood to sell. "
    "Do not gather wood if the market has no grain. Build houses when the village is full. "
    "If you are single, find a partner. If you have a partner and a home, have children to grow the village. "
    "Actions: buy or sell one grain/wood (join the market queue first), "
    "trade amount of offer for want of resource with another villager, "
    "gather at a node, socialize with another villager, wander or rest to move, or build. "
    "build needs resource shelter (5 wood + 10 coins) "
    "or granary (10 wood + 20 coins; stores grain for later)."
)

_cached_model: str | None = None


def system_prompt(citizen: Any) -> str:
    return SYSTEM_PROMPT.format(name=citizen.name, personality=citizen.personality)


def build_prompt(citizen: Any, observation: dict[str, Any]) -> str:
    state = observation.get("self") if isinstance(observation.get("self"), dict) else {}
    market = observation.get("market") if isinstance(observation.get("market"), dict) else {}
    survival = (
        f"SURVIVAL RULES: You have {state.get('coins', 0)} coins and {state.get('grain', 0)} grain. "
        f"Grain costs {market.get('grain_price', 0)} coins. "
        "If your hunger is above 30 and you have 0 grain, you MUST choose 'buy' grain. "
        "You cannot eat wood. Selling wood gives you coins to buy grain. "
        "Do not hoard coins—coins cannot be eaten. "
        "If you have coins and no grain, buying grain is the only way to survive. "
        "If the market has low grain supply, gather grain and sell it to the market for a high price. "
        "Do not gather wood if wood is already at 3c, it is worthless. "
        "Buy grain in bulk (3 at a time) so you do not starve while walking. "
        "You are paid only when you sell at the market: a harvest alone earns nothing."
    )
    if market.get("grain_supply", 0) < 20:
        survival += (
            " The market grain supply is critically low: prioritize farming and "
            "gathering grain over wood, and sell grain to the market."
        )
    if market.get("wood_supply", 0) < 100:
        survival += (
            " The town wood supply is below 100: go gather wood. Do not stand in the "
            "market queue if you do not have grain or wood to sell."
        )
    # Keep the prompt small: only the citizen's needs and the local prices, never
    # the whole world/citizen record (which also carries id, position and age).
    compact = {
        "hunger": state.get("hunger", 0),
        "coins": state.get("coins", 0),
        "grain": state.get("grain", 0),
        "job": state.get("job", "unemployed"),
        "homeless": bool(state.get("homeless")),
        "market": {
            "grain_price": market.get("grain_price", 0),
            "wood_price": market.get("wood_price", 0),
            "grain_supply": market.get("grain_supply", 0),
            "wood_supply": market.get("wood_supply", 0),
        },
    }
    lines = [
        "Your current state and the market prices are:",
        json.dumps(compact, sort_keys=True),
        survival,
        "Decide one action for this tick. You may buy or sell at most one unit, "
        "or trade amount of offer for want of resource with a neighbour.",
        "No one gives grain away for free: work, sell, then buy or barter.",
    ]
    if state.get("homeless"):
        lines.append(
            "You are homeless. You need to gather wood and build a shelter "
            "(requires 5 wood + 10 coins)."
            " Build first: a full village has no spare bed for you."
        )
    else:
        lines.append(
            f"You are a {state.get('job', 'unemployed')} and you have a home. "
            "Work, then trade at the market, then go home."
        )
    if state.get("partner_id"):
        lines.append(
            "You have a partner and a home: have children to grow the village, and "
            "keep food in the house so the family survives."
        )
    else:
        lines.append(
            "You are single. If you are single, find a partner; a couple with a home "
            "has children to grow the village."
        )
    return "\n".join(lines)


def ask_gaia(query_text: str) -> str | None:
    """Answer one citizen question through Ollama in ten words or fewer."""

    prompt = (
        "You are GAIA, the AI overseer of this civilization. You are wise, slightly "
        "sarcastic, and highly practical. A citizen asks: "
        f"'{query_text}'. Give them a specific, actionable piece of advice in 10 words "
        "or less. Vary your answers."
    )
    payload = {
        "model": _resolve_model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.9, "num_predict": 40},
    }
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        answer = " ".join(str(response.json().get("response", "")).split())
    except (requests.RequestException, RuntimeError, ValueError, KeyError) as error:
        _LOGGER.warning("GAIA answer unavailable: %s", error)
        return None
    if answer.lower().startswith("gaia:"):
        answer = answer[5:].strip()
    words = answer.split()
    if not words:
        return None
    return " ".join(words[:10])


def is_reachable(timeout: float = 2.0) -> bool:
    """Cheap health check used only for diagnostics."""

    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout).ok
    except requests.RequestException:
        return False


def _resolve_model() -> str:
    """Env override, else the first locally installed model, else a default name."""

    global _cached_model
    if _cached_model:
        return _cached_model
    if OLLAMA_MODEL:
        _cached_model = OLLAMA_MODEL
        return _cached_model

    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
    response.raise_for_status()
    models = response.json().get("models", [])
    if not models:
        raise RuntimeError("Ollama is running but has no models installed")
    _cached_model = models[0]["name"]
    return _cached_model


def _generate(citizen: Any, observation: dict[str, Any]) -> str:
    payload = {
        "model": _resolve_model(),
        "system": system_prompt(citizen),
        "prompt": build_prompt(citizen, observation),
        "stream": False,
        "format": "json",
        # Small JSON answer only: a long reply would blow the 5 s budget.
        "options": {"temperature": 0.7, "num_predict": 60},
    }
    response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
    response.raise_for_status()
    return str(response.json().get("response", ""))


def _json_objects(text: str) -> list[str]:
    """Every balanced {...} block in the text, in order, string-aware.

    A greedy ``re.search(r"\{.*\}")`` spans from the first brace to the last one, so
    a reply with two objects (or a brace in prose) produced invalid JSON and was
    thrown away. Scanning for balanced braces recovers each object separately.
    """

    objects: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(text[start : index + 1])
                start = -1
    return objects


def parse_decision(text: str) -> dict[str, Any] | None:
    """Extract the first usable JSON object from a model reply and validate it.

    Tolerates markdown fences, prose around the JSON and several objects in one
    reply: the whole text is tried first, then every balanced {...} block.
    """

    raw = (text or "").strip()
    if not raw:
        return None
    decision: Any = None
    for candidate in [raw, *_json_objects(raw)]:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            decision = loaded
            break
    if decision is None:
        return None

    action = str(decision.get("action", "")).lower().strip()
    resource = str(decision.get("resource", "grain")).lower().strip()
    if action not in VALID_ACTIONS:
        return None
    if action == "build":
        if resource not in VALID_BUILDINGS:
            return None
    elif action not in ("rest", "gather", "wander", "socialize") and resource not in VALID_RESOURCES:
        return None

    # A missing reason must never cost us a usable decision.
    reason = str(decision.get("reason", "")).strip().replace("\n", " ")
    reason = " ".join(reason.split()[:10]) or ""
    if action == "trade":
        offer = str(decision.get("offer", "wood")).lower().strip()
        if offer not in VALID_RESOURCES or resource not in VALID_RESOURCES or offer == resource:
            return None
        try:
            amount = max(1, min(10, int(decision.get("amount", 2))))
            want = max(1, min(10, int(decision.get("want", 1))))
        except (TypeError, ValueError):
            return None
        return {
            "action": "trade",
            "resource": resource,
            "offer": offer,
            "amount": amount,
            "want": want,
            "reason": reason,
        }
    if action == "wander":
        return {"action": "wander", "reason": reason}
    if action != "build" and resource not in VALID_RESOURCES:
        resource = "grain"
    return {
        "action": action,
        "resource": resource,
        "reason": reason,
    }


def decide(citizen: Any, observation: dict[str, Any]) -> dict[str, Any]:
    """Return the citizen's action for this tick; rest when the model cannot answer."""

    try:
        raw = _generate(citizen, observation)
    except (requests.RequestException, RuntimeError, ValueError, KeyError) as error:
        return {"action": "gather", "resource": "grain", "reason": f"fallback: {type(error).__name__}"}

    decision = parse_decision(raw)
    if decision is None:
        return {"action": "gather", "resource": "grain", "reason": "fallback: unparsable reply"}
    return decision
