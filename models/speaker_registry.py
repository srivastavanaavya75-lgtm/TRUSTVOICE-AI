"""Speaker enrollment registry for TRUSTVOICE AI.

Stores speaker profiles (name, role, voice samples) on disk as JSON and
derives a speaker embedding from AASIST window-level CM logits.

The embedding is the mean of per-window raw logit pairs across all enrolled
samples.  It intentionally reuses the already-cached AASIST ONNX session so
the model is never loaded twice.

Storage layout:
  models/speaker_profiles.json  — persisted index
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None

from utils.audio import (
    decode_audio_bytes,
    normalize_model_audio,
    make_deterministic_windows,
    quality_gate,
)

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_PROFILES_PATH = Path(__file__).resolve().parent / "speaker_profiles.json"

# In-memory cache of loaded profiles  {profile_id: dict}
_PROFILE_CACHE: dict[str, dict] | None = None

SAMPLE_FORMATS = ["wav", "mp3", "m4a", "flac", "ogg", "aac",
                  "mpeg", "mpga", "opus", "oga", "mp4", "webm"]

MIN_SAMPLES = 3
MAX_SAMPLES = 5
MIN_DURATION_SEC = 1.5   # from quality_gate
MAX_DURATION_SEC = 120.0  # sanity cap per sample


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_from_disk() -> dict[str, dict]:
    """Load profiles from JSON; return empty dict on any error."""
    if not _PROFILES_PATH.exists():
        return {}
    try:
        raw = _PROFILES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def _save_to_disk(profiles: dict[str, dict]) -> None:
    """Persist profiles dict to JSON.  Embeddings stored as lists."""
    _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Convert numpy arrays to plain lists before serialising
    serialisable = {}
    for pid, prof in profiles.items():
        p = dict(prof)
        emb = p.get("embedding")
        if emb is not None and np is not None and isinstance(emb, np.ndarray):
            p["embedding"] = emb.tolist()
        serialisable[pid] = p
    _PROFILES_PATH.write_text(
        json.dumps(serialisable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _profiles() -> dict[str, dict]:
    """Return the in-memory profile cache, loading from disk if needed."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is None:
        _PROFILE_CACHE = _load_from_disk()
    return _PROFILE_CACHE


def _persist() -> None:
    _save_to_disk(_profiles())


# ---------------------------------------------------------------------------
# AASIST embedding extraction
# ---------------------------------------------------------------------------

def _extract_raw_logits(audio: "np.ndarray", sr: int, session) -> list[list[float]]:
    """Run AASIST on all speech-bearing windows; return raw output pairs."""
    if np is None:
        return []
    audio, sr = normalize_model_audio(audio, sr)
    windows, _ = make_deterministic_windows(audio)
    input_name = session.get_inputs()[0].name

    results = []
    for win in windows:
        x = np.ascontiguousarray(win.reshape(1, -1), dtype=np.float32)
        try:
            expected = session.get_inputs()[0].shape
            if expected is not None and len(expected) == 3:
                x = x.reshape(1, 1, -1)
        except Exception:
            pass
        outputs = session.run(None, {input_name: x})
        if outputs:
            raw = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
            results.append([float(raw[0]), float(raw[1])] if raw.size >= 2 else [float(raw[0]), 0.0])
    return results


def _mean_embedding(all_logit_pairs: list[list[float]]) -> "np.ndarray | None":
    """Mean-pool all [spoof_logit, bona_logit] vectors into one embedding."""
    if np is None or not all_logit_pairs:
        return None
    arr = np.array(all_logit_pairs, dtype=np.float64)
    return np.mean(arr, axis=0)  # shape (2,)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_profiles() -> list[dict]:
    """Return all profiles sorted by creation time, embeddings stripped."""
    profs = _profiles()
    out = []
    for pid, p in profs.items():
        summary = {
            "id": pid,
            "name": p.get("name", ""),
            "role": p.get("role", ""),
            "sample_count": len(p.get("samples", [])),
            "enrolled": p.get("enrolled", False),
            "created_at": p.get("created_at", 0),
            "enrolled_at": p.get("enrolled_at"),
        }
        out.append(summary)
    out.sort(key=lambda x: x["created_at"])
    return out


def get_profile(profile_id: str) -> dict | None:
    """Return full profile dict or None."""
    return _profiles().get(profile_id)


def create_profile(name: str, role: str) -> dict:
    """Create and persist an empty profile; return the new profile."""
    if not name.strip():
        raise ValueError("Name must not be empty.")
    pid = str(uuid.uuid4())
    now = time.time()
    profile = {
        "id": pid,
        "name": name.strip(),
        "role": role.strip(),
        "samples": [],          # list of {filename, duration, quality, issues}
        "embedding": None,      # serialised as list[float]
        "enrolled": False,
        "created_at": now,
        "enrolled_at": None,
    }
    _profiles()[pid] = profile
    _persist()
    return profile


def delete_profile(profile_id: str) -> bool:
    """Delete profile from registry; return True if it existed."""
    profs = _profiles()
    if profile_id not in profs:
        return False
    del profs[profile_id]
    _persist()
    return True


def validate_sample(raw: bytes, filename: str) -> dict:
    """Decode and validate a single audio sample.

    Returns a dict with keys:
      ok        — bool, True if sample passes all checks
      errors    — list[str] of human-readable errors
      warnings  — list[str]
      duration  — float | None
      quality   — dict | None (quality_gate output)
      samples   — np.ndarray | None (decoded PCM, 16 kHz)
      sample_rate — int
    """
    errors: list[str] = []
    warnings: list[str] = []
    decoded: Any = None
    quality: dict | None = None
    audio_samples = None
    sr = 16000

    if not raw:
        errors.append("File is empty.")
        return {"ok": False, "errors": errors, "warnings": warnings,
                "duration": None, "quality": None, "samples": None, "sample_rate": sr}

    if len(raw) > 200 * 1024 * 1024:
        errors.append("File exceeds 200 MB limit.")
        return {"ok": False, "errors": errors, "warnings": warnings,
                "duration": None, "quality": None, "samples": None, "sample_rate": sr}

    # Full pipeline decode (FFmpeg → PCM, resamples to 16 kHz)
    decoded = decode_audio_bytes(raw, filename)

    if decoded.get("user_error"):
        errors.append(decoded["user_error"])
    if decoded.get("limitations"):
        for lim in decoded["limitations"]:
            if lim not in errors:
                warnings.append(lim)

    audio_samples = decoded.get("samples")
    if audio_samples is None and not errors:
        errors.append(
            "Audio could not be decoded. "
            "Please upload WAV, MP3, M4A, FLAC, OGG, or AAC."
        )

    duration = decoded.get("duration")
    if duration is not None:
        if duration < MIN_DURATION_SEC:
            errors.append(
                f"Sample is too short ({duration:.1f} s). "
                f"Minimum required is {MIN_DURATION_SEC} s."
            )
        elif duration > MAX_DURATION_SEC:
            warnings.append(
                f"Sample is very long ({duration:.1f} s). "
                "Only the first portion will be used for embedding."
            )

    if audio_samples is not None:
        quality = decoded.get("quality_gate") or quality_gate(audio_samples, decoded.get("sample_rate") or 16000)
        q_issues = quality.get("issues", [])
        # Fail on truly unusable audio; warn on marginal
        critical_issues = [i for i in q_issues if "empty" in i.lower() or "low signal" in i.lower()]
        marginal_issues = [i for i in q_issues if i not in critical_issues]
        for issue in critical_issues:
            errors.append(issue)
        for issue in marginal_issues:
            warnings.append(issue)
        sr = decoded.get("sample_rate") or 16000

    ok = len(errors) == 0 and audio_samples is not None
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "duration": duration,
        "quality": quality,
        "samples": audio_samples,
        "sample_rate": sr,
    }


def enroll_profile(
    profile_id: str,
    sample_results: list[dict],
    model_key: str = "aasist",
    allow_download: bool = True,
) -> dict:
    """Generate and persist the enrollment embedding from validated samples.

    Args:
        profile_id:     ID of an existing profile.
        sample_results: list of dicts returned by validate_sample() (must be ok=True).
        model_key:      AASIST variant key.
        allow_download: whether to allow model download if not present.

    Returns:
        Updated profile dict with 'enrolled' = True, or raises on failure.
    """
    if np is None:
        raise RuntimeError("numpy is required for speaker enrollment.")

    profs = _profiles()
    if profile_id not in profs:
        raise ValueError(f"Profile {profile_id} not found.")

    valid = [r for r in sample_results if r.get("ok") and r.get("samples") is not None]
    if len(valid) < MIN_SAMPLES:
        raise ValueError(
            f"At least {MIN_SAMPLES} valid voice samples are required "
            f"(got {len(valid)})."
        )
    if len(valid) > MAX_SAMPLES:
        valid = valid[:MAX_SAMPLES]

    # Import here to avoid circular dependency
    from models.antispoof import get_onnx_session

    session = get_onnx_session(model_key, allow_download=allow_download)

    all_logits: list[list[float]] = []
    sample_meta: list[dict] = []
    for i, r in enumerate(valid):
        logits = _extract_raw_logits(r["samples"], r["sample_rate"], session)
        all_logits.extend(logits)
        sample_meta.append({
            "index": i + 1,
            "filename": r.get("filename", f"sample_{i+1}"),
            "duration": r.get("duration"),
            "quality": r.get("quality", {}).get("quality", "UNKNOWN"),
            "issues": r.get("quality", {}).get("issues", []),
        })

    if not all_logits:
        raise RuntimeError(
            "No audio windows could be extracted from the provided samples. "
            "Ensure samples contain clear speech."
        )

    embedding = _mean_embedding(all_logits)
    profile = profs[profile_id]
    profile["samples"] = sample_meta
    profile["embedding"] = embedding.tolist() if embedding is not None else None
    profile["enrolled"] = True
    profile["enrolled_at"] = time.time()
    _persist()
    return profile


def re_enroll_profile(profile_id: str) -> dict | None:
    """Clear enrollment data so the profile can be re-enrolled.  Returns updated profile."""
    profs = _profiles()
    if profile_id not in profs:
        return None
    profs[profile_id]["samples"] = []
    profs[profile_id]["embedding"] = None
    profs[profile_id]["enrolled"] = False
    profs[profile_id]["enrolled_at"] = None
    _persist()
    return profs[profile_id]
