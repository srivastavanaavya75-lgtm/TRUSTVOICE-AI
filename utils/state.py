"""Conversation-level state for TRUSTVOICE."""

from __future__ import annotations

from copy import deepcopy

EMPTY_CONVERSATION = {
    "claimed_identity": None,
    "identity_status": "NOT_AVAILABLE",
    "voice_authenticity": "UNAVAILABLE",
    "intents": [],
    "entities": [],
    "requested_action": None,
    "destinations": [],
    "behavioural_signals": [],
    "context_signals": [],
    "previous_events": [],
    "current_risk": "LOW",
    "trust_scores": [],
    "active_concern": False,
}


def new_conversation_state() -> dict:
    return deepcopy(EMPTY_CONVERSATION)


def update_conversation_state(state: dict | None, utterance: dict) -> dict:
    state = deepcopy(state or new_conversation_state())
    intent = (utterance.get("intent") or {}).get("intent")
    if intent:
        state["intents"].append(intent)
    for ent in utterance.get("entities") or []:
        state["entities"].append(ent)
        if ent.get("type") in {"DESTINATION", "EMAIL"}:
            dest = ent.get("value")
            if dest and dest not in state["destinations"]:
                state["destinations"].append(dest)
    for sig in utterance.get("behaviour_signals") or []:
        if sig not in state["behavioural_signals"]:
            state["behavioural_signals"].append(sig)
    for sig in utterance.get("context_signals") or []:
        if sig not in state["context_signals"]:
            state["context_signals"].append(sig)
    if utterance.get("identity_status"):
        state["identity_status"] = utterance["identity_status"]
    if utterance.get("voice_label"):
        state["voice_authenticity"] = utterance["voice_label"]
    if utterance.get("claimed_identity"):
        state["claimed_identity"] = utterance["claimed_identity"]
    state["requested_action"] = intent or state.get("requested_action")
    state["current_risk"] = utterance.get("interaction_risk", state.get("current_risk"))
    state["trust_scores"].append(utterance.get("trust_score"))
    retracting = bool(
        (utterance.get("intent") or {}).get("linguistic_guards", {}).get("last_utterance_retracts")
    )
    if retracting and intent in {
        "normal_conversation", "security_support", "account_information",
    }:
        state["requested_action"] = intent
        state["active_concern"] = False
    elif intent in {
        "credential_request", "financial_request", "sensitive_data_request",
        "personal_information_request",
    }:
        state["active_concern"] = True
    state["previous_events"].append({
        "transcript": utterance.get("transcript", ""),
        "intent": intent,
        "trust_score": utterance.get("trust_score"),
        "interaction_risk": utterance.get("interaction_risk"),
    })
    return state


def reset_conversation_state() -> dict:
    return new_conversation_state()
