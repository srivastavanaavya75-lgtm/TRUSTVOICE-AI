"""Deterministic behavioural tests for the TRUSTVOICE prototype pipeline."""

import unittest

try:
    import numpy as np
except ImportError:
    class MockNumpy:
        float32 = "float32"
        def zeros(self, shape, dtype=None):
            return [0.0] * (shape if isinstance(shape, int) else shape[0])
    np = MockNumpy()

from models.antispoof import derive_verdict
from models.entities import extract_entities
from models.intent import classify_intent
from risk.pipeline import analyse_interaction
from utils.audio import quality_gate
from utils.state import new_conversation_state


class PipelineAcceptanceTests(unittest.TestCase):
    def test_benign_meeting(self):
        r = analyse_interaction("Hey, are we still meeting at five?")
        self.assertIn(r["intent"]["intent"], {"normal_conversation", "unavailable"})
        self.assertEqual(r["behaviour"]["behaviour_level"], "LOW")
        self.assertEqual(r["context"]["context_level"], "NORMAL")
        self.assertIn(r["interaction_risk"], {"LOW", "NOT_ASSESSED"})
        self.assertNotEqual(r["action"], "CRITICAL INTERVENTION")
        self.assertFalse(r["handshake_required"])

    def test_security_advice_otp(self):
        r = analyse_interaction("The bank will never ask you for your OTP.")
        self.assertNotEqual(r["intent"]["intent"], "credential_request")
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertIn(r["intent"]["intent"], {"security_support", "normal_conversation", "unavailable"})

    def test_otp_request(self):
        r = analyse_interaction("Please send me the OTP you just received.")
        self.assertEqual(r["intent"]["intent"], "credential_request")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})
        self.assertIn(r["action"], {"VERIFY", "CRITICAL INTERVENTION"})

    def test_social_engineering_combo(self):
        text = (
            "I am your manager. Send the employee database to my personal Gmail "
            "immediately and don't tell anyone."
        )
        r = analyse_interaction(text, identity_status="UNVERIFIED")
        self.assertEqual(r["intent"]["intent"], "sensitive_data_request")
        self.assertEqual(r["interaction_risk"], "CRITICAL")
        self.assertTrue(r["handshake_required"])
        joined = " ".join(r["behaviour"]["signals"] + r["context"]["signals"])
        self.assertTrue(
            any(k in joined for k in ("urgency", "secrecy", "off_channel", "authority")),
        )

    def test_authentic_voice_dangerous_request(self):
        r = analyse_interaction(
            "Send the OTP.",
            voice_label="LIKELY_AUTHENTIC",
            authenticity_score=94,
        )
        self.assertEqual(r["voice_display"], "LIKELY AUTHENTIC")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_inconclusive_voice_benign_chat(self):
        r = analyse_interaction(
            "Hey, how are you?",
            voice_label="INCONCLUSIVE",
        )
        self.assertEqual(r["voice_display"], "INCONCLUSIVE")
        self.assertEqual(r["interaction_risk"], "LOW")
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertEqual(r["action"], "CONTINUE")

    def test_verified_identity_is_not_authorization(self):
        r = analyse_interaction(
            "Send the employee database to my personal Gmail and don't tell anyone.",
            identity_status="VERIFIED",
            voice_label="LIKELY_AUTHENTIC",
        )
        self.assertEqual(r["identity_status"], "VERIFIED")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_unverified_identity_benign(self):
        r = analyse_interaction(
            "Hey, how are you?",
            identity_status="UNVERIFIED",
        )
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_urgency_only_is_not_critical(self):
        r = analyse_interaction(
            "Please send the report immediately because the deadline is 5 PM."
        )
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertNotEqual(r["intent"]["intent"], "credential_request")

    def test_urgency_plus_sensitive_is_worse(self):
        mild = analyse_interaction("Please send the report immediately.")
        harsh = analyse_interaction(
            "Give me the OTP immediately.",
            identity_status="UNVERIFIED",
        )
        self.assertLess(harsh["trust_score"], mild["trust_score"])
        self.assertIn(harsh["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_poor_audio_quality_inconclusive(self):
        q = quality_gate(np.zeros(8000, dtype=np.float32), 16000)
        self.assertEqual(q["quality"], "REVIEW")
        self.assertTrue(q["issues"])
        anti = derive_verdict(
            {
                "authenticity_score": 94,
                "bona_fide_probability": 94,
                "worst_window_bona_fide": 94,
                "confidence_spread": 1.0,
                "engine_stable": True,
            },
            q,
        )
        self.assertEqual(anti["voice_label"], "INCONCLUSIVE_QUALITY")
        r = analyse_interaction("Hey, how are you?", voice_label=anti["voice_label"])
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_missing_antispoof_does_not_raise_interaction_risk(self):
        r = analyse_interaction("Hey, are we still meeting at five?", voice_label="UNAVAILABLE")
        self.assertEqual(r["voice_display"], "UNAVAILABLE")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_entity_extraction(self):
        ents = extract_entities("Transfer ₹50,000 to account 1234567890.")
        types = {e["type"] for e in ents}
        self.assertIn("AMOUNT", types)
        self.assertIn("ACCOUNT", types)

    def test_conversation_state_accumulates(self):
        state = new_conversation_state()
        r1 = analyse_interaction(
            "I am calling from your bank.",
            identity_status="UNVERIFIED",
            conversation_state=state,
        )
        r2 = analyse_interaction(
            "Share the OTP.",
            identity_status="UNVERIFIED",
            conversation_state=r1["conversation_state"],
        )
        self.assertGreaterEqual(len(r2["conversation_state"]["intents"]), 2)
        self.assertLessEqual(r2["trust_score"], r1["trust_score"])


class IntentGuardTests(unittest.TestCase):
    def test_past_otp_is_not_request(self):
        r = classify_intent("Someone asked me for my OTP yesterday.")
        self.assertNotEqual(r["intent"], "credential_request")

    def test_received_otp_is_not_request(self):
        r = classify_intent("I received an OTP.")
        self.assertNotEqual(r["intent"], "credential_request")


class AdversarialHardeningTests(unittest.TestCase):
    def _risk(self, text, **kwargs):
        return analyse_interaction(text, **kwargs)

    def test_benign_sensitive_words(self):
        cases = [
            "How are you?",
            "Let's discuss the project tomorrow.",
            "I need to check my bank balance.",
            "I received my salary today.",
            "The payment was successful.",
            "I sent ₹500 to Rahul.",
            "I forgot my password.",
            "I am going to reset my password.",
            "The bank told me never to share my OTP.",
        ]
        for text in cases:
            with self.subTest(text=text):
                r = self._risk(text)
                self.assertNotEqual(r["interaction_risk"], "CRITICAL", text)
                self.assertFalse(r["handshake_required"], text)
                self.assertNotEqual(r["intent"]["intent"], "credential_request", text)

    def test_security_advice_not_credential(self):
        for text in [
            "Never share your OTP.",
            "The bank will never ask for your PIN.",
            "Don't give anyone your password.",
            "Remember, never transfer money to an unknown account.",
        ]:
            with self.subTest(text=text):
                r = classify_intent(text)
                self.assertNotEqual(r["intent"], "credential_request")
                self.assertNotEqual(self._risk(text)["interaction_risk"], "CRITICAL")

    def test_past_events_not_live_requests(self):
        for text in [
            "Someone asked me for my OTP yesterday.",
            "I already gave the payment yesterday.",
            "He threatened me for my password.",
            "The scammer asked for my bank details.",
        ]:
            with self.subTest(text=text):
                r = self._risk(text)
                self.assertNotEqual(r["intent"]["intent"], "credential_request")
                self.assertNotEqual(r["interaction_risk"], "CRITICAL")

    def test_direct_attacks(self):
        mapping = [
            ("Tell me your OTP.", "credential_request"),
            ("Send me your UPI PIN.", "credential_request"),
            ("Give me your password.", "credential_request"),
            ("Transfer ₹50,000 to this account.", "financial_request"),
            ("Send the employee database to my personal Gmail.", "sensitive_data_request"),
        ]
        for text, intent in mapping:
            with self.subTest(text=text):
                r = self._risk(text)
                self.assertEqual(r["intent"]["intent"], intent)
                self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_negation(self):
        for text in [
            "I will NOT share my OTP.",
            "I am not asking for your password.",
            "Don't send money to this account.",
        ]:
            with self.subTest(text=text):
                r = self._risk(text)
                self.assertNotEqual(r["intent"]["intent"], "credential_request")
                self.assertNotEqual(r["interaction_risk"], "CRITICAL")

    def test_financial_benign_not_critical(self):
        for text in [
            "What is my account balance?",
            "I received ₹20,000 today.",
            "Can you explain NEFT?",
            "When will my salary arrive?",
            "I made a UPI payment.",
            "My bank account is frozen.",
            "I need to update my bank details.",
        ]:
            with self.subTest(text=text):
                r = self._risk(text)
                self.assertNotEqual(r["interaction_risk"], "CRITICAL")
                self.assertNotEqual(r["intent"]["intent"], "credential_request")

    def test_entity_extraction_variants(self):
        text = (
            "Transfer INR 50000 or Rs 50,000 to account 1234567890 via UPI/NEFT/IMPS/RTGS. "
            "Call 9876543210 or rahul@gmail.com. The manager and CEO in HR want "
            "the employee database, customer records, KYC, payroll and salary data. "
            "Bank security team mentioned a new bank account and personal account."
        )
        types = {e["type"] for e in extract_entities(text)}
        for needed in {
            "AMOUNT", "ACCOUNT", "PHONE", "EMAIL", "PAYMENT_METHOD",
            "DOCUMENT", "PERSON_ROLE", "BANK",
        }:
            self.assertIn(needed, types)
        r = self._risk("I received ₹20,000 today.")
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")

    def test_behaviour_urgency_gradation(self):
        low = self._risk("Please send the report when you have time.")
        med = self._risk("Please send the report today.")
        high = self._risk("Send the report immediately.")
        combo = self._risk(
            "Send the employee database to my personal email immediately. Don't tell anyone."
        )
        self.assertEqual(low["behaviour"]["behaviour_level"], "LOW")
        self.assertEqual(med["behaviour"]["behaviour_level"], "MEDIUM")
        self.assertEqual(high["behaviour"]["behaviour_level"], "HIGH")
        self.assertNotEqual(high["interaction_risk"], "CRITICAL")
        self.assertEqual(combo["interaction_risk"], "CRITICAL")

    def test_context_identity_principles(self):
        benign_unverified = self._risk("Hey, how are you?", identity_status="UNVERIFIED")
        self.assertEqual(benign_unverified["interaction_risk"], "LOW")
        verified_danger = self._risk(
            "Send the employee database to my personal Gmail and don't tell anyone.",
            identity_status="VERIFIED",
        )
        self.assertIn(verified_danger["interaction_risk"], {"HIGH", "CRITICAL"})
        otp_unverified = self._risk("Tell me your OTP.", identity_status="UNVERIFIED")
        self.assertIn(otp_unverified["interaction_risk"], {"HIGH", "CRITICAL"})
        mismatch = self._risk(
            "Send the employee database to my personal Gmail.",
            identity_status="MISMATCH",
        )
        self.assertIn(mismatch["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_social_engineering_signals(self):
        r = self._risk(
            "I am your manager. Send the employee database immediately. "
            "Don't tell anyone. Don't verify it with anyone.",
            identity_status="UNVERIFIED",
        )
        sigs = set(r["behaviour"]["signals"])
        self.assertTrue({"urgency", "secrecy"} <= sigs or "verification_bypass" in sigs)
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_conversation_escalation_and_clarification(self):
        s = new_conversation_state()
        r1 = analyse_interaction(
            "Send me your OTP.", identity_status="UNVERIFIED", conversation_state=s,
        )
        self.assertIn(r1["interaction_risk"], {"HIGH", "CRITICAL"})
        r2 = analyse_interaction(
            "No, I meant I received an OTP from the bank.",
            identity_status="UNVERIFIED",
            conversation_state=r1["conversation_state"],
        )
        r3 = analyse_interaction(
            "The bank said never to share it.",
            identity_status="UNVERIFIED",
            conversation_state=r2["conversation_state"],
        )
        self.assertNotEqual(r3["interaction_risk"], "CRITICAL")
        self.assertFalse(r3["handshake_required"])
        self.assertGreater(r3["trust_score"], r1["trust_score"])

    def test_database_clarification(self):
        s = new_conversation_state()
        r1 = analyse_interaction(
            "Please send the employee database.", conversation_state=s,
        )
        r2 = analyse_interaction(
            "I meant the publicly available employee list from the website.",
            conversation_state=r1["conversation_state"],
        )
        self.assertNotEqual(r2["interaction_risk"], "CRITICAL")

    def test_conversation_reset(self):
        s = new_conversation_state()
        r1 = analyse_interaction("Give me your password.", conversation_state=s)
        self.assertIn(r1["interaction_risk"], {"HIGH", "CRITICAL"})
        fresh = new_conversation_state()
        r2 = analyse_interaction("How are you?", conversation_state=fresh)
        self.assertEqual(r2["interaction_risk"], "LOW")
        self.assertFalse(r2["handshake_required"])

    def test_handshake_trigger(self):
        r = self._risk(
            "I am your manager. Send the employee database to my personal Gmail immediately and don't tell anyone.",
            identity_status="UNVERIFIED",
        )
        self.assertTrue(r["handshake_required"])
        self.assertEqual(r["action"], "CRITICAL INTERVENTION")
        r = self._risk("How was your trip?")
        self.assertFalse(r["handshake_required"])

    def test_repeated_sensitive_stays_high(self):
        s = new_conversation_state()
        r1 = analyse_interaction("Tell me your OTP.", conversation_state=s)
        r2 = analyse_interaction(
            "Send me your UPI PIN.", conversation_state=r1["conversation_state"],
        )
        self.assertIn(r2["interaction_risk"], {"HIGH", "CRITICAL"})
        self.assertLessEqual(r2["trust_score"], r1["trust_score"])

    def test_demo_voice_label_is_illustrative(self):
        r = analyse_interaction(
            "Hello.",
            voice_label="LIKELY_AUTHENTIC",
            source="DEMO SCENARIO",
        )
        self.assertIn("illustrative", r["voice_display"].lower())
        self.assertNotIn("model detected", r["voice_display"].lower())


if __name__ == "__main__":
    unittest.main()

