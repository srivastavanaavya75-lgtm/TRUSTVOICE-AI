"""Local CPU speech-to-text (faster-whisper). Independent of AASIST."""

from __future__ import annotations

import os
import re
import time

try:
    import numpy as np
except ImportError:
    np = None

DEFAULT_ASR_MODEL = "base"
MAX_ASR_SECONDS = float(os.environ.get("TRUSTVOICE_ASR_MAX_SEC", "120"))
DEFAULT_ASR_PROMPT = (
    "TrustVoice security transcript: CEO fraud, urgent wire transfer, bank account, "
    "routing number, SWIFT code, OTP verification code, multi-factor credentials, "
    "financial transaction, authorization, executive voice impersonation."
)
ASR_UNAVAILABLE_SERVER = (
    "ASR is unavailable on the server because the ASR runtime dependency could not be loaded."
)
ASR_FAILURE_WARNING = (
    "ASR unavailable/failed. Voice authenticity was analyzed, but conversation "
    "content could not be automatically analyzed."
)

_MODELS: dict = {}


def asr_model_name() -> str:
    name = (os.environ.get("TRUSTVOICE_ASR_MODEL") or DEFAULT_ASR_MODEL).strip()
    return name or DEFAULT_ASR_MODEL


def get_whisper_threads() -> int:
    env_threads = os.environ.get("TRUSTVOICE_ASR_THREADS")
    if env_threads:
        try:
            return max(1, int(env_threads))
        except ValueError:
            pass
    cores = os.cpu_count() or 2
    return max(1, min(4, cores))


def asr_dependency_status() -> dict:
    try:
        import faster_whisper  # noqa: F401
        return {"ok": True, "error": None}
    except Exception:
        return {"ok": False, "error": ASR_UNAVAILABLE_SERVER}


def _empty_result(**overrides) -> dict:
    out = {
        "transcript": "",
        "status": "error",
        "model": asr_model_name(),
        "language": None,
        "language_probability": None,
        "beam_size": 5,
        "duration": None,
        "elapsed_sec": None,
        "error": None,
        "truncated": False,
    }
    out.update(overrides)
    return out


def prepare_pcm_for_asr(samples, sample_rate: int = 16000):
    """Normalize dynamic range and remove DC offset to optimize acoustic filterbanks."""
    if samples is None:
        return None
    if np is not None:
        try:
            arr = np.asarray(samples, dtype=np.float32).reshape(-1)
            if arr.size == 0:
                return arr
            # Remove DC offset (center around 0.0)
            arr = arr - float(np.mean(arr))
            # Peak normalize to 0.95 to ensure clear signal without digital clipping
            peak = float(np.max(np.abs(arr)))
            if peak > 1e-4:
                arr = arr * (0.95 / peak)
            return np.ascontiguousarray(arr, dtype=np.float32)
        except Exception:
            return samples
    return samples


def clean_transcript_text(text: str) -> str:
    """Normalize spaces and clean up common Whisper punctuation anomalies."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    # Remove repeated punctuation like ".." or "??"
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"!{2,}", "!", text)
    return text.strip()


def get_whisper_model(model_name: str | None = None):
    """Load once per process. CPU quantized by default."""
    name = model_name or asr_model_name()
    cached = _MODELS.get(name)
    if cached is not None:
        return cached
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(ASR_UNAVAILABLE_SERVER) from exc

    threads = get_whisper_threads()
    preferred = (os.environ.get("TRUSTVOICE_ASR_COMPUTE") or "").strip()
    compute_types = [preferred] if preferred else []
    for item in ("int8", "int8_float32", "default"):
        if item not in compute_types:
            compute_types.append(item)

    last_error = None
    for compute in compute_types:
        if not compute:
            continue
        try:
            model = WhisperModel(
                name,
                device="cpu",
                compute_type=compute,
                cpu_threads=threads,
            )
            _MODELS[name] = model
            return model
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not initialize ASR model '{name}': {last_error}")


def transcribe_pcm(
    samples,
    sample_rate: int = 16000,
    duration: float | None = None,
    model_name: str | None = None,
    language: str | None = "en",
    beam_size: int = 5,
    initial_prompt: str | None = DEFAULT_ASR_PROMPT,
    vad_filter: bool = True,
) -> dict:
    """Transcribe 16 kHz mono float PCM with beam search, dynamic range normalization,
    domain vocabulary priming, and tuned speech boundary detection."""
    model_id = model_name or asr_model_name()
    truncated = False
    dur = duration
    eff_beam = max(1, int(beam_size if beam_size is not None else 5))
    target_lang = None if language in (None, "", "auto") else str(language).strip()

    try:
        dep = asr_dependency_status()
        if not dep["ok"]:
            return _empty_result(
                status="unavailable",
                model=model_id,
                error=ASR_UNAVAILABLE_SERVER,
                duration=dur,
                beam_size=eff_beam,
            )

        if samples is None:
            return _empty_result(
                status="decode_failed",
                model=model_id,
                beam_size=eff_beam,
                error="No decoded audio samples were available for ASR.",
            )

        # Normalize dynamic range and remove DC offset
        samples = prepare_pcm_for_asr(samples, sample_rate)

        n = int(getattr(samples, "size", 0) or len(samples))
        sr = int(sample_rate or 16000)
        actual = (n / float(sr)) if sr else 0.0
        if dur is None:
            dur = round(actual, 3)
        if actual > MAX_ASR_SECONDS and sr:
            samples = samples[: int(MAX_ASR_SECONDS * sr)]
            n = int(getattr(samples, "size", 0) or len(samples))
            truncated = True
            dur = round(n / float(sr), 3)
        if n < int(0.35 * sr):
            return _empty_result(
                status="no_speech",
                model=model_id,
                duration=dur,
                beam_size=eff_beam,
                truncated=truncated,
                error="Clip is too short for reliable transcription.",
            )

        started = time.perf_counter()
        model = get_whisper_model(model_id)

        # Tuned Silero VAD parameters with 400ms padding to prevent front/back clipping
        vad_params = {
            "threshold": 0.45,
            "min_speech_duration_ms": 150,
            "max_speech_duration_s": float("inf"),
            "min_silence_duration_ms": 1200,
            "speech_pad_ms": 400,
        }

        def _run(use_vad: bool, lang: str | None):
            kwargs = {
                "language": lang,
                "beam_size": eff_beam,
                "best_of": max(1, eff_beam),
                "patience": 1.0,
                "temperature": [0.0, 0.2, 0.4],
                "compression_ratio_threshold": 2.4,
                "log_prob_threshold": -1.0,
                "no_speech_threshold": 0.6,
                "condition_on_previous_text": False,
                "vad_filter": use_vad,
            }
            if initial_prompt:
                kwargs["initial_prompt"] = initial_prompt
            if use_vad:
                kwargs["vad_parameters"] = vad_params
            return model.transcribe(samples, **kwargs)

        # Primary pass
        segments, info = _run(vad_filter, target_lang)
        text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments).strip()
        text = clean_transcript_text(text)

        # Fallback 1: If VAD filtered everything or only caught < 5 chars from > 1.5s audio, try without VAD
        if vad_filter and (not text or (len(text) < 5 and dur and dur > 1.5)):
            segments_novad, info_novad = _run(False, target_lang)
            alt_text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments_novad).strip()
            alt_text = clean_transcript_text(alt_text)
            if alt_text:
                text = alt_text
                info = info_novad

        # Fallback 2: If language auto-detect was used but confidence was very low (<0.60) or detected
        # an improbable language, retry with English ("en")
        detected_lang = getattr(info, "language", None) or None
        lang_prob = float(getattr(info, "language_probability", 0.0) or 0.0)
        if target_lang is None and detected_lang and detected_lang != "en" and lang_prob < 0.65:
            segments_en, info_en = _run(False, "en")
            en_text = " ".join((getattr(seg, "text", "") or "").strip() for seg in segments_en).strip()
            en_text = clean_transcript_text(en_text)
            if en_text:
                text = en_text
                info = info_en
                detected_lang = "en"
                lang_prob = float(getattr(info_en, "language_probability", 0.90) or 0.90)

        elapsed = round(time.perf_counter() - started, 3)
        language_out = str(detected_lang).strip() if detected_lang else target_lang

        note = None
        if truncated:
            note = f"Only the first {MAX_ASR_SECONDS:.0f}s were transcribed."
        if not text:
            return _empty_result(
                status="no_speech",
                model=model_id,
                language=language_out,
                language_probability=lang_prob,
                beam_size=eff_beam,
                duration=dur,
                elapsed_sec=elapsed,
                truncated=truncated,
                error="ASR detected no usable speech in audio clip.",
            )

        return {
            "transcript": text,
            "status": "success",
            "model": model_id,
            "language": language_out,
            "language_probability": round(lang_prob, 3) if lang_prob else None,
            "beam_size": eff_beam,
            "duration": dur,
            "elapsed_sec": elapsed,
            "error": note,
            "truncated": truncated,
        }
    except Exception as exc:
        message = str(exc)
        unavailable = ASR_UNAVAILABLE_SERVER.lower() in message.lower() or "faster_whisper" in message.lower()
        return _empty_result(
            status="unavailable" if unavailable else "error",
            model=model_id,
            beam_size=eff_beam,
            duration=dur,
            truncated=truncated,
            error=ASR_UNAVAILABLE_SERVER if unavailable else f"{type(exc).__name__}: {exc}",
        )


def resolve_live_transcript(manual: str, asr: dict | None) -> dict:
    """Choose the text that feeds the existing interaction engine."""
    manual_text = (manual or "").strip()
    asr = asr or {}
    asr_text = (asr.get("transcript") or "").strip()
    asr_ok = asr.get("status") == "success" and bool(asr_text)

    if manual_text:
        return {
            "text": manual_text,
            "source": "MANUAL",
            "analyze": True,
            "asr_text": asr_text or None,
            "warning": None,
        }
    if asr_ok:
        warning = asr.get("error") if asr.get("truncated") else None
        return {
            "text": asr_text,
            "source": "ASR",
            "analyze": True,
            "asr_text": asr_text,
            "warning": warning,
        }

    status = asr.get("status") or "unavailable"
    detail = asr.get("error")
    if status == "unavailable":
        warning = ASR_UNAVAILABLE_SERVER
    elif status == "decode_failed":
        warning = detail or ASR_FAILURE_WARNING
    elif status == "no_speech":
        warning = (
            "Conversation content: unavailable. ASR detected no usable speech. "
            "Voice authenticity may still be available. That is not a benign verdict."
        )
    elif status == "too_long":
        warning = detail or ASR_FAILURE_WARNING
    else:
        warning = ASR_FAILURE_WARNING
        if detail:
            warning = f"{ASR_FAILURE_WARNING} {detail}"

    return {
        "text": "",
        "source": "NONE",
        "analyze": False,
        "asr_text": None,
        "warning": warning,
    }
