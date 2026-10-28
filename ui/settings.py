"""Settings — system status and prototype analysis preferences."""

from __future__ import annotations

from html import escape

import streamlit as st

from models.antispoof import MODEL_REGISTRY
from models.asr import asr_dependency_status, asr_model_name
from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def render_settings():
    render("""
    <div class="tv-page">
      <div>
        <h1>SETTINGS</h1>
        <p>System status and prototype analysis preferences.</p>
      </div>
    </div>
    """)

    dep = asr_dependency_status()
    asr_ready = dep.get("ok", False)
    asr_status_badge = '<span class="tv-badge tv-badge-ok">● Ready</span>' if asr_ready else \
                       '<span class="tv-badge tv-badge-warn">● Unavailable</span>'

    col_services, col_policy = st.columns([1, 1], gap="medium")

    with col_services:
        render(f"""
        <div class="tv-card">
          <div class="tv-card-title">Analysis services</div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Audio preprocessing</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-ok">● Ready</span>
          </div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Voice authenticity</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-ok">● Ready</span>
          </div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Speech-to-text</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            {asr_status_badge}
          </div>
          <div class="tv-evidence-row" style="border-bottom:0">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Risk fusion</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-warn">● Prototype</span>
          </div>
        </div>
        """)

        if not asr_ready:
            st.info(dep.get("error") or "ASR unavailable — faster-whisper may not be installed.")

        # Model selection
        render("""<div class="tv-card" style="margin-top:0">
          <div class="tv-card-title">Anti-spoofing model</div>
        </div>""")
        model_key = st.selectbox(
            "Model",
            list(MODEL_REGISTRY.keys()),
            index=list(MODEL_REGISTRY.keys()).index(st.session_state.model_choice)
            if st.session_state.model_choice in MODEL_REGISTRY else 0,
            format_func=lambda k: MODEL_REGISTRY[k]["label"],
            key="settings_model",
            label_visibility="collapsed",
        )
        if model_key != st.session_state.model_choice:
            st.session_state.model_choice = model_key
            st.success("Model updated.")

        # Speech recognition settings
        render("""<div class="tv-card" style="margin-top:0">
          <div class="tv-card-title">Speech recognition & transcription</div>
        </div>""")

        asr_model_labels = {
            "base": "base — Recommended (Balanced speed & high accuracy)",
            "small": "small — High Accuracy (Best for accents & noise)",
            "tiny": "tiny — Ultra-fast (Lower accuracy)",
            "base.en": "base.en — English-only (Fast & high accuracy)",
            "small.en": "small.en — English-only (High accuracy)",
            "medium": "medium — Maximum Accuracy (Enterprise)",
        }
        current_asr_model = st.session_state.get("asr_model_choice", asr_model_name())
        if current_asr_model not in asr_model_labels:
            current_asr_model = "base"

        selected_asr_model = st.selectbox(
            "Speech recognition model",
            list(asr_model_labels.keys()),
            index=list(asr_model_labels.keys()).index(current_asr_model),
            format_func=lambda k: asr_model_labels.get(k, k),
            key="settings_asr_model",
            help="Higher accuracy models drastically reduce word errors, misheard numbers, and dropped phrases.",
        )
        if selected_asr_model != st.session_state.get("asr_model_choice"):
            st.session_state.asr_model_choice = selected_asr_model

        col_lang, col_beam = st.columns(2)
        with col_lang:
            lang_options = {
                "en": "English (en)",
                "auto": "Auto-detect",
                "es": "Spanish (es)",
                "fr": "French (fr)",
                "de": "German (de)",
                "hi": "Hindi (hi)",
                "zh": "Chinese (zh)",
            }
            current_lang = st.session_state.get("asr_language", "en")
            if current_lang not in lang_options:
                current_lang = "en"
            selected_lang = st.selectbox(
                "Spoken language",
                list(lang_options.keys()),
                index=list(lang_options.keys()).index(current_lang),
                format_func=lambda k: lang_options.get(k, k),
                key="settings_asr_lang",
                help="Setting an explicit language prevents false foreign-language hallucinations on accented or quiet audio.",
            )
            if selected_lang != st.session_state.get("asr_language"):
                st.session_state.asr_language = selected_lang

        with col_beam:
            mode_options = {
                "accurate": "Beam Search (size=5 · Accurate)",
                "fast": "Greedy (size=1 · Fast)",
            }
            current_mode = st.session_state.get("asr_quality_mode", "accurate")
            if current_mode not in mode_options:
                current_mode = "accurate"
            selected_mode = st.selectbox(
                "Decoding accuracy",
                list(mode_options.keys()),
                index=list(mode_options.keys()).index(current_mode),
                format_func=lambda k: mode_options.get(k, k),
                key="settings_asr_mode",
                help="Beam search explores multiple hypotheses to avoid acoustic transcription mistakes.",
            )
            if selected_mode != st.session_state.get("asr_quality_mode"):
                st.session_state.asr_quality_mode = selected_mode

        boost_prompt = st.checkbox(
            "Boost security & financial terminology",
            value=bool(st.session_state.get("asr_domain_prompt", True)),
            key="settings_asr_prompt",
            help="Primes Whisper's vocabulary with security terms like OTP, wire transfer, SWIFT, credentials, and verification codes.",
        )
        if boost_prompt != st.session_state.get("asr_domain_prompt"):
            st.session_state.asr_domain_prompt = boost_prompt

        render(f"""
        <div class="tv-evidence-row" style="margin-top:8px">
          <span class="tv-evidence-label">Active ASR engine</span>
          <span style="font-size:13px;font-weight:500;color:var(--tv-text)">faster-whisper ({escape(st.session_state.get('asr_model_choice', 'base'))})</span>
        </div>
        <div class="tv-evidence-row" style="border-bottom:0">
          <span class="tv-evidence-label">Service status</span>
          {'<span class="tv-badge tv-badge-ok">● Ready</span>' if asr_ready else '<span class="tv-badge tv-badge-warn">● Unavailable</span>'}
        </div>
        """)

    with col_policy:
        render("""<div class="tv-card">
          <div class="tv-card-title">Decision policy</div>
        </div>""")

        # Threshold
        threshold_display = st.selectbox(
            "Verification threshold",
            ["Use backend policy", "Manual"],
            key="settings_thresh_mode",
        )

        current_thresh = float(st.session_state.bona_threshold)
        if threshold_display == "Manual":
            new_thresh = st.slider(
                "Threshold value",
                min_value=0.0,
                max_value=1.0,
                value=current_thresh,
                step=0.005,
                format="%.3f",
                key="settings_thresh_val",
            )
            if new_thresh != current_thresh:
                st.session_state.bona_threshold = new_thresh
                st.session_state.threshold_source = "manual override"

        render(f"""
        <div class="tv-evidence-row" style="margin-top:6px">
          <span class="tv-evidence-label">Current threshold</span>
          <span style="font-size:13px;font-weight:500;color:var(--tv-text)">{current_thresh:.3f}</span>
        </div>
        <div class="tv-evidence-row">
          <span class="tv-evidence-label">Source</span>
          <span style="font-size:13px;color:var(--tv-text)">{escape(str(st.session_state.threshold_source))}</span>
        </div>
        """)

        # Unavailable evidence handling
        unavail_choice = st.selectbox(
            "Unavailable evidence",
            ["Display as not available", "Treat as inconclusive", "Ignore"],
            key="settings_unavail",
        )

        if st.button("Save preferences", use_container_width=True, type="primary", key="settings_save"):
            st.success("Preferences saved for this session.")

        # Reset thresholds
        render("""<div style="margin-top:14px"></div>""")
        if st.button("Reset to defaults", use_container_width=True, key="settings_reset"):
            st.session_state.bona_threshold = DEFAULT_BONA_THRESHOLD
            st.session_state.decision_band = DEFAULT_DECISION_BAND
            st.session_state.threshold_source = "prototype default"
            st.success("Thresholds reset.")
            st.rerun()

        # Band
        render("""<div class="tv-card" style="margin-top:12px">
          <div class="tv-card-title">Decision band</div>
        </div>""")
        current_band = float(st.session_state.decision_band)
        new_band = st.slider(
            "Decision band (±)",
            0.0, 0.25, current_band, 0.005, format="%.3f",
            key="settings_band",
        )
        if new_band != current_band:
            st.session_state.decision_band = new_band

    # Evaluation lab link
    render("""<div style="margin-top:12px"></div>""")
    render("""<div class="tv-card">
      <div class="tv-card-title">Evaluation lab</div>
      <div class="tv-muted" style="margin-bottom:10px">
        Score labelled audio files against the current model. Upload REAL_… and SPOOF_… prefixed files.
      </div>
    </div>""")
    if st.button("→ Open Evaluation Lab", use_container_width=True, key="settings_eval"):
        st.session_state.ui_nav = "Evaluation Lab"
        st.rerun()

    render("""<div class="tv-footer">TRUSTVOICE AI · SIH prototype · settings affect this session only</div>""")
