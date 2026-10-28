"""Main conversation security console."""

from html import escape

import streamlit as st

from demo.scenarios import BENIGN_EXAMPLES, IDENTITY_HELP, SCENARIO_A, SCENARIO_B, SCENARIO_C
from models.antispoof import analyze_audio_bytes
from models.asr import asr_dependency_status, asr_model_name, get_whisper_model, resolve_live_transcript
from risk.pipeline import analyse_interaction
from ui.components import (
    analysis_mode,
    audio_analysis_card,
    conversation_intel,
    conversation_timeline,
    decision_block,
    handshake_block,
    idle_decision,
    page_header,
    pipeline_block,
    recommended_action_card,
    render,
    risk_breakdown,
    scenario_choice,
    score_trail,
    signal_rows,
    waveform,
)
from utils.audio import DECODE_FORMAT_HELP
from utils.state import new_conversation_state


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


def consume_pending_transcript(state):
    if "pending_console_transcript" in state:
        state["console_transcript"] = state["pending_console_transcript"]
        del state["pending_console_transcript"]


def _apply_pending_console_transcript():
    consume_pending_transcript(st.session_state)


PAGE_COPY = {
    "Console": ("Console", "Analyze voice conversations for fraud, deepfakes and suspicious intent."),
    "Demo Scenarios": ("Demo Scenarios", "Scripted calls with illustrative voice labels — not live AASIST output."),
    "Evaluation Lab": ("Evaluation Lab", "Score labelled audio files. Metrics appear only after a real labelled run."),
    "Reports": ("Reports", "Export the latest analysis as an incident summary."),
    "Settings": ("Settings", "Prototype analysis controls that already affect this application."),
    "Trusted Speakers": ("Trusted Speakers", "Enroll voice profiles for known speakers. Profiles persist locally across restarts."),
}


def render_topbar(page: str = "Console"):
    source = st.session_state.get("analysis_source") or "Idle"
    mode = analysis_mode(source)
    title, subtitle = PAGE_COPY.get(page, (page, ""))
    render(st, page_header(title, subtitle, mode))


def render_console():
    _apply_pending_console_transcript()
    render_topbar("Console")
    source = st.session_state.get("analysis_source") or "Idle"
    mode = analysis_mode(source)
    if mode == "DEMO":
        render(st, '<div class="tv-banner">Demo scenario — scripted transcript and illustrative voice labels. Not a live AASIST verdict.</div>')
    elif mode == "LIVE":
        render(st, '<div class="tv-banner">Live analysis — anti-spoofing and local ASR run on uploaded or microphone audio when provided. Typed transcripts still override ASR.</div>')
    dep = asr_dependency_status()
    if not dep.get("ok"):
        st.warning(dep.get("error") or "ASR is unavailable on the server because the ASR runtime dependency could not be loaded.")

    result = st.session_state.get("last_result")
    audio = st.session_state.get("last_analysis") or {}
    anti = (audio or {}).get("anti_spoof") or {}
    quality = (audio or {}).get("quality_gate") or {}

    left, center, right = st.columns([1, 1.15, 1], gap="medium")
    with left:
        if result:
            render(st, decision_block(result))
        else:
            render(st, idle_decision())
    with center:
        render(st, audio_analysis_card(audio if audio else None))
    with right:
        render(st, '<div class="tv-card-title">Upload or record</div>')
        uploaded = st.file_uploader(
            "Upload audio",
            type=["wav", "mp3", "mpeg", "mpga", "m4a", "aac", "ogg", "opus", "oga",
                  "flac", "mp4", "webm", "mov", "3gp", "amr"],
            key="console_upload",
        )
        mic = st.audio_input("Record", key="console_mic")
        render(st, f'<div class="tv-upload-hint">{escape(DECODE_FORMAT_HELP)} Video containers are accepted when ffmpeg can extract audio.</div>')
        if uploaded is not None:
            st.audio(uploaded)
        elif mic is not None:
            st.audio(mic)
        transcript = st.text_area(
            "Transcript",
            height=90,
            key="console_transcript",
        )
        asr_meta = (audio or {}).get("asr") or {}
        tsrc = st.session_state.get("transcript_source") or "NONE"
        if tsrc == "ASR":
            st.caption("Source: ASR — ASR-generated transcript. Edit if needed. Not a guarantee of accuracy.")
        elif tsrc == "MANUAL":
            st.caption("Source: MANUAL — typed transcript used for interaction analysis.")
            if asr_meta.get("status") == "success" and asr_meta.get("transcript"):
                st.caption(f"ASR (not used for scoring): {asr_meta.get('transcript')}")
        else:
            st.caption("Type a transcript, or upload audio and run analysis to fill this from local ASR.")
        identity = st.selectbox(
            "Speaker identity (prototype — not an enrolled user directory)",
            ["NOT_AVAILABLE", "UNVERIFIED", "VERIFIED", "MISMATCH"],
            help=IDENTITY_HELP["NOT_AVAILABLE"],
            key="console_identity",
        )
        st.caption(IDENTITY_HELP.get(identity, ""))
        if st.session_state.get("live_warning"):
            st.warning(st.session_state.live_warning)
        act1, act2 = st.columns(2)
        with act1:
            run = st.button("Run live analysis", use_container_width=True, key="console_run")
        with act2:
            clear = st.button("Clear analysis", use_container_width=True, key="console_clear")
        if clear:
            _reset_demo_session()
            st.session_state.pending_console_transcript = ""
            st.rerun()

        if run:
            st.session_state.live_warning = None
            raw = None
            fname = "typed_transcript.txt"
            if uploaded is not None:
                raw, fname = uploaded.getvalue(), uploaded.name
            elif mic is not None:
                raw, fname = mic.getvalue(), "live_microphone.wav"

            audio_result = None
            voice_label = "UNAVAILABLE"
            auth_score = None
            asr_result = None
            if raw:
                try:
                    status_box = st.status("Analyzing uploaded audio", expanded=True)

                    def _progress(message: str):
                        status_box.write(message)

                    asr_model = st.session_state.get("asr_model_choice", asr_model_name())
                    asr_lang = st.session_state.get("asr_language", "en")
                    asr_beam = 5 if st.session_state.get("asr_quality_mode", "accurate") == "accurate" else 1
                    asr_prompt_on = st.session_state.get("asr_domain_prompt", True)
                    from models.asr import DEFAULT_ASR_PROMPT
                    asr_prompt_str = DEFAULT_ASR_PROMPT if asr_prompt_on else None

                    try:
                        _progress(f"Loading speech-to-text model ({asr_model})...")
                        _cached_asr_model(asr_model)
                    except Exception:
                        _progress(
                            "ASR is unavailable on the server because the ASR runtime "
                            "dependency could not be loaded."
                        )
                    audio_result = analyze_audio_bytes(
                        raw, fname,
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
                        on_progress=_progress,
                    )
                    if audio_result.get("user_error"):
                        st.session_state.live_warning = audio_result["user_error"]
                    status_box.update(label="Audio processing finished", state="complete")
                except Exception as exc:
                    audio_result = {
                        "anti_spoof": None,
                        "asr": {
                            "status": "error",
                            "transcript": "",
                            "error": f"{type(exc).__name__}: {exc}",
                            "model": asr_model_name(),
                        },
                        "user_error": "Audio analysis failed on the server.",
                        "limitations": [f"{type(exc).__name__}: {exc}"],
                    }
                    st.session_state.live_warning = audio_result["user_error"]
                st.session_state.last_analysis = audio_result
                asr_result = (audio_result or {}).get("asr")
                if audio_result.get("limitations") and not audio_result.get("user_error"):
                    st.warning(" | ".join(audio_result["limitations"]))
                anti_now = audio_result.get("anti_spoof")
                if anti_now:
                    voice_label = anti_now.get("voice_label", "INCONCLUSIVE")
                    auth_score = anti_now.get("authenticity_score")
                elif raw:
                    st.info(
                        "Anti-spoof model unavailable. Interaction analysis can still run, "
                        "but voice authenticity cannot be established."
                    )
                q = audio_result.get("quality_gate") or {}
                if q.get("quality") == "REVIEW":
                    st.warning(
                        "Audio quality insufficient for reliable authenticity analysis. "
                        + "; ".join(q.get("issues") or [])
                    )
            elif not transcript.strip():
                st.warning("Provide audio and/or a transcript. Nothing was analysed.")
            else:
                st.session_state.last_analysis = None

            if raw or transcript.strip():
                filled = (st.session_state.get("asr_filled_transcript") or "").strip()
                typed = transcript.strip()
                if raw:
                    manual = typed if typed and typed != filled else ""
                else:
                    manual = typed
                choice = resolve_live_transcript(manual, asr_result)
                st.session_state.transcript_source = choice["source"]
                st.session_state.live_warning = choice["warning"]
                if choice["source"] == "ASR" and choice["text"]:
                    st.session_state.pending_console_transcript = choice["text"]
                    st.session_state.asr_filled_transcript = choice["text"]
                if choice["analyze"]:
                    with st.spinner("Analyzing intent, behaviour, context, and fusing risk..."):
                        analysed = analyse_interaction(
                            transcript=choice["text"],
                            voice_label=voice_label,
                            identity_status=identity,
                            authenticity_score=auth_score,
                            conversation_state=st.session_state.conversation_state,
                            source="LIVE / MANUAL ANALYSIS",
                            voice_evidence="model" if auth_score is not None else "unavailable",
                        )
                    with st.spinner("Calculating trust score..."):
                        _apply_result(analysed, "LIVE / UPLOADED ANALYSIS", audio_result)
                elif raw:
                    st.session_state.analysis_source = "LIVE / UPLOADED ANALYSIS"
                st.rerun()

    render(st, '<div class="tv-section">Five signal analysis</div>')
    if result:
        render(st, signal_rows(result.get("factor_display"), result.get("identity_status"), result))
        id_status = result.get("identity_status") or "NOT_AVAILABLE"
        st.caption(
            f"Speaker identity status: {str(id_status).replace('_', ' ')}. "
            + IDENTITY_HELP.get(id_status, "")
        )
    else:
        render(st, signal_rows(None, result=None))

    transcript_show = (result or {}).get("transcript") or st.session_state.transcript
    intel, risk = st.columns([1.35, 1], gap="medium")
    with intel:
        render(st, conversation_intel(
            transcript_show,
            st.session_state.get("transcript_source") or "NONE",
            (audio or {}).get("asr"),
            result,
        ))
    with risk:
        render(st, risk_breakdown(result))

    pipe, action = st.columns([1.35, 1], gap="medium")
    with pipe:
        render(st, pipeline_block(audio if audio else None, result, source))
    with action:
        if result and result.get("handshake_required"):
            render(st, handshake_block(result.get("action_detail", "")))
            st.caption("Prototype / simulated — this does not contact a manager, device, or bank.")
            h1, h2, h3 = st.columns(3)
            with h1:
                if st.button("Confirm", use_container_width=True):
                    st.session_state.handshake_result = {
                        "status": "CONFIRMED",
                        "message": "Simulated confirmation on a trusted channel. Sensitive action may continue.",
                    }
            with h2:
                if st.button("Deny", use_container_width=True):
                    st.session_state.handshake_result = {
                        "status": "DENIED",
                        "message": "Simulated denial. Sensitive action remains blocked.",
                    }
            with h3:
                if st.button("No response", use_container_width=True):
                    st.session_state.handshake_result = {
                        "status": "NO_RESPONSE",
                        "message": "No independent confirmation. Sensitive action remains blocked pending manual verification.",
                    }
            if st.session_state.handshake_result:
                st.caption(
                    f"{st.session_state.handshake_result['status']}: "
                    f"{st.session_state.handshake_result['message']}"
                )
        else:
            render(st, recommended_action_card(result))

    with st.expander("Audio evidence and diagnostics"):
        if audio:
            render(st, waveform(audio.get("envelope")))
            render(st, f"""
            <div class="tv-note">
              Duration {escape(str(audio.get('duration', '—')))} s ·
              Quality {escape(str(quality.get('quality', '—')))}
            </div>
            """)
        if anti:
            render(st, f"""
            <div class="tv-row"><span>Voice authenticity</span><span>{int(anti.get('authenticity_score', 0))} / 100 · {escape(str(anti.get('verdict', 'UNAVAILABLE')))}</span></div>
            """)
            st.caption("Model confidence is an estimate from the selected countermeasure and is not a guarantee of authenticity.")
            st.write({
                "model": anti.get("model"),
                "sample_rate": anti.get("sample_rate_used"),
                "window_count": anti.get("windows_used"),
                "cm_score": anti.get("cm_score"),
                "threshold": anti.get("threshold_used"),
                "decision_band": anti.get("decision_band"),
                "threshold_source": anti.get("threshold_source"),
                "audio_quality": quality,
                "speech_activity": quality.get("speech_activity_ratio"),
                "repeatability": anti.get("engine_stable"),
                "inference_status": anti.get("verdict"),
                "authenticity_score": anti.get("authenticity_score"),
            })
            st.caption(anti.get("score_note", ""))
        else:
            st.caption("No live countermeasure result. Upload audio or use a demo scenario.")
        asr_info = (audio or {}).get("asr") or {}
        if asr_info:
            st.write({
                "asr_model": asr_info.get("model"),
                "transcription_status": asr_info.get("status"),
                "duration": asr_info.get("duration"),
                "detected_language": asr_info.get("language"),
                "processing_time_sec": asr_info.get("elapsed_sec"),
                "truncated": asr_info.get("truncated"),
                "asr_error": asr_info.get("error"),
                "transcript_source": st.session_state.get("transcript_source") or "NONE",
                "decode_path": audio.get("decode_path") if audio else None,
                "ffmpeg": audio.get("ffmpeg") if audio else None,
            })
            st.caption("ASR is local faster-whisper on CPU. It is not a guarantee of transcription accuracy and does not decide whether a voice is synthetic.")
        st.caption(
            "Prototype processing is local to the application environment. "
            "Voice/audio data should be treated as sensitive and retained only as long as necessary. "
            "No compliance certification is claimed."
        )


def render_demo():
    render_topbar("Demo Scenarios")
    st.caption(
        "Each scenario uses a fixed script. Demo voice labels are illustrative and are not live AASIST results. "
        "Reset clears this page and the shared analysis session."
    )

    a, b, c, d = st.columns([1, 1, 1, 0.7], gap="medium")
    selected = (st.session_state.get("demo_view") or {}).get("id")
    with a:
        render(st, scenario_choice("A", "Unknown caller", "Bank pretext / OTP", selected == "A"))
        run_a = st.button("Run A", key="demo_run_a", use_container_width=True)
    with b:
        render(st, scenario_choice("B", "Verified identity", "Dangerous request", selected == "B"))
        run_b = st.button("Run B", key="demo_run_b", use_container_width=True)
    with c:
        render(st, scenario_choice("C", "Benign workplace", "Normal conversation", selected == "C"))
        run_c = st.button("Run C", key="demo_run_c", use_container_width=True)
    with d:
        render(st, '<div class="tv-choice"><div class="sub">Clear this demonstration</div></div>')
        reset = st.button("Reset", key="demo_reset", use_container_width=True)

    if reset:
        _reset_demo_session()
        st.rerun()

    if run_a:
        _run_scenario(SCENARIO_A)
    elif run_b:
        _run_scenario(SCENARIO_B)
    elif run_c:
        _run_scenario(SCENARIO_C)

    demo = st.session_state.get("demo_view")
    edge = st.session_state.get("edge_case_view")
    if demo:
        _render_demo_progression(demo)
    elif edge:
        _render_edge_case_result(edge)
    else:
        render(st, '<div class="tv-note">Select a scenario. Only that scripted conversation will appear here. Console uploads are not shown on this page.</div>')

    edge_open = bool(st.session_state.get("edge_case_view"))
    with st.expander("Additional edge-case tests (not part of A / B / C)", expanded=edge_open):
        st.caption(
            "Each click scores that one sentence and shows the result above. "
            "These are not the scripts for Scenarios A–C."
        )
        for i, (kind, text) in enumerate(BENIGN_EXAMPLES):
            if st.button(f"{kind}: {text}", key=f"ex_{i}", use_container_width=True):
                analysed = analyse_interaction(
                    transcript=text,
                    voice_label="UNAVAILABLE" if kind == "SPOOF-NOTE" else "LIKELY_AUTHENTIC",
                    identity_status="UNVERIFIED",
                    source="LIVE / MANUAL ANALYSIS",
                    voice_evidence="illustrative",
                    conversation_state=new_conversation_state(),
                )
                st.session_state.demo_view = None
                st.session_state.edge_case_view = {
                    "kind": kind,
                    "text": text,
                    "result": analysed,
                }
                _apply_result(analysed, "LIVE / MANUAL ANALYSIS")
                st.rerun()


def _reset_demo_session():
    st.session_state.conversation_state = new_conversation_state()
    st.session_state.last_result = None
    st.session_state.last_analysis = None
    st.session_state.transcript = ""
    st.session_state.analysis_source = "Idle"
    st.session_state.handshake_result = None
    st.session_state.history = []
    st.session_state.demo_view = None
    st.session_state.edge_case_view = None
    st.session_state.analysis_done = False
    st.session_state.intent_prediction = None
    st.session_state.risk_explanation = []
    st.session_state.score = None
    st.session_state.scenario = "Awaiting analysis"
    st.session_state.transcript_source = "NONE"
    st.session_state.live_warning = None
    st.session_state.asr_filled_transcript = ""


def _render_edge_case_result(edge: dict):
    result = edge.get("result") or {}
    render(st, f'<div class="tv-section">{escape(str(edge.get("kind", "TEST")))}</div>')
    render(st, conversation_timeline([str(edge.get("text") or "")]))
    render(st, '<div class="tv-note">Single-sentence check, not Scenario A/B/C.</div>')
    if result:
        render(st, decision_block(result))


def _render_demo_progression(demo: dict):
    title = str(demo.get("title", "Demo scenario"))
    turns = demo.get("turns") or []
    render(st, f"""
    <div class="tv-card">
      <div class="tv-card-title">Scenario {escape(str(demo.get("id", "")))}</div>
      <div class="tv-label">{escape(title)}</div>
      <div class="tv-note">{escape(str(demo.get("note") or "Illustrative voice labels — not live AASIST output."))}</div>
    </div>
    """)
    left, right = st.columns([1.35, 1], gap="medium")
    with left:
        render(st, '<div class="tv-card-title">Conversation steps</div>')
        render(st, conversation_timeline([str(t.get("text") or "") for t in turns]))
        rows = "".join(
            f"<tr><td>{i+1:02d}</td><td class='num'>{int(t.get('trust_score') or 0)}</td>"
            f"<td>{escape(str(t.get('risk') or '—'))}</td></tr>"
            for i, t in enumerate(turns)
        )
        render(st, f"""
        <div class="tv-card">
          <div class="tv-card-title">Risk progression</div>
          <table class="tv-table">
            <tr><th>Step</th><th class="num">Trust</th><th>Band</th></tr>
            {rows}
          </table>
        </div>
        """)
        render(st, score_trail([int(t.get("trust_score") or 0) for t in turns]))
    last = st.session_state.get("last_result")
    with right:
        if last:
            render(st, decision_block(last))
            render(st, risk_breakdown(last))
            render(st, pipeline_block(None, last, "DEMO SCENARIO"))
            if last.get("handshake_required"):
                render(st, handshake_block(last.get("action_detail", "")))
                st.caption("Prototype / simulated — this does not contact a manager, device, or bank.")
                d1, d2, d3 = st.columns(3)
                with d1:
                    if st.button("Confirm", key="demo_hs_yes", use_container_width=True):
                        st.session_state.handshake_result = {
                            "status": "CONFIRMED",
                            "message": "Simulated confirmation on a trusted channel. Sensitive action may continue.",
                        }
                with d2:
                    if st.button("Deny", key="demo_hs_no", use_container_width=True):
                        st.session_state.handshake_result = {
                            "status": "DENIED",
                            "message": "Simulated denial. Sensitive action remains blocked.",
                        }
                with d3:
                    if st.button("No response", key="demo_hs_none", use_container_width=True):
                        st.session_state.handshake_result = {
                            "status": "NO_RESPONSE",
                            "message": "No independent confirmation. Sensitive action remains blocked pending manual verification.",
                        }
                if st.session_state.handshake_result:
                    st.caption(
                        f"{st.session_state.handshake_result['status']}: "
                        f"{st.session_state.handshake_result['message']}"
                    )
            else:
                render(st, recommended_action_card(last))


def _run_scenario(spec):
    _reset_demo_session()
    state = new_conversation_state()
    combined = []
    last = None
    turns = []
    for step in spec["steps"]:
        combined.append(step["text"])
        last = analyse_interaction(
            transcript=" ".join(combined),
            voice_label=step["voice"],
            identity_status=step["identity"],
            claimed_identity=step.get("claimed_identity"),
            conversation_state=state,
            source="DEMO SCENARIO",
            voice_evidence="illustrative",
        )
        state = last["conversation_state"]
        turns.append({
            "text": step["text"],
            "trust_score": last["trust_score"],
            "risk": last["interaction_risk"],
            "action": last["action"],
        })
    if last:
        last = dict(last)
        last["transcript"] = " ".join(s["text"] for s in spec["steps"])
        st.session_state.demo_view = {
            "id": spec.get("id"),
            "title": spec.get("title"),
            "note": spec.get("note"),
            "turns": turns,
        }
        _apply_result(last, "DEMO SCENARIO")
        st.session_state.last_analysis = None
        st.session_state.edge_case_view = None
        st.rerun()
