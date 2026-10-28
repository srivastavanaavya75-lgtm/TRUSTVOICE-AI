"""Observable social-engineering indicators. Combinations matter more than single cues."""

from __future__ import annotations

import re

from models.intent import clean_text

SENSITIVE_INTENTS = {
    "credential_request",
    "financial_request",
    "sensitive_data_request",
    "personal_information_request",
    "authorization_request",
}

CUES = [
    ("urgency", r"\b(immediately|right now|urgent(ly)?|hurry|quickly|at once|do it now|abhi)\b", "Urgency"),
    ("soft_deadline", r"\b(today|by eod|this evening)\b", "Time expectation"),
    ("threat", r"\b(will be (blocked|suspended|closed|frozen)|permanently blocked|legal action|arrest|you will lose|otherwise)\b", "Threat / consequence framing"),
    ("secrecy", r"\b(don't tell anyone|do not tell anyone|keep this secret|don't mention|no one should know|keep this between us)\b", "Secrecy"),
    ("isolation", r"\b(don't hang up|do not hang up|don't disconnect|stay on the (line|call)|don't call (the )?bank)\b", "Isolation attempt"),
    ("verification_bypass", r"\b(trust me|no need to (verify|check|confirm)|skip the (verification|process)|don't mention this to anyone|don't verify)\b", "Verification bypass"),
    ("artificial_deadline", r"\b(last (chance|warning)|final notice|expires? (today|in)|in \d+ minutes?|before (evening|5 ?pm))\b", "Artificial deadline"),
    ("authority_claim", r"\b(i am (calling from|your manager|from (your )?bank|the manager)|this is (your )?bank|security department|bank security)\b", "Authority claim"),
]


def analyse_behaviour(text: str, intent: str = "normal_conversation") -> dict:
    clean = clean_text(text)
    signals = []
    labels = []
    for key, pattern, label in CUES:
        if re.search(pattern, clean, flags=re.I):
            signals.append(key)
            labels.append(label)

    if re.search(r"\bwhen you (have time|can)\b", clean, flags=re.I):
        signals = [s for s in signals if s not in {"soft_deadline", "urgency"}]
        labels = [lb for lb in labels if lb not in {"Time expectation", "Urgency"}]

    sensitive = intent in SENSITIVE_INTENTS
    penalty = 0
    notes = []

    if "urgency" in signals or "artificial_deadline" in signals:
        if sensitive:
            penalty += 18
            notes.append("Urgency combined with a sensitive request")
        else:
            penalty += 40
            notes.append("Strong urgency language (not by itself a critical interaction)")

    if "soft_deadline" in signals and "urgency" not in signals:
        penalty += 18
        notes.append("Same-day time expectation")

    if "threat" in signals:
        penalty += 16 if sensitive else 8
        notes.append("Threat / consequence language")

    if "secrecy" in signals:
        penalty += 20 if sensitive else 10
        notes.append("Secrecy request")

    if "isolation" in signals:
        penalty += 14
        notes.append("Isolation attempt")

    if "verification_bypass" in signals:
        penalty += 16 if sensitive else 8
        notes.append("Verification bypass language")

    if "authority_claim" in signals and sensitive:
        penalty += 10
        notes.append("Authority claim alongside a sensitive request")

    combo = len(signals)
    if combo >= 3 and sensitive:
        penalty += 12
        notes.append("Multiple social-engineering indicators combined")
    elif combo >= 3:
        penalty += 6
        notes.append("Multiple pressure indicators, request itself not sensitive")

    safety = int(max(4, min(96, 94 - penalty)))
    if safety >= 80:
        level = "LOW"
    elif safety >= 55:
        level = "MEDIUM"
    else:
        level = "HIGH"

    return {
        "Behaviour Safety": safety,
        "behaviour_level": level,
        "signals": signals,
        "signal_labels": labels,
        "notes": notes,
        "disclaimer": "Observable social-engineering indicators detected."
        if signals else "No major social-engineering indicators observed.",
    }
