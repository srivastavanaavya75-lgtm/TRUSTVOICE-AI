"""
Compatibility wrapper around the modular interaction engine.

Prefer `risk.pipeline.analyse_interaction` for new code.
"""

from demo.scenarios import SCENARIO_A, SCENARIO_B
from risk.pipeline import analyse_interaction

SCENARIOS = {"A": SCENARIO_A, "B": SCENARIO_B}

VOICE_MAP = {
    "REAL": "LIKELY_AUTHENTIC",
    "SUSPICIOUS": "LIKELY_SPOOF",
    "SPOOF": "LIKELY_SPOOF",
}


class RiskEngine:
    def evaluate(
        self,
        transcript,
        voice_authenticity="REAL",
        identity="UNVERIFIED",
        previous_score=None,
    ):
        voice = VOICE_MAP.get(voice_authenticity, voice_authenticity)
        if voice not in {
            "LIKELY_AUTHENTIC", "LIKELY_SPOOF", "INCONCLUSIVE",
            "INCONCLUSIVE_QUALITY", "UNAVAILABLE",
        }:
            voice = "UNAVAILABLE"
        identity_status = identity if identity in {
            "VERIFIED", "UNVERIFIED", "NOT_AVAILABLE", "MISMATCH",
        } else "UNVERIFIED"
        result = analyse_interaction(
            transcript, voice_label=voice, identity_status=identity_status,
        )
        score = previous_score if previous_score is not None else result["trust_score"]
        return {
            "score": int(score),
            "status": result["interaction_risk"],
            "intent": (result.get("intent") or {}).get("intent"),
            "behaviour": (result.get("behaviour") or {}).get("disclaimer"),
            "signals": result.get("drivers") or [],
        }
