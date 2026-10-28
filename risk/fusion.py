"""Transparent Dynamic Trust Score fusion and hard safety gates."""

from __future__ import annotations

from risk.config import FUSION_WEIGHTS, IDENTITY_SAFETY, TRUST_BANDS, VOICE_SAFETY


def voice_safety_from_label(label: str) -> int:
    return int(VOICE_SAFETY.get(label, VOICE_SAFETY["UNAVAILABLE"]))


def identity_safety_from_status(status: str) -> int:
    return int(IDENTITY_SAFETY.get(status, IDENTITY_SAFETY["NOT_AVAILABLE"]))


def compute_fused_score(components: dict) -> int:
    total = 0.0
    for key, weight in FUSION_WEIGHTS.items():
        total += float(components.get(key, 80)) * weight
    return int(round(total))


def trust_band(score: int) -> tuple[str, str]:
    for cutoff, risk, action in TRUST_BANDS:
        if score >= cutoff:
            return risk, action
    return "CRITICAL", "CRITICAL INTERVENTION"


def apply_safety_gates(score: int, evidence: dict) -> tuple[int, list[str], str | None]:
    """
    Caps require combinations. A single keyword or an inconclusive voice
    signal is not enough to collapse the score.
    """
    caps = []
    forced_risk = None
    intent = evidence.get("intent")
    behaviour_signals = set(evidence.get("behaviour_signals") or [])
    context_signals = set(evidence.get("context_signals") or [])
    identity = evidence.get("identity_status") or "NOT_AVAILABLE"
    voice = evidence.get("voice_label") or "UNAVAILABLE"
    pressure = behaviour_signals & {
        "urgency", "threat", "secrecy", "isolation",
        "verification_bypass", "artificial_deadline",
    }

    credential = intent == "credential_request"
    financial = intent == "financial_request"
    sensitive = intent == "sensitive_data_request"
    personal = intent == "personal_information_request"

    high_pressure = len(pressure) >= 2 or "threat" in pressure
    unverified = identity in {"UNVERIFIED", "NOT_AVAILABLE", "MISMATCH"}

    if credential and high_pressure and unverified:
        if score > 22:
            score = 22
        caps.append("Credential request + pressure + unverified identity")
        forced_risk = "CRITICAL"
    elif credential and (pressure or "credential_from_unverified" in context_signals):
        if score > 38:
            score = 38
        caps.append("Live credential solicitation with elevated context")
        forced_risk = forced_risk or "HIGH"
    elif credential:
        if score > 48:
            score = 48
        caps.append("Direct credential solicitation")
        forced_risk = forced_risk or "HIGH"

    if financial and evidence.get("new_destination") and (
        "urgency" in pressure or "artificial_deadline" in pressure
    ):
        if score > 28:
            score = 28
        caps.append("Financial transfer to a new destination under time pressure")
        forced_risk = "CRITICAL"
    elif financial and evidence.get("new_destination"):
        if score > 40:
            score = 40
        caps.append("Financial transfer toward a new or unusual destination")
        forced_risk = forced_risk or "HIGH"

    if sensitive and evidence.get("off_channel") and (
        "secrecy" in pressure or "urgency" in pressure or identity == "VERIFIED"
    ):
        if score > 24:
            score = 24
        caps.append("Sensitive data + unusual destination + pressure or over-claim of authority")
        forced_risk = "CRITICAL"
    elif sensitive and (evidence.get("off_channel") or pressure):
        if score > 36:
            score = 36
        caps.append("Sensitive data request with contextual concern")
        forced_risk = forced_risk or "HIGH"

    if personal and unverified and pressure:
        if score > 40:
            score = 40
        caps.append("Personal data request from an unverified party under pressure")
        forced_risk = forced_risk or "HIGH"

    if voice == "LIKELY_SPOOF" and intent in {
        "credential_request", "financial_request", "sensitive_data_request",
    }:
        if score > 18:
            score = 18
        caps.append("Likely synthetic voice combined with a high-sensitivity request")
        forced_risk = "CRITICAL"

    if identity == "MISMATCH" and intent in {
        "credential_request", "financial_request", "sensitive_data_request",
    }:
        if score > 20:
            score = 20
        caps.append("Speaker mismatch with a high-sensitivity request")
        forced_risk = "CRITICAL"

    return int(score), caps, forced_risk


def recommended_action(
    interaction_risk: str,
    voice_label: str,
    identity_status: str,
) -> tuple[str, str]:
    """Return (action code, human explanation)."""
    if interaction_risk == "CRITICAL":
        return (
            "CRITICAL INTERVENTION",
            "Independent verification is required. Voice identity alone is not sufficient authorization for this action.",
        )
    if interaction_risk == "HIGH":
        return (
            "VERIFY",
            "Hold the sensitive action and verify through a trusted channel or device.",
        )
    if interaction_risk == "ELEVATED":
        return (
            "WARN",
            "Continue with caution. Confirm unusual details before sharing information or moving funds.",
        )

    if voice_label == "LIKELY_SPOOF":
        return (
            "WARN",
            "Interaction content looks ordinary, but the voice authenticity signal is weak. Review the voice independently if identity matters.",
        )
    if voice_label in {"INCONCLUSIVE", "INCONCLUSIVE_QUALITY"}:
        extra = " Continue the conversation, but use an independent check if identity matters."
        if identity_status in {"UNVERIFIED", "NOT_AVAILABLE"}:
            extra = " Identity has not been independently established."
        return (
            "CONTINUE",
            "Interaction risk is low. Voice authenticity is inconclusive — not a reason to treat the conversation as an attack."
            + extra,
        )
    return (
        "CONTINUE",
        "No sensitive request or social-engineering combination detected.",
    )


def authenticity_display(label: str, evidence_kind: str = "", source: str = "") -> str:
    base = {
        "LIKELY_AUTHENTIC": "LIKELY AUTHENTIC",
        "LIKELY_SPOOF": "LIKELY SPOOF",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "INCONCLUSIVE_QUALITY": "INCONCLUSIVE / AUDIO QUALITY",
        "UNAVAILABLE": "UNAVAILABLE",
    }.get(label, label.replace("_", " "))
    demo = source == "DEMO SCENARIO" or evidence_kind == "illustrative"
    if demo and label != "UNAVAILABLE":
        return f"{base} (illustrative demo input — not a live model verdict)"
    if evidence_kind == "model":
        return f"{base} (model-derived countermeasure score — not a calibrated probability)"
    return base
