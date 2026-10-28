"""TRUSTVOICE AI — Security Console (Streamlit entrypoint)."""

import streamlit as st

from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.analyze import render_analyze
from ui.evaluation import render_evaluation
from ui.incidents import render_incidents
from ui.live_monitor import render_live_monitor
from ui.overview import render_overview
from ui.settings import render_settings
from ui.speakers import render_speakers
from ui.theme import css
from utils.state import new_conversation_state

st.set_page_config(
    page_title="TRUSTVOICE AI",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
)

NEUTRAL_FACTORS = {
    "Voice Authenticity": 76,
    "Speaker Identity": 76,
    "Intent Safety": 96,
    "Behaviour Safety": 94,
    "Context Safety": 93,
}

# Navigation: (group_label, [(store_name, button_key, display_label, icon)])
NAV_GROUPS = (
    (
        "SECURITY OPERATIONS",
        (
            ("Overview", "nav_Overview", "Overview", ":material/grid_view:"),
            ("Analyze Audio", "nav_Analyze", "Analyze Audio", ":material/graphic_eq:"),
            ("Live Monitor", "nav_Live", "Live Monitor", ":material/sensors:"),
            ("Trusted Speakers", "nav_Speakers", "Trusted Speakers", ":material/person:"),
            ("Incidents", "nav_Incidents", "Incidents", ":material/receipt_long:"),
        ),
    ),
    (
        "SYSTEM",
        (
            ("Settings", "nav_Settings", "Settings", ":material/settings:"),
        ),
    ),
)

# Hidden pages (accessible via nav but not in primary sidebar)
HIDDEN_PAGES = {"Evaluation Lab"}


def init_state():
    defaults = {
        "score": None,
        "scenario": "Awaiting analysis",
        "history": [],
        "analysis_done": False,
        "last_analysis": None,
        "last_result": None,
        "transcript": "",
        "factors": dict(NEUTRAL_FACTORS),
        "action_status": "CONTINUE",
        "handshake_result": None,
        "incident_report": None,
        "incident_report_pdf": None,
        "incident_report_filename": "trustvoice_incident_report.pdf",
        "intent_prediction": None,
        "risk_explanation": [],
        "bona_threshold": DEFAULT_BONA_THRESHOLD,
        "decision_band": DEFAULT_DECISION_BAND,
        "threshold_source": "prototype default",
        "model_choice": "aasist",
        "ui_nav": "Overview",
        "accuracy_eval": None,
        "analysis_source": "Idle",
        "conversation_state": new_conversation_state(),
        "demo_view": None,
        "edge_case_view": None,
        "transcript_source": "NONE",
        "live_warning": None,
        "asr_filled_transcript": "",
        # speech recognition settings
        "asr_model_choice": "base",
        "asr_language": "en",
        "asr_quality_mode": "accurate",
        "asr_domain_prompt": True,
        # speakers
        "speakers_view": "gallery",
        "speakers_selected_id": None,
        "speakers_confirm_delete": None,
        # incidents
        "incidents_selected": None,
        # handshake
        "handshake_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Migrate legacy nav values
    legacy = {
        "Console": "Overview",
        "Reports": "Incidents",
        "Demo Scenarios": "Analyze Audio",
        "Demo scenarios": "Analyze Audio",
    }
    if st.session_state.ui_nav in legacy:
        st.session_state.ui_nav = legacy[st.session_state.ui_nav]


def _render_html(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


# ── Init ────────────────────────────────────────────────────────────────────
init_state()
_render_html(css())

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand logo using Base64 SVG (requires xmlns to render in an img tag)
    import base64
    raw_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="2.2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>'
    b64_svg = base64.b64encode(raw_svg.encode('utf-8')).decode('utf-8')
    svg_data = f"data:image/svg+xml;base64,{b64_svg}"
    
    st.markdown(f"""
    <div class="tv-brand">
      <div class="tv-mark">
        <img src="{svg_data}" alt="Logo" width="20" height="20" style="display:block">
      </div>
      <div>
        <div class="tv-brand-name">TRUSTVOICE</div>
        <div class="tv-brand-sub">AI Security</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    current = st.session_state.ui_nav
    for group_label, items in NAV_GROUPS:
        _render_html(f'<div class="tv-nav-section">{group_label}</div>')
        for store, key, label, icon in items:
            active = current == store
            if st.button(
                label,
                key=key,
                icon=icon,
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.ui_nav = store
                st.rerun()

    # Theme toggle
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
        
    theme_icon = "🌙" if st.session_state.theme == "light" else "☀️"
    theme_label = "Dark Mode" if st.session_state.theme == "light" else "Light Mode"
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button(f"{theme_icon} {theme_label}", use_container_width=True, key="theme_toggle"):
        new_theme = "dark" if st.session_state.theme == "light" else "light"
        st.session_state.theme = new_theme
        
        # Rewrite Streamlit config to apply the native theme
        import os
        config_path = ".streamlit/config.toml"
        os.makedirs(".streamlit", exist_ok=True)
        with open(config_path, "w") as f:
            if new_theme == "dark":
                f.write('[theme]\nbase="dark"\nprimaryColor="#2563D6"\n')
            else:
                f.write('[theme]\nbase="light"\nprimaryColor="#2563D6"\nbackgroundColor="var(--tv-bg)"\nsecondaryBackgroundColor="#F1F5F9"\ntextColor="var(--tv-text)"\n')
                
        st.rerun()

    # Bottom status card
    _render_html("""
    <div style="flex:1"></div>
    <div class="tv-side-foot">
      <div class="tv-side-foot-title">
        <span class="tv-online-dot"></span>Prototype system
      </div>
      <div class="tv-side-foot-sub">Analysis services ready</div>
    </div>
    """)

# ── Page routing ────────────────────────────────────────────────────────────
nav = st.session_state.ui_nav

if nav == "Overview":
    render_overview()
elif nav == "Analyze Audio":
    render_analyze()
elif nav == "Live Monitor":
    render_live_monitor()
elif nav == "Trusted Speakers":
    render_speakers()
elif nav == "Incidents":
    render_incidents()
elif nav == "Settings":
    render_settings()
elif nav in {"Evaluation Lab", "Evaluation"}:
    render_evaluation()
else:
    # Fallback — redirect to Overview
    st.session_state.ui_nav = "Overview"
    st.rerun()
