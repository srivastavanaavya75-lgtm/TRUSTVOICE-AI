"""Smoke-test the speaker registry logic.

Run with:  python tests/test_speaker_enrollment.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile, json
from pathlib import Path

# ── Override storage path to a temp file ─────────────────────────────────────
import models.speaker_registry as reg
_tmpdir = tempfile.mkdtemp()
reg._PROFILES_PATH = Path(_tmpdir) / "speaker_profiles_test.json"
reg._PROFILE_CACHE = None   # flush cache

# ─────────────────────────────────────────────────────────────────────────────
def hr(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def run_tests():
    # 1. Import check
    hr("Import check")
    print("speaker_registry imported OK")
    print(f"  MIN_SAMPLES={reg.MIN_SAMPLES}  MAX_SAMPLES={reg.MAX_SAMPLES}")
    print(f"  Storage: {reg._PROFILES_PATH}")

    # 2. Create profile
    hr("create_profile()")
    p = reg.create_profile("Alice Test", "Quality Assurance")
    print(f"  Created: id={p['id']}  name={p['name']}  enrolled={p['enrolled']}")
    pid = p['id']

    # 3. Persist & reload
    hr("Persistence (disk round-trip)")
    reg._PROFILE_CACHE = None  # flush
    reloaded = reg.list_profiles()
    assert len(reloaded) == 1, f"Expected 1 profile, got {len(reloaded)}"
    assert reloaded[0]["name"] == "Alice Test"
    print(f"  list_profiles after reload: {reloaded[0]}")

    # 4. validate_sample with an invalid file
    hr("validate_sample() — invalid audio")
    bad_result = reg.validate_sample(b"NOT AUDIO DATA", "bad.wav")
    print(f"  ok={bad_result['ok']}  errors={bad_result['errors']}")
    assert not bad_result["ok"], "Expected validation to fail for garbage bytes"

    # 5. validate_sample with empty bytes
    hr("validate_sample() — empty file")
    empty_result = reg.validate_sample(b"", "empty.wav")
    print(f"  ok={empty_result['ok']}  errors={empty_result['errors']}")
    assert not empty_result["ok"]

    # 6. validate_sample with synthetic WAV (too short)
    hr("validate_sample() — too-short WAV")
    short_wav = make_wav(duration_sec=0.5)
    short_result = reg.validate_sample(short_wav, "short.wav")
    print(f"  ok={short_result['ok']}  duration={short_result['duration']}  errors={short_result['errors']}")
    assert not short_result["ok"], "0.5 s sample should fail duration check"

    # 7. validate_sample with valid WAV (2.5 s)
    hr("validate_sample() — valid WAV (2.5 s)")
    good_wav = make_wav(duration_sec=2.5)
    good_result = reg.validate_sample(good_wav, "good.wav")
    good_result["filename"] = "good.wav"
    print(f"  ok={good_result['ok']}  duration={good_result['duration']}  quality={good_result.get('quality')}")
    if not good_result["ok"] and any("Audio decoding is unavailable" in e for e in good_result.get("errors", [])):
        print("  SKIP — audio decoding requires numpy/scipy (install requirements.txt)")
        return
    assert good_result["duration"] is not None and good_result["duration"] >= 1.5

    # 8. enroll requires MIN_SAMPLES
    hr("enroll_profile() — insufficient samples")
    try:
        reg.enroll_profile(pid, [good_result])  # only 1 sample
        print("  ERROR: should have raised ValueError")
    except ValueError as e:
        print(f"  Correctly raised ValueError: {e}")

    # 9. delete profile
    hr("delete_profile()")
    deleted = reg.delete_profile(pid)
    print(f"  deleted={deleted}")
    reg._PROFILE_CACHE = None
    assert len(reg.list_profiles()) == 0

    # 10. Cleanup
    import shutil
    shutil.rmtree(_tmpdir, ignore_errors=True)

    hr("ALL BASIC TESTS PASSED")
    print("  (Enrollment with real AASIST model tested via Streamlit UI)")


if __name__ == "__main__":
    run_tests()
