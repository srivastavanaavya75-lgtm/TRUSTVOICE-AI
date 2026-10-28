"""
Prototype configuration.

These weights and thresholds are decision-support defaults for a hackathon
demo. They are not calibrated against a validation set and must not be
described as scientifically optimal or as probabilities.
"""

FUSION_WEIGHTS = {
    "voice_authenticity": 0.15,
    "speaker_identity": 0.10,
    "intent_safety": 0.30,
    "behaviour_safety": 0.25,
    "context_safety": 0.20,
}

FUSION_WEIGHTS_NOTE = (
    "Prototype fusion weights for a decision-support Dynamic Trust Score. "
    "They should be calibrated against labelled validation data before any "
    "operational use. The score is not a probability."
)

# Authenticity decision uses the countermeasure score mapped through a
# sigmoid for display only. The operating point is uncalibrated unless the
# evaluation lab has derived one from labelled samples.
DEFAULT_BONA_THRESHOLD = 0.50
DEFAULT_DECISION_BAND = 0.15

# Display mapping: authenticity score 0-100 (not a calibrated probability).
VOICE_SAFETY = {
    "LIKELY_AUTHENTIC": 92,
    "LIKELY_SPOOF": 18,
    "INCONCLUSIVE": 74,
    "INCONCLUSIVE_QUALITY": 74,
    "UNAVAILABLE": 72,
}

IDENTITY_SAFETY = {
    "VERIFIED": 92,
    "UNVERIFIED": 72,
    "NOT_AVAILABLE": 76,
    "MISMATCH": 12,
}

INTENT_SAFETY_FLOOR = {
    "normal_conversation": 96,
    "security_support": 88,
    "account_information": 74,
    "authorization_request": 48,
    "personal_information_request": 34,
    "sensitive_data_request": 22,
    "financial_request": 20,
    "credential_request": 12,
    "unknown": 86,
    "unavailable": 86,
}

TRUST_BANDS = [
    (80, "LOW", "CONTINUE"),
    (60, "ELEVATED", "WARN"),
    (35, "HIGH", "VERIFY"),
    (0, "CRITICAL", "CRITICAL INTERVENTION"),
]
