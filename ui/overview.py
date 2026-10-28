"""Overview — TRUSTVOICE Security Console main dashboard."""

from __future__ import annotations

from html import escape

import streamlit as st
import streamlit.components.v1 as _stc

from ui.theme import COLORS, status_color


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _render_progression_card(stages_risk: list[int], label: str):
    """Render the analysis progression card using components.v1.html so the
    SVG is guaranteed to display regardless of Streamlit version."""
    svg = _progression_svg(stages_risk)
    # Wrap in a styled container so fonts/colours match the rest of the page
    html_blob = f"""
    <!doctype html>
    <html>
    <head>
    <style>
      body {{margin:0;padding:0;background:#fff;font-family:'Inter','Segoe UI',system-ui,sans-serif;}}
      .wrap {{padding:0;}}
      .head {{display:flex;justify-content:space-between;align-items:center;
              margin-bottom:10px;}}
      .title {{font-size:14px;font-weight:600;color:var(--tv-text);}}
      .meta  {{font-size:12px;color:var(--tv-dim);}}
    </style>
    </head>
    <body>
    <div class="wrap">
      <div class="head">
        <span class="title">Analysis progression</span>
        <span class="meta">{label}</span>
      </div>
      {svg}
    </div>
    </body>
    </html>
    """
    # Height: 14px head + 10px gap + 140px svg + 4px pad ≈ 168px; card border
    # is rendered by the outer Streamlit container via CSS, so we wrap in a
    # tv-card div here too so the border + padding are consistent.
    render("""<div class="tv-card" style="padding:14px 16px 10px">""")
    _stc.html(html_blob, height=160, scrolling=False)
    render("""</div>""")


# ── Helpers ────────────────────────────────────────────────────────────────

def _risk_color(score: int) -> str:
    if score >= 80:
        return COLORS["red"]
    if score >= 55:
        return COLORS["amber"]
    if score >= 30:
        return "#2563D6"
    return COLORS["green"]


def _risk_label(score: int, risk: str | None = None) -> str:
    if risk:
        return risk.replace("_", " ").title()
    if score >= 80:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 30:
        return "Elevated"
    return "Low"


def _factor_dot(val: int | None, label: str) -> str:
    """Return a small colored dot + label text for a factor value."""
    if val is None:
        color_cls = "tv-dot-gray"
        text = "N/A"
    elif val >= 70:
        color_cls = "tv-dot-green"
        text = "Normal"
    elif val >= 45:
        color_cls = "tv-dot-amber"
        text = "Review"
    else:
        color_cls = "tv-dot-red"
        text = "Suspicious" if "voice" in label.lower() or "speaker" in label.lower() else "Alert"
    return f'<span class="tv-dot {color_cls}"></span> {text}'


def _factor_label_from_result(result: dict, key: str) -> str:
    """Get human-readable label for a risk factor using actual result data."""
    factors = (result.get("factor_display") or {})
    val = factors.get(key)

    # Special label overrides from actual analysis data
    if key == "Voice Authenticity":
        vl = (result.get("voice_label") or "").upper()
        if "SPOOF" in vl:
            return "Likely spoof"
        if "AUTHENTIC" in vl:
            return "Authentic"
        if "INCONCLUSIVE" in vl:
            return "Inconclusive"
        return "Suspicious" if (val or 100) < 50 else "Unclear"

    if key == "Speaker Identity":
        ids = str(result.get("identity_status") or "").upper()
        if ids == "VERIFIED":
            return "Verified"
        if ids == "MISMATCH":
            return "Mismatch"
        if ids == "UNVERIFIED":
            return "Unverified"
        return "Not available"

    if key == "Intent Safety":
        intent = str((result.get("intent") or {}).get("intent") or "unknown").replace("_", " ")
        return intent.title() if intent != "unknown" else "Unknown"

    if key == "Behaviour Safety":
        sigs = result.get("behaviour_signals") or []
        return sigs[0].replace("_", " ").title() if sigs else ("Normal" if (val or 100) >= 70 else "Urgency")

    if key == "Context Safety":
        sigs = result.get("context_signals") or []
        if sigs:
            return sigs[0].replace("_", " ").title()
        return "Sensitive action" if (val or 100) < 50 else "Normal"

    return "—"


def _dot_for_factor(result: dict, key: str) -> str:
    """Return a colored dot for the given factor."""
    factors = result.get("factor_display") or {}
    val = factors.get(key)
    if val is None:
        return '<span class="tv-dot tv-dot-gray"></span>'
    if val >= 70:
        return '<span class="tv-dot tv-dot-green"></span>'
    if val >= 45:
        return '<span class="tv-dot tv-dot-amber"></span>'
    return '<span class="tv-dot tv-dot-red"></span>'


def _progression_svg(stages_risk: list[int]) -> str:
    """Create an SVG line chart for analysis progression."""
    w, h = 560, 110
    pad_l, pad_r, pad_t, pad_b = 12, 12, 12, 28
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b

    n = len(stages_risk)
    xs = [pad_l + i * chart_w / (n - 1) for i in range(n)]
    # Convert risk score (0-100, higher=riskier) to y coord
    ys = [pad_t + chart_h * (1 - r / 100) for r in stages_risk]

    # Grid lines
    grids = ""
    for y_pct in [0.25, 0.5, 0.75]:
        gy = pad_t + chart_h * y_pct
        grids += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" stroke="var(--tv-border)" stroke-width="1"/>'

    # Area fill
    pts_area = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    pts_area += f" {xs[-1]:.1f},{pad_t + chart_h} {xs[0]:.1f},{pad_t + chart_h}"

    # Line
    pts_line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))

    labels = ["01\nAudio", "02\nVoice", "03\nIdentity", "04\nIntent", "05\nBehav.", "06\nFinal"]

    # Circles
    circles = ""
    for x, y in zip(xs, ys):
        circles += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" '
            f'fill="var(--tv-surface)" stroke="#2563D6" stroke-width="2.5"/>'
        )

    # Labels
    label_els = ""
    for i, (x, lab) in enumerate(zip(xs, labels)):
        parts = lab.split("\n")
        label_els += (
            f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" '
            f'font-size="10.5" fill="var(--tv-dim)" font-family="Inter,system-ui">'
            f'{escape(parts[0])}</text>'
        )
        if len(parts) > 1:
            label_els += (
                f'<text x="{x:.1f}" y="{h}" text-anchor="middle" '
                f'font-size="11" fill="var(--tv-muted)" font-family="Inter,system-ui">'
                f'{escape(parts[1])}</text>'
            )

    return f"""
    <svg width="100%" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="display:block">
      <defs>
        <linearGradient id="prog-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#2563D6" stop-opacity="0.12"/>
          <stop offset="100%" stop-color="#2563D6" stop-opacity="0.01"/>
        </linearGradient>
      </defs>
      {grids}
      <polygon points="{pts_area}" fill="url(#prog-grad)"/>
      <polyline points="{pts_line}" fill="none" stroke="#2563D6"
        stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      {circles}
      {label_els}
    </svg>
    """


def _reasoning_chain_html(result: dict | None) -> str:
    stages = [
        ("Audio", "File decoded and preprocessed"),
        ("Voice authenticity", result and (result.get("voice_display") or result.get("voice_label") or "Analyzed") or "—"),
        ("Speaker identity", result and str(result.get("identity_status") or "Not available").replace("_", " ") or "—"),
        ("Conversation", result and str((result.get("intent") or {}).get("intent") or "Analyzed").replace("_", " ").title() or "—"),
        ("Risk fusion", result and f"{result.get('interaction_risk', '—')}" or "—"),
        ("Trust handshake", result and ("Required" if result.get("handshake_required") else "Not required") or "—"),
    ]
    rows = ""
    for i, (label, detail) in enumerate(stages, 1):
        rows += f"""
        <div class="tv-chain-item">
          <div class="tv-chain-num">{i}</div>
          <div class="tv-chain-label">{escape(label)}</div>
          <div class="tv-chain-arrow">↓</div>
        </div>"""
    return rows


def _evidence_summary_html(result: dict) -> str:
    anti = (result.get("last_analysis") or {}).get("anti_spoof") or {}
    quality = (result.get("last_analysis") or {}).get("quality_gate") or {}
    intent = str((result.get("intent") or {}).get("intent") or "—").replace("_", " ").title()
    behaviour = "; ".join(result.get("behaviour_signals") or []) or "None"
    context = "; ".join(result.get("context_signals") or []) or "None"
    transcript = str(result.get("transcript") or "")[:120] or "—"
    if len(result.get("transcript") or "") > 120:
        transcript += "…"

    rows = [
        ("Voice authenticity", result.get("voice_display") or result.get("voice_label") or "—"),
        ("Speaker identity", str(result.get("identity_status") or "—").replace("_", " ")),
        ("Transcript", transcript),
        ("Intent", intent),
        ("Behaviour", behaviour),
        ("Context", context),
        ("Final risk", result.get("interaction_risk") or "—"),
        ("Decision", result.get("action") or "—"),
    ]
    html = ""
    for label, val in rows:
        html += f"""
        <div class="tv-evidence-row">
          <span class="tv-evidence-label">{escape(label)}</span>
          <span style="color:var(--tv-text);font-weight:500;font-size:13px">{escape(str(val))}</span>
        </div>"""
    return html


# ── Main render ─────────────────────────────────────────────────────────────

def render_overview():
    result = st.session_state.get("last_result")
    audio = st.session_state.get("last_analysis") or {}
    is_demo = not result

    # trust_score: higher = safer → impersonation_risk = 100 - trust_score
    trust_score = int(result["trust_score"]) if result else None
    if trust_score is not None:
        impersonation_risk = max(0, min(100, 100 - trust_score))
        interaction_risk = result.get("interaction_risk", "—")
    else:
        impersonation_risk = 94
        interaction_risk = "CRITICAL"

    risk_col = _risk_color(impersonation_risk)
    risk_lbl = _risk_label(impersonation_risk, interaction_risk if result else "Critical")
    risk_fill = impersonation_risk

    # ── Page header ─────────────────────────────────────────────────────────
    demo_badge = '<span class="tv-badge tv-badge-demo">DEMO DATA</span>' if is_demo else ""
    render(f"""
    <div class="tv-page">
      <div>
        <h1>TRUSTVOICE SECURITY CONSOLE</h1>
        <p>Voice authenticity, identity and interaction risk.&nbsp;&nbsp;{demo_badge}</p>
      </div>
    </div>
    """)

    # ── Row 1: Risk score + Risk factors ────────────────────────────────────
    col_risk, col_factors = st.columns([1, 2.2], gap="medium")

    with col_risk:
        factors = (result or {}).get("factor_display") or {}
        render(f"""
        <div class="tv-card" style="height:100%">
          <div class="tv-card-title">Impersonation risk
            <span style="float:right;font-size:10.5px;color:{COLORS['muted']}">
              {'Simulated analysis' if is_demo else 'Current analysis'}
            </span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
            <span class="tv-risk-num">{impersonation_risk}</span>
            <span class="tv-risk-denom">/ 100</span>
            <span class="tv-badge {'tv-badge-crit' if impersonation_risk >= 80 else ('tv-badge-warn' if impersonation_risk >= 55 else 'tv-badge-blue')}"
              style="margin-left:6px">{escape(risk_lbl)}</span>
          </div>
          <div class="tv-risk-bar">
            <div class="tv-risk-fill" style="width:{risk_fill}%;background:{risk_col}"></div>
          </div>
          <div class="tv-risk-bar-wrap">
            <span>Low</span><span>Critical</span>
          </div>
        </div>
        """)

    with col_factors:
        # Risk factors panel
        if result:
            va_dot = _dot_for_factor(result, "Voice Authenticity")
            va_lbl = escape(_factor_label_from_result(result, "Voice Authenticity"))
            si_dot = _dot_for_factor(result, "Speaker Identity")
            si_lbl = escape(_factor_label_from_result(result, "Speaker Identity"))
            it_dot = _dot_for_factor(result, "Intent Safety")
            it_lbl = escape(_factor_label_from_result(result, "Intent Safety"))
            be_dot = _dot_for_factor(result, "Behaviour Safety")
            be_lbl = escape(_factor_label_from_result(result, "Behaviour Safety"))
            co_dot = _dot_for_factor(result, "Context Safety")
            co_lbl = escape(_factor_label_from_result(result, "Context Safety"))
        else:
            # Demo data
            va_dot = '<span class="tv-dot tv-dot-red"></span>'
            va_lbl = "Suspicious"
            si_dot = '<span class="tv-dot tv-dot-amber"></span>'
            si_lbl = "Mismatch"
            it_dot = '<span class="tv-dot tv-dot-amber"></span>'
            it_lbl = "OTP request"
            be_dot = '<span class="tv-dot tv-dot-amber"></span>'
            be_lbl = "Urgency"
            co_dot = '<span class="tv-dot tv-dot-amber"></span>'
            co_lbl = "Sensitive action"

        render(f"""
        <div class="tv-card" style="height:100%">
          <div class="tv-section-head">
            <span class="tv-section-head-title" style="font-size:14px;font-weight:600">Risk factors</span>
            <span class="tv-section-head-meta">{'Latest simulated analysis' if is_demo else 'Current evaluation'}</span>
          </div>
          <div class="tv-factors">
            <div class="tv-factor">
              <div class="tv-factor-label">Voice Authenticity</div>
              <div class="tv-factor-val">{va_dot} {va_lbl}</div>
            </div>
            <div class="tv-factor">
              <div class="tv-factor-label">Speaker Identity</div>
              <div class="tv-factor-val">{si_dot} {si_lbl}</div>
            </div>
            <div class="tv-factor">
              <div class="tv-factor-label">Intent</div>
              <div class="tv-factor-val">{it_dot} {it_lbl}</div>
            </div>
            <div class="tv-factor">
              <div class="tv-factor-label">Behaviour</div>
              <div class="tv-factor-val">{be_dot} {be_lbl}</div>
            </div>
            <div class="tv-factor">
              <div class="tv-factor-label">Context</div>
              <div class="tv-factor-val">{co_dot} {co_lbl}</div>
            </div>
          </div>
        </div>
        """)

    st.write("")  # spacing

    # ── Row 2: Analysis Progression + Reasoning Chain ───────────────────────
    col_prog, col_chain = st.columns([1.55, 1], gap="medium")

    with col_prog:
        # Compute progression data
        if result:
            fd = result.get("factor_display") or {}
            stages_risk = [
                max(5, min(95, 100 - (fd.get("Voice Authenticity") or 50))),
                max(5, min(95, 100 - (fd.get("Voice Authenticity") or 50))),
                max(5, min(95, 100 - (fd.get("Speaker Identity") or 50))),
                max(5, min(95, 100 - (fd.get("Intent Safety") or 50))),
                max(5, min(95, 100 - (fd.get("Behaviour Safety") or 50))),
                impersonation_risk,
            ]
        else:
            stages_risk = [32, 38, 42, 55, 72, 92]

        prog_label = "Simulated demonstration" if is_demo else "Current evaluation"
        _render_progression_card(stages_risk, prog_label)



    with col_chain:
        chain_rows = _reasoning_chain_html(result)
        render(f"""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Reasoning chain</span>
            <span class="tv-section-head-meta">{'Current evaluation' if result else '—'}</span>
          </div>
          {chain_rows}
        </div>
        """)

    # ── Row 3: Analysis Overview ─────────────────────────────────────────────
    render("""<div style="margin-top:4px"></div>""")
    col_ov, col_tr = st.columns([1, 1], gap="medium")

    with col_ov:
        if result:
            ev_html = _evidence_summary_html(result)
        else:
            ev_html = """
            <div class="tv-evidence-row"><span class="tv-evidence-label">Voice authenticity</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Suspicious</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Speaker identity</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Mismatch</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Transcript</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Hi, this is Rahul…</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Intent</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">OTP request</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Behaviour</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Urgency</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Context</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Sensitive action</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Final risk</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">CRITICAL</span></div>
            <div class="tv-evidence-row"><span class="tv-evidence-label">Decision</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">Verify identity</span></div>
            """
        render(f"""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Analysis overview</span>
            <span class="tv-section-head-meta">Evidence summary</span>
          </div>
          {ev_html}
        </div>
        """)

    with col_tr:
        transcript = (result or {}).get("transcript") or ""
        intent_str = str(((result or {}).get("intent") or {}).get("intent") or "—").replace("_", " ").title()
        behaviour_str = "; ".join((result or {}).get("behaviour_signals") or []) or "—"
        context_str = "; ".join((result or {}).get("context_signals") or []) or "—"

        if is_demo:
            transcript_body = '"Hi, this is Rahul. I\'m in a meeting. I need you to send the OTP immediately."'
            intent_str = "Credential / OTP request"
            behaviour_str = "Urgency"
            context_str = "Sensitive action"
        else:
            transcript_body = f'"{escape(transcript[:240])}"' if transcript else "No transcript recorded."
            if len(transcript) > 240:
                transcript_body += "…"

        render(f"""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Transcript & intelligence</span>
          </div>
          <div style="font-size:14px;color:var(--tv-text);line-height:1.6;padding:8px 0;border-bottom:1px solid var(--tv-border);margin-bottom:10px;font-style:italic">
            {transcript_body}
          </div>
          <div class="tv-evidence-row"><span class="tv-evidence-label">Intent</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">{escape(intent_str)}</span></div>
          <div class="tv-evidence-row"><span class="tv-evidence-label">Behaviour</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">{escape(behaviour_str)}</span></div>
          <div class="tv-evidence-row" style="border-bottom:0"><span class="tv-evidence-label">Context</span><span style="color:var(--tv-text);font-weight:500;font-size:13px">{escape(context_str)}</span></div>
        </div>
        """)

    # ── Trust Handshake ──────────────────────────────────────────────────────
    handshake_req = (result or {}).get("handshake_required", is_demo)
    if handshake_req:
        render(f"""
        <div class="tv-handshake-panel" style="margin-top:4px">
          <div class="tv-handshake-title">Trust Handshake</div>
          <div class="tv-handshake-sub">
            High-risk interaction detected. Identity verification required before any sensitive action.
          </div>
        </div>
        """)
        h1, h2, h3 = st.columns(3)
        with h1:
            if st.button("✓ Confirm", use_container_width=True, key="ov_hs_yes"):
                st.session_state.handshake_result = {"status": "CONFIRMED", "message": "Simulated confirmation. Sensitive action may continue."}
        with h2:
            if st.button("✕ Deny", use_container_width=True, key="ov_hs_no"):
                st.session_state.handshake_result = {"status": "DENIED", "message": "Simulated denial. Action blocked."}
        with h3:
            if st.button("No response", use_container_width=True, key="ov_hs_none"):
                st.session_state.handshake_result = {"status": "NO_RESPONSE", "message": "No confirmation. Action blocked pending manual verification."}

        hs_result = st.session_state.get("handshake_result")
        if hs_result:
            status = hs_result.get("status", "")
            color = "#16A34A" if status == "CONFIRMED" else "#DC2626"
            render(f"""
            <div style="margin-top:8px;padding:10px 14px;border-radius:6px;background:var(--tv-surface);
              border:1px solid var(--tv-border);font-size:13px;color:{color};font-weight:500">
              {escape(status)}: {escape(hs_result.get('message', ''))}
            </div>
            """)
        st.caption("Prototype / simulated — does not contact a manager, device, or bank.")

    # ── Nav to Analyze Audio ─────────────────────────────────────────────────
    render("""<div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--tv-border)">""")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("→ Analyze new audio", use_container_width=True, type="primary", key="ov_goto_analyze"):
            st.session_state.ui_nav = "Analyze Audio"
            st.rerun()
    render("""</div>""")
    render("""<div class="tv-footer">TRUSTVOICE AI · SIH prototype · local processing · not a certified fraud verdict</div>""")
