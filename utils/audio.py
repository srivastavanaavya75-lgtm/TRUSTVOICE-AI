"""Deterministic 16 kHz audio helpers and quality gating."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

try:
    import librosa
except ImportError:
    librosa = None

AASIST_WINDOW = 64600
AASIST_HOP = 32300
AASIST_MAX_WINDOWS = 7
MAX_INPUT_BYTES = 200 * 1024 * 1024
DECODE_FORMAT_HELP = (
    "Audio format could not be decoded. Please upload WAV, MP3, M4A, OGG, or WebM."
)
FFMPEG_TIMEOUT_SEC = 90
_FFMPEG_EXE = None
_FFMPEG_CHECKED = False


def speech_ratio(chunk, floor: float = 0.006) -> float:
    if np is None or chunk is None or getattr(chunk, "size", 0) < 400:
        return 0.0
    frame, hop = 400, 160
    n = 1 + (chunk.size - frame) // hop
    strided = np.lib.stride_tricks.as_strided(
        chunk,
        shape=(n, frame),
        strides=(chunk.strides[0] * hop, chunk.strides[0]),
    )
    rms = np.sqrt(np.mean(np.square(strided, dtype=np.float64), axis=1))
    return float(np.mean(rms > floor))


def quality_gate(audio, sample_rate: int) -> dict:
    if np is None:
        return {
            "duration": 0.0, "rms": 0.0, "clipping_ratio": 0.0,
            "speech_activity_ratio": 0.0, "quality": "REVIEW",
            "issues": ["numpy is required for audio quality checks"],
        }
    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    duration = float(len(a) / sample_rate) if sample_rate else 0.0
    rms = float(np.sqrt(np.mean(np.square(a, dtype=np.float64)))) if len(a) else 0.0
    clipping_ratio = float(np.mean(np.abs(a) >= 0.999)) if len(a) else 0.0
    ratio = speech_ratio(np.ascontiguousarray(a), floor=max(0.006, rms * 0.12))

    issues = []
    if a.size == 0:
        issues.append("Corrupted or empty audio")
    if duration < 1.5:
        issues.append("Sample shorter than 1.5 s")
    if rms < 0.003:
        issues.append("Very low signal energy")
    if clipping_ratio > 0.02:
        issues.append("Significant clipping")
    if ratio < 0.15:
        issues.append("Low speech/activity ratio")

    return {
        "duration": round(duration, 3),
        "rms": round(rms, 6),
        "clipping_ratio": round(clipping_ratio * 100, 3),
        "speech_activity_ratio": round(ratio * 100, 2),
        "quality": "GOOD" if not issues else "REVIEW",
        "issues": issues,
    }


def normalize_model_audio(audio, sample_rate: int):
    if np is None:
        raise RuntimeError("numpy is required for anti-spoof inference.")
    if librosa is None:
        raise RuntimeError("librosa is required for audio preprocessing.")

    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        raise ValueError("No audio samples were decoded.")
    if sample_rate != 16000:
        audio = librosa.resample(
            audio, orig_sr=int(sample_rate), target_sr=16000, res_type="kaiser_best",
        )
        sample_rate = 16000
    audio = np.nan_to_num(
        np.asarray(audio, dtype=np.float32).reshape(-1),
        nan=0.0, posinf=0.0, neginf=0.0,
    )
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    return np.ascontiguousarray(audio, dtype=np.float32), 16000


def fixed_window(audio, length: int = AASIST_WINDOW):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        raise ValueError("No audio samples were decoded.")
    if audio.size >= length:
        return np.ascontiguousarray(audio[:length], dtype=np.float32)
    reps = int(np.ceil(length / audio.size))
    return np.ascontiguousarray(np.tile(audio, reps)[:length], dtype=np.float32)


def make_deterministic_windows(
    audio,
    window_len=AASIST_WINDOW,
    hop=AASIST_HOP,
    max_windows=AASIST_MAX_WINDOWS,
):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size <= window_len:
        return [fixed_window(audio, window_len)], 0

    starts = list(range(0, audio.size - window_len + 1, hop))
    final_start = audio.size - window_len
    if len(starts) > max_windows:
        idx = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in sorted(set(int(v) for v in idx))]
    if final_start not in starts:
        starts.append(final_start)
    if 0 not in starts:
        starts.insert(0, 0)

    candidates = [
        np.ascontiguousarray(audio[s:s + window_len], dtype=np.float32)
        for s in sorted(set(starts))
    ]
    speech_bearing = [w for w in candidates if speech_ratio(w) >= 0.25]
    dropped = len(candidates) - len(speech_bearing)
    if speech_bearing:
        first = fixed_window(audio, window_len)
        if not any(np.array_equal(first, w) for w in speech_bearing):
            speech_bearing.insert(0, first)
            dropped = max(0, dropped - 1)
        return speech_bearing, dropped
    return candidates, 0


def waveform_envelope(audio, bars: int = 48) -> list[int]:
    if np is None or audio is None or getattr(audio, "size", 0) == 0:
        return [12] * bars
    a = np.abs(np.asarray(audio, dtype=np.float32).reshape(-1))
    step = max(1, a.size // bars)
    env = [float(np.mean(a[i:i + step])) for i in range(0, min(a.size, step * bars), step)]
    peak = max(env) or 1.0
    return [int(8 + 90 * (v / peak)) for v in env[:bars]]


def sniff_audio_kind(raw: bytes, filename: str = "") -> str:
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    head = raw[:16] if raw else b""
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"fLaC"):
        return "flac"
    if head.startswith(b"OggS"):
        return "ogg"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "webm"
    if len(raw) >= 8 and raw[4:8] == b"ftyp":
        return "mp4"
    if head.startswith(b"ID3") or (
        len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0
    ):
        return "mp3"
    aliases = {
        "mpga": "mp3", "mpeg": "mp3", "mp2": "mp3",
        "opus": "ogg", "oga": "ogg",
        "m4a": "mp4", "aac": "mp4", "3gp": "mp4", "3gpp": "mp4", "amr": "amr",
        "weba": "webm",
    }
    return aliases.get(suffix, suffix or "unknown")


def ffmpeg_executable() -> str | None:
    global _FFMPEG_EXE, _FFMPEG_CHECKED
    if _FFMPEG_CHECKED:
        return _FFMPEG_EXE
    _FFMPEG_CHECKED = True
    found = shutil.which("ffmpeg")
    if found:
        _FFMPEG_EXE = found
        return _FFMPEG_EXE
    try:
        import imageio_ffmpeg
        _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        _FFMPEG_EXE = None
    return _FFMPEG_EXE


def ffmpeg_available() -> bool:
    return bool(ffmpeg_executable())


def _ffmpeg_to_wav16k(raw: bytes, suffix: str) -> tuple[bytes | None, str | None]:
    exe = ffmpeg_executable()
    if not exe:
        return None, "FFmpeg is not available on the server; compressed audio cannot be decoded."
    ext = suffix if suffix.startswith(".") else f".{suffix or 'bin'}"
    if ext == ".unknown":
        ext = ".bin"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / f"input{ext}"
            wav_path = Path(tmpdir) / "canonical.wav"
            input_path.write_bytes(raw)
            proc = subprocess.run(
                [
                    exe, "-y", "-i", str(input_path),
                    "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(wav_path),
                ],
                capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SEC,
            )
            if proc.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size < 44:
                err = (proc.stderr or proc.stdout or "").strip()[-240:] or "no audio track"
                return None, err
            return wav_path.read_bytes(), None
    except subprocess.TimeoutExpired:
        return None, "Audio conversion timed out."
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _pcm_from_wav_bytes(wav_bytes: bytes):
    if np is None:
        return None
    try:
        import soundfile as sf
        data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
        y = np.asarray(data, dtype=np.float32).reshape(-1)
        if int(sr) != 16000 and librosa is not None:
            y = librosa.resample(y, orig_sr=int(sr), target_sr=16000, res_type="kaiser_fast")
            sr = 16000
        return np.ascontiguousarray(y, dtype=np.float32), int(sr)
    except Exception:
        pass
    if librosa is None:
        return None
    try:
        y, sr = librosa.load(io.BytesIO(wav_bytes), sr=16000, mono=True)
        return np.ascontiguousarray(np.asarray(y, dtype=np.float32).reshape(-1)), 16000
    except Exception:
        return None


def _try_direct_pcm(raw: bytes):
    loaded = _pcm_from_wav_bytes(raw)
    if loaded is not None:
        return loaded
    if librosa is None:
        return None
    try:
        y, sr = librosa.load(io.BytesIO(raw), sr=16000, mono=True)
        y = np.ascontiguousarray(np.asarray(y, dtype=np.float32).reshape(-1))
        if y.size == 0:
            return None
        return y, 16000
    except Exception:
        return None


def decode_audio_bytes(raw: bytes, filename: str) -> dict:
    kind = sniff_audio_kind(raw, filename)
    result = {
        "file": filename,
        "file_hash": hashlib.sha256(raw).hexdigest()[:16],
        "format": kind,
        "duration": None, "sample_rate": None, "channels": None,
        "rms": None, "zero_crossing_rate": None, "spectral_centroid": None,
        "analysis_mode": "Canonical 16 kHz mono PCM",
        "limitations": [], "anti_spoof": None, "quality_gate": None,
        "envelope": [], "samples": None, "user_error": None,
        "ffmpeg": bool(ffmpeg_executable()) if _FFMPEG_CHECKED else None,
        "decode_path": None,
    }
    if len(raw) > MAX_INPUT_BYTES:
        result["user_error"] = f"File exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MB analysis limit."
        result["limitations"].append(result["user_error"])
        return result
    if np is None:
        result["user_error"] = "Audio decoding is unavailable on the server."
        result["limitations"].append(result["user_error"])
        return result

    loaded = None
    if kind in {"wav", "flac"}:
        loaded = _try_direct_pcm(raw)
        if loaded is not None:
            result["decode_path"] = "direct"
    if loaded is None:
        wav_bytes, ferr = _ffmpeg_to_wav16k(raw, kind if kind != "unknown" else Path(filename).suffix.lower())
        if wav_bytes:
            loaded = _pcm_from_wav_bytes(wav_bytes)
            if loaded is not None:
                result["decode_path"] = "ffmpeg"
                result["analysis_mode"] = "FFmpeg canonical 16 kHz mono PCM"
        elif ferr:
            result["limitations"].append(ferr)
        if loaded is None:
            loaded = _try_direct_pcm(raw)
            if loaded is not None:
                result["decode_path"] = "direct-fallback"

    if loaded is None:
        result["user_error"] = DECODE_FORMAT_HELP
        result["limitations"].append(DECODE_FORMAT_HELP)
        return result

    y, sr = loaded
    y = np.ascontiguousarray(np.asarray(y, dtype=np.float32).reshape(-1))
    if y.size == 0:
        result["user_error"] = DECODE_FORMAT_HELP
        result["limitations"].append("Decoded stream contains no samples.")
        return result
    if int(sr) != 16000 and librosa is not None:
        y = np.ascontiguousarray(
            librosa.resample(y, orig_sr=int(sr), target_sr=16000, res_type="kaiser_fast"),
            dtype=np.float32,
        )
        sr = 16000
    result["duration"] = round(float(len(y) / sr), 2)
    result["sample_rate"] = int(sr)
    result["channels"] = 1
    result["quality_gate"] = quality_gate(y, sr)
    result["rms"] = round(float(np.sqrt(np.mean(np.square(y, dtype=np.float64)))), 5)
    result["input_fingerprint"] = hashlib.sha256(
        y.tobytes() + str(int(sr)).encode("utf-8")
    ).hexdigest()[:16]
    result["envelope"] = waveform_envelope(y)
    result["samples"] = y
    result["ffmpeg"] = ffmpeg_available()
    return result
