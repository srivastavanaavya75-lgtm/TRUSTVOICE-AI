"""Illustrative scripted scenarios. These scores are not live model measurements."""

SCENARIO_A = {
    "id": "A",
    "title": "Unknown caller · bank pretext",
    "mode": "DEMO SCENARIO",
    "note": "Illustrative scenario progression — not live countermeasure output.",
    "steps": [
        {
            "text": "Hello.",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": None,
        },
        {
            "text": "I am calling from your bank.",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "bank representative",
        },
        {
            "text": "Confirm your account number.",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "bank representative",
        },
        {
            "text": "Share the OTP.",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "bank representative",
        },
        {
            "text": "Do it immediately or your account will be blocked.",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "bank representative",
        },
    ],
}

SCENARIO_B = {
    "id": "B",
    "title": "Verified identity · dangerous request",
    "mode": "DEMO SCENARIO",
    "note": "Illustrative scenario progression — not live countermeasure output.",
    "steps": [
        {
            "text": "Hey, it's me.",
            "identity": "VERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "known colleague",
        },
        {
            "text": "I need the employee database.",
            "identity": "VERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "known colleague",
        },
        {
            "text": "Send it to my personal email.",
            "identity": "VERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "known colleague",
        },
        {
            "text": "Don't mention this to anyone.",
            "identity": "VERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": "known colleague",
        },
    ],
}

SCENARIO_C = {
    "id": "C",
    "title": "Benign workplace conversation",
    "mode": "DEMO SCENARIO",
    "note": "Illustrative scenario progression — not live countermeasure output.",
    "steps": [
        {
            "text": "Hey, are we still meeting at five?",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": None,
        },
        {
            "text": "Can you send me yesterday's report when you have time?",
            "identity": "UNVERIFIED",
            "voice": "LIKELY_AUTHENTIC",
            "claimed_identity": None,
        },
    ],
}

BENIGN_EXAMPLES = [
    ("BENIGN", "Hey, are we still meeting at five?"),
    ("BENIGN", "Can you send me yesterday's report?"),
    ("BENIGN", "How was your trip?"),
    ("BENIGN", "I'll call you tomorrow."),
    ("BENIGN", "Did you finish the assignment?"),
    ("SECURITY ADVICE", "The bank will never ask for your OTP."),
    ("SECURITY ADVICE", "Never share your password with anyone."),
    ("SECURITY ADVICE", "Someone tried to scam me yesterday."),
    ("CREDENTIAL", "Please give me the OTP you just received."),
    ("CREDENTIAL", "Tell me your password."),
    ("FINANCIAL", "Transfer ₹50,000 to this new account."),
    ("SOCIAL ENGINEERING", "Do it immediately and don't tell anyone."),
    ("SOCIAL ENGINEERING", "I am your manager. Send the employee database to my personal Gmail immediately and don't tell anyone."),
    ("SPOOF-NOTE", "Illustrative spoof case requires live audio through AASIST — this text path does not invent a spoof verdict."),
]

IDENTITY_HELP = {
    "VERIFIED": "Speaker matches an enrolled voiceprint in this demo session.",
    "UNVERIFIED": "Identity has not been independently established. That is not the same as malicious.",
    "NOT_AVAILABLE": "Identity verification unavailable — this prototype does not enroll users by default.",
    "MISMATCH": "Claimed speaker does not match enrolled voice evidence.",
}
