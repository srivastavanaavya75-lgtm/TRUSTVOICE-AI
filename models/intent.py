"""Lightweight TF-IDF + logistic regression intent classifier with linguistic guards."""

from __future__ import annotations

import re

from models.intent_data import INTENT_TRAINING
from risk.config import INTENT_SAFETY_FLOOR

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion
except ImportError:
    TfidfVectorizer = None
    LogisticRegression = None
    FeatureUnion = None

_intent_model = None

INTENT_DISPLAY = {
    "normal_conversation": "Normal Conversation",
    "account_information": "Account Information",
    "credential_request": "Credential Request",
    "financial_request": "Financial Request",
    "sensitive_data_request": "Sensitive Data Request",
    "personal_information_request": "Personal Information Request",
    "security_support": "Security Advice / Support Discussion",
    "authorization_request": "Authorization Request",
    "unknown": "Unknown",
    "unavailable": "Unavailable",
}

CREDENTIAL_TERMS = [
    (r"\b(otp|o\.?t\.?p\.?|one[- ]time password)\b", "OTP"),
    (r"\b(cvv|cvc)\b", "CVV"),
    (r"\b(upi pin|atm pin)\b", "PIN"),
    (r"\b(password|passcode)\b", "Password"),
    (r"\b(verification|security|authentication) code\b", "Verification code"),
    (r"\bpin\b", "PIN"),
]

SOLICIT_VERBS = (
    r"(give|send|share|tell|read|forward|confirm|provide|dictate|type|batao|bata)"
)

CREDENTIAL_LEX = (
    r"(otp|o\.?t\.?p\.?|one[- ]time password|cvv|cvc|upi pin|atm pin|password|"
    r"passcode|verification code|security code|authentication code|\bpin\b)"
)

ADVICE_PATTERNS = [
    r"\b(never ask|will never|do not ask|doesn't ask|does not ask)\b",
    r"\b(never share|don't share|do not share|never give|don't give|do not give)\b",
    r"\b(don't tell anyone your|do not tell anyone your)\b",
    r"\b(explain why .{0,40}(otp|password|pin).{0,20}(dangerous|sensitive|risky))\b",
    r"\b(why (otps?|passwords?) are (dangerous|sensitive))\b",
    r"\b(legitimate|real (bank|agent)|official).{0,40}(never|will not)\b",
    r"\b(hang up|report|awareness|phishing|scam)\b",
    r"\bkabhi (otp|password).{0,12}(mat|nahi)\b",
    r"\bbank kabhi otp nahi\b",
    r"\b(told me never|said never|remember,? never)\b",
    r"\bnever transfer money\b",
    r"\bdon't send money\b",
    r"\bdo not send money\b",
]

PAST_OR_REPORT_PATTERNS = [
    r"\b(someone (asked|tried|called)|tried to (steal|scam|phish)|the scammer)\b",
    r"\b(yesterday|last (night|week)|already)\b.{0,40}\b(otp|password|pin|payment|bank details)\b",
    r"\b(otp|password|pin|payment|bank details)\b.{0,40}\b(yesterday|last (night|week))\b",
    r"\b(i (received|got) (an |the |my )?(otp|code|salary))\b",
    r"\b(did you receive (the )?(otp|code|sms))\b",
    r"\b(the otp (came|arrived))\b",
    r"\b(he threatened me|threatened me for)\b",
    r"\b(i (already )?(gave|sent|made) (the |a )?(payment|otp|money))\b",
]

CLARIFICATION_PATTERNS = [
    r"\b(i meant|no[, ]+i meant|that is not what i meant|publicly available|from the website)\b",
    r"\b(i am not asking|i'm not asking|not asking for)\b",
    r"\b(i will not share|i won't share|i forgot my password|reset my password)\b",
]

NEGATION_WINDOW = re.compile(
    r"(never|not|don't|do not|didn't|did not|won't|will not|nahi|mat)\b.{0,50}"
    + CREDENTIAL_LEX,
    re.I,
)

FINANCIAL_TRANSFER = re.compile(
    r"\b(transfer|wire|neft|imps|send (the )?money|send ₹|send rs)\b.{0,60}"
    r"\b(to (this|the new|my personal|a new)|to account)\b",
    re.I,
)

FINANCIAL_NEGATION = re.compile(
    r"\b(don't|do not|never|not)\b.{0,40}\b(send money|transfer|wire)\b",
    re.I,
)

SELF_PASSWORD = re.compile(
    r"\b(i forgot my password|reset my password|change my password)\b",
    re.I,
)

BENIGN_BALANCE = re.compile(
    r"\b(account balance|bank balance|my salary|payment was successful|explain neft|"
    r"when will my salary|i made a upi|bank account is frozen|"
    r"update my bank details|received ₹|received rs|received inr|"
    r"i sent ₹|i sent rs)\b",
    re.I,
)

SENSITIVE_SOLICIT = re.compile(
    r"(send|share|export|mail|forward|dump|give).{0,80}"
    r"(employee database|customer (?:database|records|kyc)|salary sheet|payroll|kyc documents?)",
    re.I,
)


def clean_text(text) -> str:
    clean = re.sub(r"<[^>]+>", " ", str(text or ""))
    return " ".join(clean.split())


def split_utterances(text: str):
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    return parts or ([text] if text else [])


def get_intent_model():
    global _intent_model
    if _intent_model is not None:
        return _intent_model
    if TfidfVectorizer is None or LogisticRegression is None or FeatureUnion is None:
        return None

    labels = [x[0] for x in INTENT_TRAINING]
    texts = [x[1] for x in INTENT_TRAINING]
    vectorizer = FeatureUnion([
        ("word", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)),
        ("char", TfidfVectorizer(
            lowercase=True, analyzer="char_wb", ngram_range=(3, 5),
            sublinear_tf=True, min_df=1,
        )),
    ])
    X = vectorizer.fit_transform(texts)
    model = LogisticRegression(
        max_iter=4000, C=3.5, class_weight="balanced", random_state=42,
    )
    model.fit(X, labels)
    _intent_model = (vectorizer, model)
    return _intent_model


def credential_terms_in(text: str):
    found = []
    for pattern, name in CREDENTIAL_TERMS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            if name not in found:
                found.append(name)
    return found


def _is_retract(sent: str) -> bool:
    return bool(
        any(re.search(p, sent, flags=re.I) for p in ADVICE_PATTERNS)
        or any(re.search(p, sent, flags=re.I) for p in PAST_OR_REPORT_PATTERNS)
        or any(re.search(p, sent, flags=re.I) for p in CLARIFICATION_PATTERNS)
        or NEGATION_WINDOW.search(sent)
        or FINANCIAL_NEGATION.search(sent)
        or SELF_PASSWORD.search(sent)
    )


def linguistic_context(text: str) -> dict:
    """Explainable heuristics around credential language. Not an LLM."""
    clean = clean_text(text)
    sentences = split_utterances(clean)
    advice, past, solicitation, negated, clarifications = [], [], [], [], []

    for sent in sentences:
        if any(re.search(p, sent, flags=re.I) for p in ADVICE_PATTERNS):
            advice.append(sent)
        if any(re.search(p, sent, flags=re.I) for p in PAST_OR_REPORT_PATTERNS):
            past.append(sent)
        if any(re.search(p, sent, flags=re.I) for p in CLARIFICATION_PATTERNS):
            clarifications.append(sent)
        if NEGATION_WINDOW.search(sent) or FINANCIAL_NEGATION.search(sent):
            negated.append(sent)

        solicit = re.search(
            rf"{SOLICIT_VERBS}.{{0,40}}{CREDENTIAL_LEX}|{CREDENTIAL_LEX}.{{0,24}}"
            rf"(you just received|jo abhi aaya|from your phone|on your phone)",
            sent,
            flags=re.I,
        )
        if solicit and not _is_retract(sent):
            solicitation.append(sent)

        if re.search(
            rf"^\s*{SOLICIT_VERBS}\s+(me\s+|us\s+)?(the\s+|your\s+|an\s+)?{CREDENTIAL_LEX}",
            sent,
            flags=re.I,
        ) and not _is_retract(sent):
            if sent not in solicitation:
                solicitation.append(sent)

    last = sentences[-1] if sentences else ""
    last_retracts = bool(last and _is_retract(last))
    force_cred = bool(solicitation) and not last_retracts
    force_sensitive = bool(SENSITIVE_SOLICIT.search(clean)) and not last_retracts
    if last_retracts and clarifications:
        force_sensitive = False
    force_financial = bool(FINANCIAL_TRANSFER.search(clean)) and not last_retracts
    if FINANCIAL_NEGATION.search(clean) and last_retracts:
        force_financial = False

    return {
        "advice_or_warning": advice,
        "past_or_report": past,
        "direct_solicitation": solicitation,
        "negated_credential": negated,
        "clarification": clarifications,
        "last_utterance_retracts": last_retracts,
        "suppress_credential_hard_rule": (
            bool(advice or past or negated or clarifications or last_retracts)
            and not force_cred
        ),
        "force_credential_request": force_cred,
        "force_sensitive_data_request": force_sensitive,
        "force_financial_request": force_financial,
        "self_service_password": bool(SELF_PASSWORD.search(clean)),
        "benign_financial_language": bool(BENIGN_BALANCE.search(clean)) and not force_financial,
        "notes": _context_notes(advice, past, solicitation, negated, clarifications),
    }


def _context_notes(advice, past, solicitation, negated, clarifications=None):
    notes = []
    if advice:
        notes.append("Credential terms appear in security-advice or warning language")
    if past:
        notes.append("Credential terms refer to a past event or report, not a live request")
    if negated:
        notes.append("Negation around credential/payment terms (do not / never share)")
    if clarifications:
        notes.append("Later utterance clarifies or retracts an earlier reading")
    if solicitation:
        notes.append("Direct solicitation of a live credential")
    return notes


def classify_intent(text: str) -> dict:
    clean = clean_text(text)
    guards = linguistic_context(clean)
    terms = credential_terms_in(clean)

    empty = {
        "intent": "unknown",
        "confidence": 0.0,
        "probabilities": {},
        "engine": "No text",
        "riskiest_utterance": "",
        "utterances_scored": 0,
        "credential_terms": terms,
        "linguistic_guards": guards,
        "override": None,
    }
    if not clean:
        return empty

    bundle = get_intent_model()
    if bundle is None:
        empty.update({
            "intent": "unavailable",
            "engine": "scikit-learn not installed",
        })
        return _apply_guards(empty, guards)

    vectorizer, model = bundle
    utterances = split_utterances(clean)
    X = vectorizer.transform(utterances)
    all_probs = model.predict_proba(X)
    classes = [str(c) for c in model.classes_]

    best_row, best_intent, best_conf, best_risk = 0, "normal_conversation", 0.0, 100.0
    for row_idx, probs in enumerate(all_probs):
        order = probs.argsort()[::-1]
        intent = classes[int(order[0])]
        conf = float(probs[int(order[0])])
        floor = INTENT_SAFETY_FLOOR.get(intent, 80)
        risk_value = 96 - (96 - floor) * conf
        if risk_value < best_risk:
            best_row, best_intent, best_conf, best_risk = row_idx, intent, conf, risk_value

    probs = all_probs[best_row]
    order = probs.argsort()[::-1]
    probabilities = {classes[int(i)]: round(float(probs[int(i)]) * 100, 1) for i in order[:5]}

    result = {
        "intent": best_intent,
        "confidence": round(best_conf * 100, 1),
        "probabilities": probabilities,
        "engine": "Local TF-IDF (word + char n-grams) + Logistic Regression",
        "riskiest_utterance": utterances[best_row],
        "utterances_scored": len(utterances),
        "credential_terms": terms,
        "linguistic_guards": guards,
        "override": None,
    }
    return _apply_guards(result, guards)


def _apply_guards(result: dict, guards: dict) -> dict:
    intent = result.get("intent", "unknown")
    if guards.get("last_utterance_retracts") and guards.get("suppress_credential_hard_rule"):
        if intent in {
            "credential_request", "personal_information_request",
            "financial_request", "sensitive_data_request",
        }:
            if guards.get("advice_or_warning") or guards.get("negated_credential"):
                result["intent"] = "security_support"
                result["override"] = "Latest utterance is advice, negation, or a report — not a live request"
            elif guards.get("clarification"):
                result["intent"] = "normal_conversation"
                result["override"] = "Clarification / retraction of an earlier reading"
            else:
                result["intent"] = "normal_conversation"
                result["override"] = "Sensitive terms without a live request"
            result["confidence"] = max(float(result.get("confidence") or 0), 80.0)
            return result

    if guards.get("force_credential_request"):
        result["intent"] = "credential_request"
        result["override"] = "Direct credential solicitation pattern"
        result["confidence"] = max(float(result.get("confidence") or 0), 88.0)
        return result
    if guards.get("force_sensitive_data_request"):
        result["intent"] = "sensitive_data_request"
        result["override"] = "Sensitive dataset transfer request"
        result["confidence"] = max(float(result.get("confidence") or 0), 86.0)
        return result
    if guards.get("force_financial_request"):
        result["intent"] = "financial_request"
        result["override"] = "Outbound transfer request pattern"
        result["confidence"] = max(float(result.get("confidence") or 0), 84.0)
        return result

    if guards.get("self_service_password") and intent == "credential_request":
        result["intent"] = "normal_conversation"
        result["override"] = "Self-service password mention, not a request for someone else's secret"
        return result

    if guards.get("benign_financial_language") and intent == "financial_request":
        result["intent"] = "account_information" if re.search(
            r"\b(balance|salary|neft|upi payment|frozen|bank details)\b",
            str(result.get("riskiest_utterance") or ""),
            flags=re.I,
        ) else "normal_conversation"
        result["override"] = "Ordinary financial language, not an outbound transfer request"
        return result

    if guards.get("suppress_credential_hard_rule"):
        if intent in {
            "credential_request",
            "personal_information_request",
            "financial_request",
        }:
            if guards.get("advice_or_warning") or guards.get("negated_credential"):
                result["intent"] = "security_support"
                result["override"] = "Treated as security advice / warning, not a request"
            else:
                result["intent"] = "normal_conversation"
                result["override"] = "Credential mention without a live request"
            result["confidence"] = max(float(result.get("confidence") or 0), 80.0)
    return result


def intent_display_name(name: str) -> str:
    return INTENT_DISPLAY.get(name, str(name or "unknown").replace("_", " ").title())


def intent_safety_score(intent_result: dict) -> int:
    intent = intent_result.get("intent", "unknown")
    floor = INTENT_SAFETY_FLOOR.get(intent, 86)
    conf = float(intent_result.get("confidence", 0.0)) / 100.0
    safety = 96 - (96 - floor) * conf
    if intent_result.get("linguistic_guards", {}).get("force_credential_request"):
        safety = min(safety, 14)
    if intent_result.get("linguistic_guards", {}).get("suppress_credential_hard_rule"):
        if intent in {"security_support", "normal_conversation"}:
            safety = max(safety, 88)
    return int(max(2, min(98, round(safety))))


def describe_intent(intent) -> str:
    if not isinstance(intent, dict):
        return str(intent or "")
    name = intent_display_name(intent.get("intent", "unknown"))
    parts = [f"{name} (classifier confidence {intent.get('confidence', 0)}%)"]
    if intent.get("override"):
        parts.append(str(intent["override"]))
    if intent.get("credential_terms"):
        parts.append("credential terms mentioned: " + ", ".join(intent["credential_terms"]))
    if intent.get("riskiest_utterance"):
        parts.append("driven by: " + str(intent["riskiest_utterance"])[:160])
    return " · ".join(parts)
