"""AASIST / W2V2-AASIST ONNX anti-spoof inference."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from utils.audio import (
    AASIST_WINDOW,
    decode_audio_bytes,
    fixed_window,
    make_deterministic_windows,
    normalize_model_audio,
)

try:
    import numpy as np
except ImportError:
    np = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

MODEL_REGISTRY = {
    "aasist": {
        "label": "AASIST (ASVspoof2019 LA)",
        "repo": "SpeechAntiSpoofingBenchmarks/AASIST",
        "filenames": ["aasist.onnx", "model.onnx", "aasist_model.onnx"],
        "local_name": "aasist.onnx",
        "min_bytes": 100_000,
        "approx_size": "~1.6 MB",
        "note": "Tiny and fast. Strong in-domain, weak on in-the-wild cloned speech.",
    },
    "w2v2-aasist": {
        "label": "W2V2-AASIST (wav2vec2 front-end)",
        "repo": "SpeechAntiSpoofingBenchmarks/W2V2-AASIST",
        "filenames": ["w2v2-aasist.onnx", "model.onnx"],
        "local_name": "w2v2-aasist.onnx",
        "min_bytes": 50_000_000,
        "approx_size": "~1 GB",
        "note": "Better generalisation to unseen synthesis. Slower, large download.",
    },
}

MODEL_DIR = Path(__file__).resolve().parent
BONA_FIDE_INDEX = 1
STABILITY_TOL = 1e-5
_SESSIONS = {}


def download_model(model_key: str, target: Path):
    spec = MODEL_REGISTRY[model_key]
    last_error = None
    for filename in spec["filenames"]:
        url = f"https://huggingface.co/{spec['repo']}/resolve/main/{filename}"
        tmp_path = target.with_suffix(target.suffix + ".part")
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "TRUSTVOICE-AI/2.0"}
            )
            with urllib.request.urlopen(request, timeout=300) as response, \
                    open(tmp_path, "wb") as handle:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
            if tmp_path.stat().st_size < spec["min_bytes"]:
                raise RuntimeError(
                    f"Downloaded file is only {tmp_path.stat().st_size} bytes; "
                    "this is an error page, not a model."
                )
            tmp_path.replace(target)
            return target
        except Exception as exc:
            last_error = exc
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    raise RuntimeError(
        f"Could not download {spec['label']} from {spec['repo']}. "
        f"Last error: {last_error}. Place the .onnx file in ./models/ or set "
        "TRUSTVOICE_MODEL_PATH."
    )


def model_path_for(model_key: str) -> Path:
    spec = MODEL_REGISTRY[model_key]
    override = os.environ.get("TRUSTVOICE_MODEL_PATH", "").strip()
    if override:
        return Path(override)
    return MODEL_DIR / spec["local_name"]


def model_available(model_key: str = "aasist") -> bool:
    return model_path_for(model_key).exists()


def get_onnx_session(model_key: str, allow_download: bool = True):
    if ort is None:
        raise RuntimeError(
            "Anti-spoof model unavailable: onnxruntime is not installed. "
            "Interaction analysis can still run, but voice authenticity cannot be established."
        )
    if model_key in _SESSIONS:
        return _SESSIONS[model_key]

    spec = MODEL_REGISTRY[model_key]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = model_path_for(model_key)
    if not path.exists():
        if not allow_download:
            raise RuntimeError(
                "Anti-spoof model unavailable. Interaction analysis can still run, "
                "but voice authenticity cannot be established."
            )
        download_model(model_key, path)

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        str(path), sess_options=session_options, providers=["CPUExecutionProvider"],
    )
    _SESSIONS[model_key] = session
    return session


def _softmax2(logits):
    logits = np.asarray(logits, dtype=np.float64).reshape(-1)[:2]
    logits = logits - np.max(logits)
    expv = np.exp(logits)
    return expv / np.sum(expv)


def cm_score(raw_out) -> float:
    raw_out = np.asarray(raw_out, dtype=np.float64).reshape(-1)
    if raw_out.size >= 2:
        return float(raw_out[BONA_FIDE_INDEX] - raw_out[1 - BONA_FIDE_INDEX])
    if raw_out.size == 1:
        return float(raw_out[0])
    raise RuntimeError("Unexpected model output shape.")


def sigmoid(x: float) -> float:
    x = float(np.clip(x, -60.0, 60.0))
    return float(1.0 / (1.0 + np.exp(-x)))


def _prepare_input(window, session):
    x = np.ascontiguousarray(window.reshape(1, -1), dtype=np.float32)
    try:
        expected = session.get_inputs()[0].shape
        if expected is not None and len(expected) == 3:
            x = x.reshape(1, 1, -1)
    except Exception:
        pass
    return np.ascontiguousarray(x, dtype=np.float32)


def run_antispoof_scores(audio, sample_rate: int, model_key: str, allow_download: bool = True):
    if np is None:
        raise RuntimeError("numpy is required for anti-spoof inference.")
    audio, sample_rate = normalize_model_audio(audio, sample_rate)
    windows, dropped = make_deterministic_windows(audio)
    session = get_onnx_session(model_key, allow_download=allow_download)
    input_name = session.get_inputs()[0].name

    cm_scores, raw_outputs = [], []
    for win in windows:
        outputs = session.run(None, {input_name: _prepare_input(win, session)})
        if not outputs:
            raise RuntimeError("Model returned no output.")
        raw = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        cm_scores.append(cm_score(raw))
        raw_outputs.append([round(float(v), 6) for v in raw[:2]])

    cm_array = np.asarray(cm_scores, dtype=np.float64)
    pooled_cm = float(np.mean(cm_array))
    worst_cm = float(np.min(cm_array))
    bona = sigmoid(pooled_cm)
    worst_bona = sigmoid(worst_cm)
    spread = float(np.std(np.asarray([sigmoid(v) for v in cm_array])))

    primary = fixed_window(audio)
    x_primary = _prepare_input(primary, session)
    repeat_a = np.asarray(session.run(None, {input_name: x_primary})[0], dtype=np.float32).reshape(-1)
    repeat_b = np.asarray(session.run(None, {input_name: x_primary})[0], dtype=np.float32).reshape(-1)
    repeat_delta = (
        float(np.max(np.abs(repeat_a[:2] - repeat_b[:2])))
        if repeat_a.size and repeat_b.size else float("inf")
    )
    spec = MODEL_REGISTRY[model_key]
    authenticity_score = int(round(bona * 100))
    return {
        "model": spec["label"],
        "model_source": spec["repo"],
        "sample_rate_used": sample_rate,
        "cm_score": round(pooled_cm, 4),
        "worst_window_cm": round(worst_cm, 4),
        "authenticity_score": authenticity_score,
        "bona_fide_probability": round(bona * 100, 2),
        "spoof_probability": round((1.0 - bona) * 100, 2),
        "worst_window_bona_fide": round(worst_bona * 100, 2),
        "windows_used": len(cm_scores),
        "windows_dropped_silent": dropped,
        "confidence_spread": round(spread * 100, 3),
        "repeatability_delta": repeat_delta,
        "engine_stable": repeat_delta <= STABILITY_TOL,
        "raw_output": raw_outputs[0] if raw_outputs else [],
        "window_samples": AASIST_WINDOW,
        "providers": session.get_providers(),
        "aggregation": "mean of per-window countermeasure logits (speech-bearing windows)",
        "preprocessing": "raw mono float32 @ 16 kHz, no normalisation, fixed windows",
        "score_note": (
            "Authenticity score is a model-derived countermeasure score — not a "
            "calibrated probability and not a guarantee of authenticity."
        ),
    }


def derive_verdict(
    anti: dict,
    quality: dict,
    threshold: float = DEFAULT_BONA_THRESHOLD,
    band: float = DEFAULT_DECISION_BAND,
    threshold_source: str = "default (uncalibrated)",
) -> dict:
    anti = dict(anti)
    score01 = float(anti.get("authenticity_score", anti.get("bona_fide_probability", 0.0))) / 100.0
    worst = float(anti.get("worst_window_bona_fide", score01 * 100)) / 100.0
    spread = float(anti.get("confidence_spread", 0.0)) / 100.0
    quality_issues = list((quality or {}).get("issues", []))

    if not anti.get("engine_stable", True):
        label, css = "INCONCLUSIVE", "watch"
        verdict = "INCONCLUSIVE / ENGINE INSTABILITY"
    elif quality_issues:
        label, css = "INCONCLUSIVE_QUALITY", "watch"
        verdict = "INCONCLUSIVE / AUDIO QUALITY"
    elif spread >= 0.20:
        label, css = "INCONCLUSIVE", "watch"
        verdict = "INCONCLUSIVE / LOW CONFIDENCE"
    elif score01 <= threshold - band:
        label, css = "LIKELY_SPOOF", "critical"
        verdict = "LIKELY SPOOF"
    elif score01 >= threshold + band and worst >= threshold - band:
        label, css = "LIKELY_AUTHENTIC", "safe"
        verdict = "LIKELY AUTHENTIC"
    else:
        label, css = "INCONCLUSIVE", "watch"
        verdict = "INCONCLUSIVE"

    anti["voice_label"] = label
    anti["verdict"] = verdict
    anti["verdict_class"] = css
    anti["threshold_used"] = round(float(threshold), 4)
    anti["decision_band"] = round(float(band), 4)
    anti["threshold_source"] = threshold_source
    anti["authenticity_score"] = int(round(score01 * 100))
    anti["display_note"] = (
        "Model-derived countermeasure score — not a calibrated probability."
    )
    return anti


def analyze_audio_bytes(
    raw: bytes,
    filename: str,
    model_key: str = "aasist",
    threshold: float = DEFAULT_BONA_THRESHOLD,
    band: float = DEFAULT_DECISION_BAND,
    threshold_source: str = "default (uncalibrated)",
    allow_download: bool = True,
    transcribe: bool = False,
    asr_model: str | None = None,
    asr_language: str | None = None,
    asr_beam_size: int | None = None,
    asr_prompt: str | None = None,
    on_progress=None,
) -> dict:
    def note(message: str):
        if on_progress:
            on_progress(message)

    note("Decoding audio...")
    result = decode_audio_bytes(raw, filename)
    samples = result.pop("samples", None)
    if result.get("limitations") and samples is None:
        result["anti_spoof"] = None
        result["voice_error"] = result.get("user_error") or "; ".join(result["limitations"])
        if transcribe:
            from models.asr import transcribe_pcm
            result["asr"] = transcribe_pcm(
                None, 16000, duration=result.get("duration"),
                model_name=asr_model, language=asr_language,
                beam_size=asr_beam_size or 5, initial_prompt=asr_prompt,
            )
        return result
    if samples is None:
        result["voice_error"] = result.get("user_error") or (
            "Audio quality insufficient for reliable authenticity analysis."
        )
        if transcribe:
            from models.asr import transcribe_pcm
            result["asr"] = transcribe_pcm(
                None, int(result.get("sample_rate") or 16000), duration=result.get("duration"),
                model_name=asr_model, language=asr_language,
                beam_size=asr_beam_size or 5, initial_prompt=asr_prompt,
            )
        return result
    try:
        note("Running voice authenticity analysis...")
        anti = run_antispoof_scores(
            samples, int(result["sample_rate"]), model_key, allow_download=allow_download,
        )
        result["anti_spoof"] = derive_verdict(
            anti, result.get("quality_gate") or {}, threshold, band, threshold_source,
        )
        result["analysis_mode"] += " + deterministic countermeasure inference"
    except Exception as exc:
        result["limitations"].append(
            "Anti-spoof model unavailable. Interaction analysis can still run, "
            f"but voice authenticity cannot be established. ({type(exc).__name__})"
        )
        result["anti_spoof"] = None
        result["voice_error"] = result["limitations"][-1]
    if transcribe:
        note("Transcribing conversation...")
        from models.asr import transcribe_pcm
        result["asr"] = transcribe_pcm(
            samples,
            int(result.get("sample_rate") or 16000),
            duration=result.get("duration"),
            model_name=asr_model,
            language=asr_language,
            beam_size=asr_beam_size or 5,
            initial_prompt=asr_prompt,
        )
        if result["asr"].get("status") == "success":
            result["analysis_mode"] += " + local ASR"
    return result
