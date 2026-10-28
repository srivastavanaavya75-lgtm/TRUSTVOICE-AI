"""Light enterprise theme for TRUSTVOICE AI — clean security console."""

COLORS = {
    "bg": "#F7F9FC",
    "bg2": "#F1F5F9",
    "surface": "#FFFFFF",
    "surface2": "var(--tv-surface)",
    "elevated": "#F1F5F9",
    "border": "#E2E8F0",
    "border2": "#CBD5E1",
    "text": "#182235",
    "muted": "#64748B",
    "dim": "#94A3B8",
    "accent": "#2563D6",
    "accent_light": "#EFF6FF",
    "accent2": "#DBEAFE",
    "green": "#16A34A",
    "green_light": "#DCFCE7",
    "amber": "#D97706",
    "amber_light": "#FEF3C7",
    "red": "#DC2626",
    "red_light": "#FEE2E2",
    "gray": "#64748B",
    "sidebar": "#FFFFFF",
}

STATUS_COLOR = {
    "LOW": "#16A34A",
    "CONTINUE": "#16A34A",
    "LIKELY AUTHENTIC": "#16A34A",
    "GOOD": "#16A34A",
    "COMPLETED": "#16A34A",
    "ONLINE": "#16A34A",
    "VERIFIED": "#16A34A",
    "ELEVATED": "#D97706",
    "WARN": "#D97706",
    "INCONCLUSIVE": "#D97706",
    "ANALYZING": "#2563D6",
    "MEDIUM": "#D97706",
    "HIGH": "#DC2626",
    "CRITICAL": "#DC2626",
    "VERIFY": "#DC2626",
    "CRITICAL INTERVENTION": "#DC2626",
    "LIKELY SPOOF": "#DC2626",
    "FAILED": "#DC2626",
    "UNAVAILABLE": "#64748B",
    "NOT_AVAILABLE": "#64748B",
    "UNVERIFIED": "#64748B",
    "QUEUED": "#64748B",
    "MISMATCH": "#DC2626",
    "SUSPICIOUS": "#DC2626",
}


def status_color(label: str) -> str:
    return STATUS_COLOR.get(str(label).upper(), COLORS["gray"])


COLORS_DARK = {
    "bg": "#0B1120",
    "bg2": "#111827",
    "surface": "#1F2937",
    "surface2": "#374151",
    "elevated": "#111827",
    "border": "#374151",
    "border2": "#4B5563",
    "text": "#F9FAFB",
    "muted": "#9CA3AF",
    "dim": "#6B7280",
    "accent": "#3B82F6",
    "accent_light": "#1E3A8A",
    "accent2": "#2563EB",
    "green": "#10B981",
    "green_light": "#064E3B",
    "amber": "#F59E0B",
    "amber_light": "#78350F",
    "red": "#EF4444",
    "red_light": "#7F1D1D",
    "gray": "#9CA3AF",
    "sidebar": "#111827",
}

def css() -> str:
    from streamlit import session_state
    dark_mode = session_state.get("theme") == "dark"
    c = COLORS_DARK if dark_mode else COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,700&display=swap');

:root {{
  --tv-text: {c['text']};
  --tv-muted: {c['muted']};
  --tv-dim: {c['dim']};
  --tv-border: {c['border']};
  --tv-bg: {c['bg']};
  --tv-surface: {c['surface']};
}}

/* ── Reset / Base ─────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {{
  background: {c['bg']} !important;
  color: {c['text']} !important;
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif !important;
  font-size: 14px !important;
}}

/* Hide Streamlit chrome */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu, footer {{ display: none !important; }}

/* Main block container */
.block-container {{
  max-width: none !important;
  padding: 2rem 3rem 2rem !important;
  margin: 0 !important;
}}
[data-testid="stMainBlockContainer"] {{
  padding: 2rem 3rem 2rem !important;
}}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: {c['sidebar']} !important;
  border-right: 1px solid {c['border']} !important;
  box-shadow: none !important;
}}
section[data-testid="stSidebar"] {{
  min-width: 260px !important;
  max-width: 260px !important;
}}
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  padding-top: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  background: {c['sidebar']} !important;
}}

/* Sidebar button resets */
[data-testid="stSidebar"] .stButton {{
  margin: 0 !important;
  padding: 0 !important;
}}
[data-testid="stSidebar"] .stButton > button {{
  background: transparent !important;
  border: none !important;
  border-left: 3px solid transparent !important;
  border-radius: 0 !important;
  color: {c['text']} !important;
  font-size: 15px !important;
  font-weight: 500 !important;
  text-align: left !important;
  justify-content: flex-start !important;
  padding: 10px 24px 10px 21px !important;
  min-height: 44px !important;
  width: 100% !important;
  margin: 0 !important;
  box-shadow: none !important;
  transition: background 0.12s, color 0.12s !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: {c['bg2']} !important;
  color: {c['text']} !important;
  border: none !important;
  border-left: 3px solid transparent !important;
  box-shadow: none !important;
}}

/* Active nav item */
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {{
  background: {c['accent_light']} !important;
  color: {c['accent']} !important;
  font-weight: 600 !important;
  box-shadow: none !important;
  border: none !important;
  border-left: 3px solid {c['accent']} !important;
  border-radius: 0 !important;
}}
[data-testid="stSidebar"] button[kind="primary"] p::after,
[data-testid="stSidebar"] button[data-testid="baseButton-primary"] p::after {{
  content: '›';
  position: absolute;
  right: 20px;
  font-size: 18px;
  font-weight: 500;
}}
[data-testid="stSidebar"] button[kind="primary"]:hover,
[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {{
  background: {c['accent2']} !important;
  border-left: 3px solid {c['accent']} !important;
}}

/* ── Main area buttons ────────────────────────────────────────────────────── */
.main .stButton > button, .block-container .stButton > button {{
  border-radius: 6px !important;
  border: 1px solid {c['border']} !important;
  background: {c['surface']} !important;
  color: {c['text']} !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  min-height: 38px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
  transition: border-color 0.12s, background 0.12s !important;
}}
.main .stButton > button:hover, .block-container .stButton > button:hover {{
  border-color: {c['accent']} !important;
  background: {c['surface2']} !important;
  box-shadow: 0 1px 3px rgba(37,99,214,0.1) !important;
}}
button[kind="primary"]:not([data-testid="stSidebar"] *),
button[data-testid="baseButton-primary"]:not([data-testid="stSidebar"] *) {{
  background: {c['accent']} !important;
  border-color: {c['accent']} !important;
  color: #FFFFFF !important;
  box-shadow: 0 1px 3px rgba(37,99,214,0.25) !important;
}}
button[kind="primary"]:not([data-testid="stSidebar"] *):hover,
button[data-testid="baseButton-primary"]:not([data-testid="stSidebar"] *):hover {{
  background: #1D4DB0 !important;
  border-color: #1D4DB0 !important;
}}

/* ── Inputs ───────────────────────────────────────────────────────────────── */
.stTextArea textarea, .stTextInput input {{
  background: {c['surface']} !important;
  border: 1px solid {c['border']} !important;
  border-radius: 6px !important;
  color: {c['text']} !important;
  font-size: 14px !important;
  font-family: 'Inter', system-ui, sans-serif !important;
}}
.stTextArea textarea:focus, .stTextInput input:focus {{
  border-color: {c['accent']} !important;
  box-shadow: 0 0 0 2px rgba(37,99,214,0.12) !important;
  outline: none !important;
}}

/* Selectbox */
[data-baseweb="select"] > div,
[data-baseweb="select"] {{
  background: {c['surface']} !important;
  border-color: {c['border']} !important;
  color: {c['text']} !important;
  border-radius: 6px !important;
}}
[data-baseweb="select"] li {{
  background: {c['surface']} !important;
  color: {c['text']} !important;
}}
[data-baseweb="select"] li:hover {{
  background: {c['accent_light']} !important;
}}

/* Slider */
[data-testid="stSlider"] {{
  color: {c['accent']} !important;
}}

/* File uploader */
[data-testid="stFileUploader"],
[data-testid="stFileUploaderDropzone"] {{
  background: {c['surface']} !important;
  border: 2px dashed {c['border']} !important;
  border-radius: 8px !important;
  color: {c['muted']} !important;
}}
[data-testid="stFileUploader"] section {{
  background: {c['surface']} !important;
}}

/* Expander */
.stExpander,
[data-testid="stExpander"] {{
  border: 1px solid {c['border']} !important;
  border-radius: 8px !important;
  background: {c['surface']} !important;
  box-shadow: none !important;
}}
.stExpander summary, [data-testid="stExpander"] summary {{
  color: {c['text']} !important;
  font-weight: 500 !important;
  background: {c['surface']} !important;
}}

/* Alerts */
div[data-testid="stAlert"] {{
  border-radius: 6px !important;
  font-size: 13.5px !important;
  border: 1px solid {c['border']} !important;
}}

/* Captions / labels */
.stCaption, [data-testid="stCaptionContainer"] p {{
  color: {c['muted']} !important;
  font-size: 12.5px !important;
}}
[data-testid="stWidgetLabel"] p, label, .stSelectbox label {{
  color: {c['muted']} !important;
  font-size: 13px !important;
  font-weight: 500 !important;
}}

/* Progress */
.stProgress > div > div > div > div {{
  background: {c['accent']} !important;
}}

/* Divider */
[data-testid="stDivider"] hr {{
  border-color: {c['border']} !important;
}}

/* Status/spinner */
[data-testid="stStatus"] {{
  border: 1px solid {c['border']} !important;
  border-radius: 8px !important;
  background: {c['surface']} !important;
}}

/* Audio component */
[data-testid="stAudio"] audio {{
  filter: none !important;
}}

/* Dataframe */
[data-testid="stDataFrame"],
.stDataFrame {{
  background: {c['surface']} !important;
  border: none !important;
  border-radius: 8px !important;
  overflow: hidden !important;
}}

/* ── TV component classes ─────────────────────────────────────────────────── */

/* Page header */
.tv-page {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid {c['border']};
}}
.tv-page h1 {{
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: {c['text']};
  letter-spacing: -0.02em;
  line-height: 1.2;
}}
.tv-page p {{ margin: 4px 0 0; font-size: 13.5px; color: {c['muted']}; }}
.tv-page-right {{ text-align: right; flex-shrink: 0; }}

/* Cards */
.tv-card {{
  background: {c['surface']};
  border: 1px solid {c['border']};
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}}
.tv-card-title {{
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: {c['muted']};
  margin: 0 0 12px;
}}
.tv-card-heading {{
  font-size: 14px;
  font-weight: 600;
  color: {c['text']};
  margin: 0 0 8px;
}}

/* Table rows */
.tv-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  font-size: 13.5px;
  padding: 7px 0;
  border-bottom: 1px solid {c['border']};
}}
.tv-row:last-child {{ border-bottom: 0; }}
.tv-row span:first-child {{ color: {c['muted']}; font-size: 13px; }}

/* Table */
.tv-table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
.tv-table th {{
  text-align: left;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: {c['muted']};
  border-bottom: 1px solid {c['border']};
  background: {c['bg']};
}}
.tv-table td {{
  padding: 11px 12px;
  border-bottom: 1px solid {c['border']};
  color: {c['text']};
  vertical-align: middle;
}}
.tv-table tr:last-child td {{ border-bottom: 0; }}
.tv-table tr:hover td {{ background: {c['bg']}; }}
.tv-table td.num {{
  font-variant-numeric: tabular-nums;
  text-align: right;
  font-family: 'Inter', monospace;
}}
.tv-table td.tv-link {{ cursor: pointer; }}

/* Sidebar nav section label */
.tv-nav-section {{
  font-size: 12.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: {c['muted']};
  padding: 20px 24px 10px;
  margin-top: 12px;
}}

/* Sidebar logo */
.tv-brand {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 16px;
  margin-top: -42px; /* Aggressively pull up over Streamlit markdown padding */
  margin-left: -20px;
  margin-right: -20px;
  border-bottom: 1px solid {c['border']};
  margin-bottom: 12px;
}}
.tv-mark {{
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: {c['accent']};
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.tv-mark svg {{ color: white; }}
.tv-brand-name {{ font-size: 15px; font-weight: 700; color: {c['text']}; line-height: 1.1; }}
.tv-brand-sub {{ font-size: 11px; color: {c['muted']}; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; margin-top: 2px; }}

/* Sidebar footer */
.tv-side-foot {{
  margin: 24px 16px 16px;
  padding: 12px 14px;
  background: {c['bg']};
  border: 1px solid {c['border']};
  border-radius: 8px;
  font-size: 12px;
}}
.tv-side-foot-title {{ font-weight: 600; color: {c['text']}; font-size: 12px; margin-bottom: 2px; }}
.tv-side-foot-sub {{ color: {c['muted']}; font-size: 11.5px; }}
.tv-online-dot {{
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: {c['green']};
  margin-right: 5px;
  position: relative;
  top: -1px;
}}

/* Badges */
.tv-badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid transparent;
}}
.tv-badge-demo {{
  background: {c['amber_light']};
  color: {c['amber']};
  border-color: #FDE68A;
}}
.tv-badge-ok {{
  background: {c['green_light']};
  color: {c['green']};
  border-color: #BBF7D0;
}}
.tv-badge-warn {{
  background: {c['amber_light']};
  color: {c['amber']};
  border-color: #FDE68A;
}}
.tv-badge-crit {{
  background: {c['red_light']};
  color: {c['red']};
  border-color: #FCA5A5;
}}
.tv-badge-blue {{
  background: {c['accent_light']};
  color: {c['accent']};
  border-color: {c['accent2']};
}}
.tv-badge-gray {{
  background: {c['bg2']};
  color: {c['muted']};
  border-color: {c['border']};
}}

/* Risk score */
.tv-risk-block {{
  padding: 4px 0;
}}
.tv-risk-num {{
  font-size: 42px;
  font-weight: 700;
  color: {c['text']};
  line-height: 1;
  letter-spacing: -0.03em;
}}
.tv-risk-denom {{
  font-size: 20px;
  font-weight: 400;
  color: {c['muted']};
  margin-left: 2px;
}}
.tv-risk-label {{
  font-size: 13px;
  font-weight: 600;
  margin-top: 4px;
}}

/* Risk bar */
.tv-risk-bar-wrap {{
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: {c['dim']};
  margin-top: 12px;
}}
.tv-risk-bar {{
  height: 5px;
  background: {c['bg2']};
  border-radius: 3px;
  overflow: hidden;
  margin: 4px 0;
}}
.tv-risk-fill {{
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}}

/* Dot indicator */
.tv-dot {{
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.tv-dot-green {{ background: {c['green']}; }}
.tv-dot-amber {{ background: {c['amber']}; }}
.tv-dot-red {{ background: {c['red']}; }}
.tv-dot-blue {{ background: {c['accent']}; }}
.tv-dot-gray {{ background: {c['dim']}; }}

/* Risk factors grid */
.tv-factors {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: {c['border']};
  border: 1px solid {c['border']};
  border-radius: 6px;
  overflow: hidden;
}}
.tv-factor {{
  background: {c['surface']};
  padding: 14px 14px 14px;
}}
.tv-factor-label {{
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: {c['muted']};
  margin-bottom: 8px;
}}
.tv-factor-val {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  font-weight: 500;
  color: {c['text']};
}}

/* Analysis progression stages */
.tv-stages {{
  display: flex;
  gap: 0;
  overflow-x: auto;
  border: 1px solid {c['border']};
  border-radius: 6px;
  overflow: hidden;
}}
.tv-stage {{
  flex: 1;
  min-width: 80px;
  text-align: center;
  padding: 10px 6px;
  background: {c['surface']};
  border-right: 1px solid {c['border']};
  position: relative;
}}
.tv-stage:last-child {{ border-right: 0; }}
.tv-stage.active {{ background: {c['accent_light']}; }}
.tv-stage-num {{
  font-size: 11px;
  font-weight: 700;
  color: {c['dim']};
  display: block;
}}
.tv-stage-label {{
  font-size: 12px;
  font-weight: 500;
  color: {c['muted']};
  margin-top: 2px;
  display: block;
}}
.tv-stage.done .tv-stage-num, .tv-stage.done .tv-stage-label {{ color: {c['accent']}; }}
.tv-stage.active .tv-stage-num, .tv-stage.active .tv-stage-label {{ color: {c['accent']}; font-weight: 600; }}

/* Reasoning chain */
.tv-chain-item {{
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid {c['border']};
  cursor: pointer;
}}
.tv-chain-item:last-child {{ border-bottom: 0; }}
.tv-chain-num {{
  width: 22px; height: 22px;
  border-radius: 50%;
  background: {c['accent_light']};
  border: 1px solid {c['accent2']};
  color: {c['accent']};
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}}
.tv-chain-label {{
  font-size: 13.5px;
  font-weight: 500;
  color: {c['text']};
  flex: 1;
}}
.tv-chain-arrow {{ color: {c['dim']}; font-size: 13px; margin-top: 2px; }}

/* Evidence summary rows */
.tv-evidence-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 0;
  border-bottom: 1px solid {c['border']};
  font-size: 13.5px;
}}
.tv-evidence-row:last-child {{ border-bottom: 0; }}
.tv-evidence-label {{ color: {c['muted']}; font-size: 13px; }}

/* Trust handshake */
.tv-handshake-panel {{
  border: 1px solid {c['border']};
  border-top: 3px solid {c['accent']};
  border-radius: 8px;
  padding: 16px;
  background: {c['surface']};
}}
.tv-handshake-title {{
  font-size: 15px;
  font-weight: 700;
  color: {c['text']};
  margin-bottom: 6px;
}}
.tv-handshake-sub {{
  font-size: 13px;
  color: {c['muted']};
  margin-bottom: 14px;
}}

/* Incident table click arrow */
.tv-arrow {{ color: {c['dim']}; font-size: 13px; }}

/* Section heading */
.tv-section-head {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}}
.tv-section-head-title {{
  font-size: 14px;
  font-weight: 600;
  color: {c['text']};
}}
.tv-section-head-meta {{ font-size: 12px; color: {c['dim']}; }}

/* Muted text */
.tv-muted {{ color: {c['muted']}; font-size: 13px; line-height: 1.55; }}
.tv-dim {{ color: {c['dim']}; font-size: 12px; }}
.tv-note {{ font-size: 12.5px; color: {c['muted']}; margin-top: 6px; line-height: 1.5; }}

/* Footer */
.tv-footer {{
  margin-top: 28px;
  padding-top: 14px;
  border-top: 1px solid {c['border']};
  color: {c['dim']};
  font-size: 12px;
}}

/* Upload zone */
.tv-upload-zone {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed {c['border']};
  border-radius: 10px;
  background: {c['bg']};
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}}
.tv-upload-zone:hover {{
  border-color: {c['accent']};
  background: {c['accent_light']};
}}
.tv-upload-icon {{ font-size: 32px; color: {c['accent']}; margin-bottom: 10px; }}
.tv-upload-title {{ font-size: 14px; font-weight: 600; color: {c['text']}; margin-bottom: 4px; }}
.tv-upload-sub {{ font-size: 12.5px; color: {c['muted']}; }}

/* Speaker table row */
.tv-spk-row {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid {c['border']};
  cursor: pointer;
  transition: background 0.1s;
}}
.tv-spk-row:hover {{ background: {c['bg']}; }}
.tv-spk-row.selected {{ background: {c['accent_light']}; }}
.tv-spk-avatar {{
  width: 30px; height: 30px;
  border-radius: 50%;
  background: {c['bg2']};
  display: flex;
  align-items: center;
  justify-content: center;
  color: {c['muted']};
  font-size: 13px;
  flex-shrink: 0;
}}

/* Analysis pipeline sidebar */
.tv-pipeline-item {{
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid {c['border']};
  font-size: 13.5px;
}}
.tv-pipeline-item:last-child {{ border-bottom: 0; }}
.tv-pipeline-num {{
  width: 22px; height: 22px;
  border-radius: 50%;
  background: {c['bg2']};
  border: 1px solid {c['border']};
  color: {c['muted']};
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.tv-pipeline-num.active {{
  background: {c['accent_light']};
  border-color: {c['accent2']};
  color: {c['accent']};
}}
.tv-pipeline-num.done {{
  background: #DCFCE7;
  border-color: #BBF7D0;
  color: {c['green']};
}}
.tv-pipeline-label {{ flex: 1; color: {c['text']}; font-weight: 500; }}
.tv-pipeline-arrow {{ color: {c['dim']}; }}

/* Waveform mini */
.tv-wave {{
  height: 40px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  padding: 4px 0;
}}
.tv-wave i {{
  width: 3px;
  background: {c['accent']};
  opacity: 0.6;
  display: block;
  border-radius: 1px;
}}

/* Responsive */
@media (max-width: 1100px) {{
  .tv-factors {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 900px) {{
  .block-container {{ padding: 1rem 1rem 1.5rem !important; }}
  .tv-page {{ flex-direction: column; }}
  section[data-testid="stSidebar"] {{
    min-width: 200px !important;
    max-width: 200px !important;
  }}
}}
/* Streamlit overrides */
header[data-testid="stHeader"],
.stDeployButton,
[data-testid="stToolbar"] {{
  display: none !important;
}}
#MainMenu {{
  visibility: hidden !important;
}}
footer {{
  visibility: hidden !important;
}}
</style>
"""
