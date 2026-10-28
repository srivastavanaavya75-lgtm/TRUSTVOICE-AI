"""Lightweight regex entity extraction for the prototype risk layer."""

from __future__ import annotations

import re

from models.intent import clean_text

ENTITY_SPECS = [
    (
        "AMOUNT",
        re.compile(
            r"(?:₹\s*\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|₹\s*\d+(?:\.\d+)?|"
            r"(?:rs\.?|inr)\s*\d{1,3}(?:,\d{2,3})+|"
            r"(?:rs\.?|inr)\s*\d{4,}|"
            r"\b\d{1,3}(?:,\d{2,3})+\s*(?:rupees?|rs)?|"
            r"\b(?:fifty|two|one|five)\s+(?:thousand|lakh|lac)\s+(?:rupees?)?)",
            re.I,
        ),
    ),
    (
        "ACCOUNT",
        re.compile(
            r"\b(?:account(?:\s+number)?|a/c)\s*[:#-]?\s*(\d{6,18})\b|"
            r"\b(personal account|new bank account)\b",
            re.I,
        ),
    ),
    (
        "OTP",
        re.compile(r"\b(?:otp|one[- ]time password|verification code)\b", re.I),
    ),
    (
        "PHONE",
        re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"),
    ),
    (
        "EMAIL",
        re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    ),
    (
        "BANK",
        re.compile(
            r"\b(?:your bank|the bank|bank security(?: team)?|sbi|hdfc|icici|axis bank|kotak)\b",
            re.I,
        ),
    ),
    (
        "PAYMENT_METHOD",
        re.compile(r"\b(?:upi|neft|imps|rtgs|gift cards?|crypto|bitcoin|wallet)\b", re.I),
    ),
    (
        "DESTINATION",
        re.compile(
            r"\b(?:personal (?:email|gmail|number|account)|gmail|"
            r"new (?:bank )?account|different account|this account)\b",
            re.I,
        ),
    ),
    (
        "DOCUMENT",
        re.compile(
            r"\b(?:employee database|customer (?:database|records|kyc)|salary (?:sheet|data)|"
            r"payroll|kyc documents?|kyc|attendance report|confidential files?|"
            r"client contact list|audit report)\b",
            re.I,
        ),
    ),
    (
        "PERSON_ROLE",
        re.compile(
            r"\b(?:your manager|i am (?:your )?manager|\bmanager\b|"
            r"from (?:your )?bank|security (?:department|team)|bank security team|"
            r"\bceo\b|\bhr\b|fraud team)\b",
            re.I,
        ),
    ),
]


def extract_entities(text: str) -> list[dict]:
    clean = clean_text(text)
    if not clean:
        return []
    found = []
    seen = set()
    for label, pattern in ENTITY_SPECS:
        for match in pattern.finditer(clean):
            value = match.group(1) if match.lastindex else match.group(0)
            value = " ".join(str(value).split())
            key = (label, value.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append({"type": label, "value": value})
    return found


def entity_map(entities: list[dict]) -> dict:
    grouped = {}
    for item in entities:
        grouped.setdefault(item["type"], []).append(item["value"])
    return grouped
