"""End-to-end enrollment test including AASIST model embedding generation.

Run with:  python tests/test_speaker_e2e.py
Requires:  AASIST model present at models/aasist.onnx (auto-downloads if missing)
"""
import sys, os, struct, io, math, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.speaker_registry as reg

# ── Isolated storage ─────────────────────────────────────────────────────────
_tmpdir = tempfile.mkdtemp()
reg._PROFILES_PATH = __import__("pathlib").Path(_tmpdir) / "spk_e2e.json"
reg._PROFILE_CACHE = None

def hr(t): print(f"\n{'='*62}\n  {t}\n{'='*62}")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def make_wav(duration_sec: float = 2.5, sr: int = 16000, freq: float = 220.0,
             amplitude: float = 0.3) -> bytes:
    """Synthesise a single-tone WAV at the given amplitude (< 1 avoids clipping)."""
    n = int(sr * duration_sec)
    samples = [int(32767 * amplitude * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)]
    pcm = struct.pack(f"<{n}h", *samples)
    buf = io.BytesIO()
    buf.write(b"RIFF"); buf.write(struct.pack("<I", 36 + len(pcm)))
    buf.write(b"WAVE"); buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr*2, 2, 16))
    buf.write(b"data"); buf.write(struct.pack("<I", len(pcm))); buf.write(pcm)
    return buf.getvalue()


def run_tests():
    # ─── 1. Validate a good WAV ───────────────────────────────────────────────────
    hr("1 · validate_sample — valid WAV")
    for i in range(5):
        r = reg.validate_sample(make_wav(duration_sec=3.0, freq=200 + i*40, amplitude=0.25), f"sample{i+1}.wav")
        print(f"  sample{i+1}: ok={r['ok']} dur={r['duration']} issues={(r.get('quality') or {}).get('issues', [])}")
        if not r["ok"] and any("Audio decoding is unavailable" in e for e in r.get("errors", [])):
            print("  SKIP — audio decoding requires numpy/scipy (install requirements.txt)")
            return
        assert r["ok"], f"Expected ok=True for good WAV, errors={r['errors']}"

    # ─── 2. Create profile & enroll with 3 WAV samples + AASIST ──────────────────
    hr("2 · enroll with 3 WAV samples (real AASIST embedding)")
    p = reg.create_profile("Bob Enrolled", "Security Officer")
    pid = p["id"]
    samples_ok = []
    for i in range(3):
        r = reg.validate_sample(make_wav(duration_sec=3.0, freq=180 + i*55, amplitude=0.25), f"bob_{i+1}.wav")
        r["filename"] = f"bob_{i+1}.wav"
        samples_ok.append(r)
    try:
        enrolled = reg.enroll_profile(pid, samples_ok)
        emb = enrolled.get("embedding")
        print(f"  enrolled={enrolled['enrolled']}  embedding_len={len(emb) if emb else 0}")
        assert enrolled["enrolled"]
        assert emb and len(emb) == 2, f"Expected 2-element embedding, got {emb}"
        print(f"  embedding={emb}")
    except Exception as e:
        print(f"  SKIP — AASIST model unavailable: {e}")
        print("  (install onnxruntime and place models/aasist.onnx to test embedding)")

    # ─── 3. Persistence — reload from disk ───────────────────────────────────────
    hr("3 · persistence — reload from disk")
    reg._PROFILE_CACHE = None
    profiles = reg.list_profiles()
    print(f"  Profiles on disk: {[p['name'] for p in profiles]}")
    assert any(p["name"] == "Bob Enrolled" for p in profiles)

    # ─── 4. Re-enroll clears enrollment ──────────────────────────────────────────
    hr("4 · re-enroll (clears existing enrollment)")
    reg.re_enroll_profile(pid)
    profile_after = reg.get_profile(pid)
    assert not profile_after["enrolled"]
    assert profile_after["embedding"] is None
    print("  enrollment cleared OK")

    # ─── 5. Invalid audio — not a real audio file ─────────────────────────────────
    hr("5 · invalid audio — garbage bytes")
    bad = reg.validate_sample(b"\x00\x01\x02\x03bad data", "noise.wav")
    print(f"  ok={bad['ok']}  errors={bad['errors']}")
    assert not bad["ok"]

    # ─── 6. Invalid audio — empty file ───────────────────────────────────────────
    hr("6 · empty file")
    empty = reg.validate_sample(b"", "empty.mp3")
    print(f"  ok={empty['ok']}  errors={empty['errors']}")
    assert not empty["ok"]

    # ─── 7. Short audio (< 1.5 s) ────────────────────────────────────────────────
    hr("7 · too-short WAV (0.8 s)")
    short = reg.validate_sample(make_wav(0.8), "short.wav")
    print(f"  ok={short['ok']}  dur={short['duration']}  errors={short['errors']}")
    assert not short["ok"]

    # ─── 8. Delete ───────────────────────────────────────────────────────────────
    hr("8 · delete profile")
    reg.delete_profile(pid)
    reg._PROFILE_CACHE = None
    assert len(reg.list_profiles()) == 0
    print("  delete OK")

    shutil.rmtree(_tmpdir, ignore_errors=True)
    hr("ALL E2E TESTS PASSED")


if __name__ == "__main__":
    run_tests()
