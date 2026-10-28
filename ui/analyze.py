"""Analyze Audio — upload and run the existing TRUSTVOICE analysis pipeline."""

from __future__ import annotations

from html import escape

import streamlit as st

from models.antispoof import analyze_audio_bytes
from models.asr import asr_dependency_status, asr_model_name, get_whisper_model, resolve_live_transcript
from risk.pipeline import analyse_interaction
from ui.theme import COLORS
from utils.audio import DECODE_FORMAT_HELP
from utils.state import new_conversation_state


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def _cached_asr_model(name: str):
    return get_whisper_model(name)


def _apply_result(result: dict, source: str, audio=None):
    st.session_state.last_result = result
    st.session_state.score = result["trust_score"]
    st.session_state.factors = result["factor_display"]
    st.session_state.transcript = result["transcript"]
    st.session_state.intent_prediction = result["intent"]
    st.session_state.risk_explanation = result["drivers"]
    st.session_state.action_status = result["action"]
    st.session_state.scenario = source
    st.session_state.analysis_source = source
    st.session_state.conversation_state = result["conversation_state"]
    st.session_state.analysis_done = True
    if audio is not None:
        st.session_state.last_analysis = audio
    st.session_state.history.append({
        "time": result.get("transcript", "")[:48],
        "scenario": source,
        "score": result["trust_score"],
        "risk": result["interaction_risk"],
        "details": result["action"],
    })


def _pipeline_sidebar_html(audio: dict | None, result: dict | None) -> str:
    """Render the 6-stage analysis pipeline progress panel."""
    anti = (audio or {}).get("anti_spoof")
    asr_info = (audio or {}).get("asr") or {}
    decoded = bool((audio or {}).get("duration") is not None)
    fused = bool(result)

    def _stage_cls(done: bool, failed: bool = False) -> str:
        if done:
            return "done"
        if failed:
            return ""
        return ""

    stages = [
        ("1", "Audio", decoded, bool((audio or {}).get("user_error"))),
        ("2", "Voice authenticity", bool(anti), not decoded),
        ("3", "Speaker identity", fused, False),
        ("4", "Conversation", fused, False),
        ("5", "Risk fusion", fused, False),
        ("6", "Trust handshake", fused and result.get("handshake_required"), False),
    ]
    items = ""
    for num, label, done, _ in stages:
        num_cls = "done" if done else ("active" if decoded and not fused else "")
        items += f"""
        <div class="tv-pipeline-item">
          <div class="tv-pipeline-num {num_cls}">{num}</div>
          <div class="tv-pipeline-label">{escape(label)}</div>
          <div class="tv-pipeline-arrow">↓</div>
        </div>"""
    return items


def render_analyze():
    # ── Header ──────────────────────────────────────────────────────────────
    render("""
    <div class="tv-page">
      <div>
        <h1>ANALYZE AUDIO</h1>
        <p>Evaluate voice authenticity, identity evidence and interaction risk.</p>
      </div>
    </div>
    """)

    dep = asr_dependency_status()
    if not dep.get("ok"):
        st.warning(dep.get("error") or "ASR is unavailable — transcription will be skipped.")

    # Pre-apply any staged ASR transcript BEFORE widgets are instantiated.
    # Writing to a widget's session_state key AFTER the widget renders causes
    # StreamlitWidgetAlreadyInstantiatedError — so we stage via a separate key.
    if "_asr_transcript_pending" in st.session_state:
        st.session_state["analyze_transcript"] = st.session_state.pop("_asr_transcript_pending")

    audio = st.session_state.get("last_analysis") or {}
    result = st.session_state.get("last_result")

    # ── Layout ──────────────────────────────────────────────────────────────
    col_main, col_pipeline = st.columns([2, 1], gap="medium")

    with col_pipeline:
        pipeline_html = _pipeline_sidebar_html(audio, result)
        render(f"""
        <div class="tv-card">
          <div class="tv-card-title">Analysis pipeline</div>
          {pipeline_html}
          <div style="margin-top:12px;padding:10px;background:var(--tv-surface);border-radius:6px;
            border:1px solid var(--tv-border);font-size:12px;color:var(--tv-muted);line-height:1.55">
            Uploaded audio is handled by the existing analysis pipeline.
            This interface does not alter audio preprocessing or model execution.
          </div>
        </div>
        """)

        if result:
            if st.button("→ View in Overview", use_container_width=True, key="az_goto_ov"):
                st.session_state.ui_nav = "Overview"
                st.rerun()

    with col_main:
        # ── Upload zone ──────────────────────────────────────────────────────
        render("""<div class="tv-card">""")
        render("""<div class="tv-card-title">Upload audio file</div>""")

        uploaded = st.file_uploader(
            "Drop audio file here",
            type=["wav", "mp3", "mpeg", "mpga", "m4a", "aac", "ogg", "opus",
                  "oga", "flac", "mp4", "webm", "mov", "3gp", "amr"],
            key="analyze_upload",
            label_visibility="collapsed",
        )
        mic = st.audio_input("Or record from microphone", key="analyze_mic")

        render(f"""<div class="tv-dim" style="margin:4px 0 10px">
          WAV · MP3 · M4A · FLAC · OGG · AAC · WebM — prototype analysis input
        </div>""")

        if uploaded is not None:
            st.audio(uploaded)
        elif mic is not None:
            st.audio(mic)

        # File metadata strip
        fname = uploaded.name if uploaded else ("live_microphone.wav" if mic else "Not selected")
        raw_bytes = uploaded.getvalue() if uploaded else (mic.getvalue() if mic else None)
        dur = audio.get("duration")
        fmt = audio.get("format")
        dur_str = f"{dur} s" if dur is not None else "Not available"
        fmt_str = str(fmt).upper() if fmt else "Not available"

        render(f"""
        <div style="display:flex;gap:24px;margin:14px 0 4px">
          <div>
            <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Filename</div>
            <div style="font-size:14px;font-weight:600;color:var(--tv-text)">{escape(fname)}</div>
          </div>
          <div>
            <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Duration</div>
            <div style="font-size:14px;font-weight:600;color:var(--tv-text)">{escape(dur_str)}</div>
          </div>
          <div>
            <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Format</div>
            <div style="font-size:14px;font-weight:600;color:var(--tv-text)">{escape(fmt_str)}</div>
          </div>
        </div>
        """)
        render("""</div>""")  # close tv-card

        # ── Transcript & identity ────────────────────────────────────────────
        render("""<div class="tv-card">""")
        render("""<div class="tv-card-title">Transcript & speaker identity</div>""")

        # ASR status and intelligence badge if audio has been transcribed
        last_asr = audio.get("asr") or {}
        if last_asr.get("status") == "success" and last_asr.get("transcript"):
            model_disp = escape(str(last_asr.get("model") or "base"))
            lang_disp = escape(str(last_asr.get("language") or "en")).upper()
            prob = last_asr.get("language_probability")
            prob_disp = f" ({int(prob * 100)}%)" if prob else ""
            beam_disp = escape(str(last_asr.get("beam_size") or 5))
            sec_disp = f"{last_asr.get('elapsed_sec')}s" if last_asr.get("elapsed_sec") is not None else ""
            meta_str = f"Model: <b>{model_disp}</b> · Lang: <b>{lang_disp}{prob_disp}</b> · Beam: <b>{beam_disp}</b>"
            if sec_disp:
                meta_str += f" · Latency: <b>{sec_disp}</b>"
            render(f"""
            <div style="margin-bottom:8px;padding:6px 10px;background:var(--tv-surface);border-radius:6px;
                 border:1px solid var(--tv-border);font-size:12px;color:var(--tv-text);display:flex;align-items:center;gap:6px">
              <span style="color:var(--tv-blue);font-weight:600">🎙️ ASR</span>
              <span>{meta_str}</span>
            </div>
            """)

        transcript = st.text_area(
            "Transcript",
            height=88,
            key="analyze_transcript",
            placeholder="Type a transcript, or run analysis to auto-fill from ASR…",
            label_visibility="collapsed",
        )
        from demo.scenarios import IDENTITY_HELP
        identity = st.selectbox(
            "Speaker identity",
            ["NOT_AVAILABLE", "UNVERIFIED", "VERIFIED", "MISMATCH"],
            help=IDENTITY_HELP.get("NOT_AVAILABLE", ""),
            key="analyze_identity",
            label_visibility="visible",
        )

        c1, c2 = st.columns(2)
        with c1:
            run = st.button("⊕ Analyze audio", use_container_width=True,
                            type="primary", key="analyze_run",
                            disabled=(raw_bytes is None and not transcript.strip()))
        with c2:
            clear = st.button("Clear analysis", use_container_width=True, key="analyze_clear")

        if st.session_state.get("live_warning"):
            st.warning(st.session_state.live_warning)

        render("""</div>""")

        # ── Results after analysis ───────────────────────────────────────────
        if audio and result:
            anti = audio.get("anti_spoof") or {}
            quality = audio.get("quality_gate") or {}
            trust = int(result.get("trust_score", 0))
            imp_risk = max(0, min(100, 100 - trust))
            risk_label = result.get("interaction_risk", "—")

            render(f"""
            <div class="tv-card">
              <div class="tv-card-title">Analysis result</div>
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:14px">
                <span class="tv-risk-num" style="font-size:36px">{imp_risk}</span>
                <span class="tv-risk-denom" style="font-size:18px">/ 100</span>
                <span class="tv-badge {'tv-badge-crit' if imp_risk >= 80 else ('tv-badge-warn' if imp_risk >= 55 else 'tv-badge-blue')}"
                  style="margin-left:8px">{escape(str(risk_label).replace('_', ' ').title())}</span>
              </div>
              <div class="tv-evidence-row"><span class="tv-evidence-label">Voice authenticity</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(str(result.get('voice_display') or result.get('voice_label') or '—'))}</span></div>
              <div class="tv-evidence-row"><span class="tv-evidence-label">Speaker identity</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(str(result.get('identity_status', '—')).replace('_', ' '))}</span></div>
              <div class="tv-evidence-row"><span class="tv-evidence-label">Intent</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(str((result.get('intent') or {{}}).get('intent', '—')).replace('_', ' ').title())}</span></div>
              <div class="tv-evidence-row" style="border-bottom:0"><span class="tv-evidence-label">Decision</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(str(result.get('action', '—')).replace('_', ' ').title())}</span></div>
            </div>
            """)

            if anti:
                with st.expander("Audio diagnostics"):
                    st.write({
                        "model": anti.get("model"),
                        "authenticity_score": anti.get("authenticity_score"),
                        "verdict": anti.get("verdict"),
                        "cm_score": anti.get("cm_score"),
                        "windows": anti.get("windows_used"),
                        "audio_quality": quality,
                        "decode_path": audio.get("decode_path"),
                    })
                    st.caption(anti.get("score_note", ""))

        # ── Clear ────────────────────────────────────────────────────────────
        if clear:
            st.session_state.last_result = None
            st.session_state.last_analysis = None
            st.session_state.transcript = ""
            st.session_state.analysis_source = "Idle"
            st.session_state.live_warning = None
            st.session_state.asr_filled_transcript = ""
            st.rerun()

        # ── Run ──────────────────────────────────────────────────────────────
        if run:
            st.session_state.live_warning = None
            fname_run = "typed_transcript.txt"
            if uploaded is not None:
                raw_bytes, fname_run = uploaded.getvalue(), uploaded.name
            elif mic is not None:
                raw_bytes, fname_run = mic.getvalue(), "live_microphone.wav"
            else:
                raw_bytes = None

            audio_result = None
            voice_label = "UNAVAILABLE"
            auth_score = None
            asr_result = None

            if raw_bytes:
                try:
                    status_box = st.status("Analyzing audio…", expanded=True)

                    def _prog(msg: str):
                        status_box.write(msg)

                    asr_model = st.session_state.get("asr_model_choice", asr_model_name())
                    asr_lang = st.session_state.get("asr_language", "en")
                    asr_beam = 5 if st.session_state.get("asr_quality_mode", "accurate") == "accurate" else 1
                    asr_prompt_on = st.session_state.get("asr_domain_prompt", True)
                    from models.asr import DEFAULT_ASR_PROMPT
                    asr_prompt_str = DEFAULT_ASR_PROMPT if asr_prompt_on else None

                    try:
                        _prog(f"Loading speech recognition model ({asr_model})…")
                        _cached_asr_model(asr_model)
                    except Exception:
                        _prog("ASR unavailable — transcription skipped.")

                    audio_result = analyze_audio_bytes(
                        raw_bytes, fname_run,
                        model_key=st.session_state.model_choice,
                        threshold=float(st.session_state.bona_threshold),
                        band=float(st.session_state.decision_band),
                        threshold_source=st.session_state.threshold_source,
                        allow_download=True,
                        transcribe=True,
                        asr_model=asr_model,
                        asr_language=asr_lang,
                        asr_beam_size=asr_beam,
                        asr_prompt=asr_prompt_str,
                        on_progress=_prog,
                    )
                    if audio_result.get("user_error"):
                        st.session_state.live_warning = audio_result["user_error"]
                    status_box.update(label="Audio processing complete", state="complete")
                except Exception as exc:
                    audio_result = {
                        "anti_spoof": None,
                        "asr": {"status": "error", "transcript": "", "error": str(exc)},
                        "user_error": "Audio analysis failed.",
                        "limitations": [str(exc)],
                    }
                    st.session_state.live_warning = audio_result["user_error"]

                st.session_state.last_analysis = audio_result
                asr_result = (audio_result or {}).get("asr")
                if (audio_result or {}).get("limitations") and not (audio_result or {}).get("user_error"):
                    st.warning(" | ".join(audio_result["limitations"]))
                anti_now = (audio_result or {}).get("anti_spoof")
                if anti_now:
                    voice_label = anti_now.get("voice_label", "INCONCLUSIVE")
                    auth_score = anti_now.get("authenticity_score")
                q = (audio_result or {}).get("quality_gate") or {}
                if q.get("quality") == "REVIEW":
                    st.warning("Audio quality issues: " + "; ".join(q.get("issues") or []))
            elif not transcript.strip():
                st.warning("Provide audio and/or a transcript.")
            else:
                st.session_state.last_analysis = None

            if raw_bytes or transcript.strip():
                filled = (st.session_state.get("asr_filled_transcript") or "").strip()
                typed = transcript.strip()
                if raw_bytes:
                    manual = typed if typed and typed != filled else ""
                else:
                    manual = typed
                choice = resolve_live_transcript(manual, asr_result)
                st.session_state.transcript_source = choice["source"]
                st.session_state.live_warning = choice["warning"]
                if choice["source"] == "ASR" and choice["text"]:
                    # Stage the ASR text — applied to the widget key at the
                    # TOP of render_analyze() on the next run, before the
                    # text_area widget is created (avoids StreamlitWidgetAlreadyInstantiatedError)
                    st.session_state["_asr_transcript_pending"] = choice["text"]
                    st.session_state.asr_filled_transcript = choice["text"]
                if choice["analyze"]:
                    with st.spinner("Fusing risk signals…"):
                        analysed = analyse_interaction(
                            transcript=choice["text"],
                            voice_label=voice_label,
                            identity_status=identity,
                            authenticity_score=auth_score,
                            conversation_state=st.session_state.conversation_state,
                            source="LIVE / UPLOADED ANALYSIS",
                            voice_evidence="model" if auth_score is not None else "unavailable",
                        )
                    _apply_result(analysed, "LIVE / UPLOADED ANALYSIS", audio_result)
                elif raw_bytes:
                    st.session_state.analysis_source = "LIVE / UPLOADED ANALYSIS"
                st.rerun()

    render("""<div class="tv-footer">TRUSTVOICE AI · local processing · audio not stored after analysis</div>""")
