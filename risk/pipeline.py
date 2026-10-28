"""End-to-end interaction analysis used by the UI and tests."""

from __future__ import annotations

import re

from models.entities import extract_entities
from models.intent import classify_intent, intent_safety_score
from risk.behaviour import analyse_behaviour
from risk.config import FUSION_WEIGHTS, FUSION_WEIGHTS_NOTE
from risk.context import analyse_context
from risk.fusion import (
    apply_safety_gates,
    authenticity_display,
    compute_fused_score,
    identity_safety_from_status,
    recommended_action,
    trust_band,
    voice_safety_from_label,
)
from utils.state import new_conversation_state, update_conversation_state

SENSITIVE_INTENTS = {
    "credential_request",
    "financial_request",
    "sensitive_data_request",
    "personal_information_request",
}

PRESSURE_ONLY = re.compile(
    r"\b(immediately|right now|do it|don't tell anyone|blocked|hurry)\b",
    re.I,
)


def analyse_interaction(
    transcript: str = "",
    voice_label: str = "UNAVAILABLE",
    identity_status: str = "NOT_AVAILABLE",
    authenticity_score: int | None = None,
    conversation_state: dict | None = None,
    claimed_identity: str | None = None,
    source: str = "LIVE",
    voice_evidence: str = "unavailable",
) -> dict:
    """
    Analyse one utterance (and accumulated conversation state).

    Voice authenticity and interaction risk are computed separately, then
    combined only at the fusion / gate layer.
    """
    if source == "DEMO SCENARIO" and voice_evidence == "unavailable":
        voice_evidence = "illustrative"
    state = conversation_state or new_conversation_state()
    intent = classify_intent(transcript)
    guards = intent.get("linguistic_guards") or {}
    prior_action = state.get("requested_action")
    continuation = (
        intent.get("intent") in {"normal_conversation", "unknown"}
        and prior_action in SENSITIVE_INTENTS
        and not guards.get("last_utterance_retracts")
        and PRESSURE_ONLY.search(transcript or "")
    )
    if continuation:
        intent = dict(intent)
        intent["intent"] = prior_action
        intent["override"] = (
            "Current turn continues an earlier sensitive request under pressure "
            "(history used as context, not as a permanent verdict)"
        )

    entities = extract_entities(transcript)
    behaviour = analyse_behaviour(transcript, intent.get("intent"))
    context = analyse_context(
        transcript, intent.get("intent"), identity_status, entities, state,
    )

    voice_safety = voice_safety_from_label(voice_label)
    if authenticity_score is not None and voice_label == "LIKELY_AUTHENTIC":
        voice_safety = int(max(voice_safety, min(96, authenticity_score)))
    if authenticity_score is not None and voice_label == "LIKELY_SPOOF":
        voice_safety = int(min(voice_safety, max(4, authenticity_score)))

    identity_safety = identity_safety_from_status(identity_status)
    intent_safety = intent_safety_score(intent)

    components = {
        "voice_authenticity": voice_safety,
        "speaker_identity": identity_safety,
        "intent_safety": intent_safety,
        "behaviour_safety": behaviour["Behaviour Safety"],
        "context_safety": context["Context Safety"],
    }
    fused = compute_fused_score(components)
    evidence = {
        "intent": intent.get("intent"),
        "behaviour_signals": behaviour["signals"],
        "context_signals": context["signals"],
        "identity_status": identity_status,
        "voice_label": voice_label,
        "off_channel": context.get("off_channel"),
        "new_destination": context.get("new_destination"),
    }
    gated, caps, forced_risk = apply_safety_gates(fused, evidence)
    if guards.get("last_utterance_retracts") and intent.get("intent") not in SENSITIVE_INTENTS:
        # Clarification / advice can lower risk; keep a small residual note only.
        forced_risk = None
        caps = [c for c in caps if "credential" not in c.lower()]
        residual = 6 if state.get("active_concern") else 0
        gated = int(min(96, gated + (8 if residual else 0)))
        if residual:
            caps.append("Earlier turn raised a concern; current turn appears to retract or clarify it")
    risk, action_code = trust_band(gated)
    if forced_risk:
        rank = {"LOW": 0, "ELEVATED": 1, "HIGH": 2, "CRITICAL": 3}
        if rank.get(forced_risk, 0) > rank.get(risk, 0):
            risk = forced_risk
            action_code = {
                "HIGH": "VERIFY",
                "CRITICAL": "CRITICAL INTERVENTION",
                "ELEVATED": "WARN",
            }.get(risk, action_code)

    action_code, action_detail = recommended_action(risk, voice_label, identity_status)
    drivers = _decision_drivers(
        risk, intent, behaviour, context, caps, voice_label, identity_status,
    )

    result = {
        "source": source,
        "transcript": transcript,
        "intent": intent,
        "entities": entities,
        "behaviour": behaviour,
        "context": context,
        "components": components,
        "factor_display": {
            "Voice Authenticity": components["voice_authenticity"],
            "Speaker Identity": components["speaker_identity"],
            "Intent Safety": components["intent_safety"],
            "Behaviour Safety": components["behaviour_safety"],
            "Context Safety": components["context_safety"],
        },
        "trust_score": gated,
        "fused_uncapped": fused,
        "interaction_risk": risk,
        "voice_label": voice_label,
        "voice_display": authenticity_display(voice_label, evidence_kind=voice_evidence, source=source),
        "identity_status": identity_status,
        "action": action_code,
        "action_detail": action_detail,
        "gates": caps,
        "drivers": drivers,
        "handshake_required": risk == "CRITICAL" or action_code == "CRITICAL INTERVENTION",
        "fusion_weights": dict(FUSION_WEIGHTS),
        "fusion_note": FUSION_WEIGHTS_NOTE,
        "claimed_identity": claimed_identity,
        "behaviour_signals": behaviour["signals"],
        "context_signals": context["signals"],
    }
    result["conversation_state"] = update_conversation_state(state, result)
    return result


def _decision_drivers(risk, intent, behaviour, context, caps, voice_label, identity_status):
    drivers = []
    if risk == "LOW":
        drivers.append("No sensitive request detected" if intent.get("intent") in {
            "normal_conversation", "security_support", "unknown", "unavailable",
        } else f"Intent labelled {intent.get('intent')}")
        if not behaviour["signals"]:
            drivers.append("No urgency, secrecy, or verification-bypass combination")
        if context.get("context_level") == "NORMAL":
            drivers.append("No unusual destination or role/action mismatch")
        if voice_label == "LIKELY_AUTHENTIC":
            drivers.append("Voice signal appears authentic (countermeasure estimate)")
        elif voice_label in {"INCONCLUSIVE", "INCONCLUSIVE_QUALITY"}:
            drivers.append("Voice authenticity is inconclusive and was not treated as an attack")
        if identity_status in {"UNVERIFIED", "NOT_AVAILABLE"}:
            drivers.append("Identity is unverified — not interpreted as malicious by itself")
    else:
        drivers.extend(caps)
        drivers.extend(behaviour.get("notes") or [])
        drivers.extend(context.get("notes") or [])
        if intent.get("override"):
            drivers.append(intent["override"])
        if intent.get("linguistic_guards", {}).get("notes"):
            drivers.extend(intent["linguistic_guards"]["notes"])
    # de-dupe
    seen = []
    for item in drivers:
        if item and item not in seen:
            seen.append(item)
    return seen[:8]
