"""Incidents — security event queue."""

from __future__ import annotations

import time
from html import escape

import streamlit as st

from ui.theme import COLORS
from utils.reporting import REPORTLAB_AVAILABLE, build_incident_report, build_incident_report_pdf


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


# ── Demo incident records ──────────────────────────────────────────────────

DEMO_INCIDENTS = [
    {
        "id": "TV-001",
        "type": "Voice impersonation attempt",
        "speaker": "Rahul Sharma",
        "risk": 94,
        "risk_band": "Critical",
        "action": "Verification required",
        "timestamp": "14:32",
        "voice": "LIKELY_SPOOF",
        "identity": "MISMATCH",
        "intent": "credential_request",
        "behaviour": "Urgency",
        "context": "Sensitive action",
        "transcript": "Hi, this is Rahul. I'm in a meeting. I need you to send the OTP immediately.",
        "handshake": True,
    },
    {
        "id": "TV-002",
        "type": "Sensitive request detected",
        "speaker": "Unknown",
        "risk": 78,
        "risk_band": "High",
        "action": "Warning issued",
        "timestamp": "12:18",
        "voice": "INCONCLUSIVE",
        "identity": "UNVERIFIED",
        "intent": "financial_request",
        "behaviour": "Authority appeal",
        "context": "Financial action",
        "transcript": "I need you to transfer funds to account 9876 urgently.",
        "handshake": False,
    },
    {
        "id": "TV-003",
        "type": "Identity evidence mismatch",
        "speaker": "Vikram Mehta",
        "risk": 71,
        "risk_band": "High",
        "action": "Review required",
        "timestamp": "09:44",
        "voice": "LIKELY_AUTHENTIC",
        "identity": "MISMATCH",
        "intent": "sensitive_data_request",
        "behaviour": "None",
        "context": "Access request",
        "transcript": "This is Vikram, I need access to the client files right away.",
        "handshake": False,
    },
    {
        "id": "TV-004",
        "type": "Routine interaction",
        "speaker": "Ananya Rao",
        "risk": 18,
        "risk_band": "Low",
        "action": "Allowed",
        "timestamp": "Yesterday",
        "voice": "LIKELY_AUTHENTIC",
        "identity": "VERIFIED",
        "intent": "normal_conversation",
        "behaviour": "None",
        "context": "Normal",
        "transcript": "Good morning, just calling to confirm the meeting at 3 PM.",
        "handshake": False,
    },
]


def _risk_badge(score: int, band: str) -> str:
    if score >= 80 or band.upper() == "CRITICAL":
        cls = "tv-badge-crit"
    elif score >= 55 or band.upper() in ("HIGH", "ELEVATED"):
        cls = "tv-badge-warn"
    elif score >= 30:
        cls = "tv-badge-blue"
    else:
        cls = "tv-badge-ok"
    return f'<span class="tv-badge {cls}">● {score} / 100</span>'


def _incident_detail_html(inc: dict) -> str:
    risk = inc["risk"]
    if risk >= 80:
        risk_cls = "tv-badge-crit"
    elif risk >= 55:
        risk_cls = "tv-badge-warn"
    else:
        risk_cls = "tv-badge-ok"

    handshake_str = "Required" if inc.get("handshake") else "Not required"
    voice_str = str(inc.get("voice", "—")).replace("_", " ").title()
    identity_str = str(inc.get("identity", "—")).replace("_", " ").title()
    intent_str = str(inc.get("intent", "—")).replace("_", " ").title()

    return f"""
    <div class="tv-card" style="border-top:3px solid {'#DC2626' if risk >= 80 else ('#D97706' if risk >= 55 else '#16A34A')}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
        <div>
          <div style="font-size:18px;font-weight:700;color:var(--tv-text);margin-bottom:3px">{escape(inc['id'])}</div>
          <div style="font-size:13px;color:var(--tv-muted)">{escape(inc['type'])}</div>
        </div>
        <span class="tv-badge {risk_cls}" style="font-size:14px;padding:4px 12px">
          {risk} / 100
        </span>
      </div>

      <div class="tv-section-head" style="margin-bottom:8px">
        <span class="tv-section-head-title">Evidence</span>
      </div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Speaker</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(inc['speaker'])}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Voice authenticity</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(voice_str)}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Identity evidence</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(identity_str)}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Intent</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(intent_str)}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Behaviour</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(inc.get('behaviour', '—'))}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Context</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(inc.get('context', '—'))}</span></div>
      <div class="tv-evidence-row"><span class="tv-evidence-label">Trust handshake</span><span style="font-size:13px;font-weight:500;color:var(--tv-text)">{handshake_str}</span></div>
      <div class="tv-evidence-row" style="border-bottom:0"><span class="tv-evidence-label">Action taken</span><span style="font-size:13px;font-weight:600;color:var(--tv-text)">{escape(inc['action'])}</span></div>

      <div style="margin-top:14px;padding:12px;background:var(--tv-bg);border-radius:6px;border:1px solid var(--tv-border)">
        <div style="font-size:11.5px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Transcript</div>
        <div style="font-size:13.5px;color:var(--tv-text);line-height:1.6;font-style:italic">"{escape(inc.get('transcript', ''))}"</div>
      </div>
    </div>
    """


def _get_incidents() -> list[dict]:
    """Return real incidents from session state + demo records."""
    incidents = []

    # Real incident from last analysis
    result = st.session_state.get("last_result")
    if result:
        trust = int(result.get("trust_score", 50))
        imp_risk = max(0, min(100, 100 - trust))
        band = result.get("interaction_risk", "LOW")
        if imp_risk >= 25:  # only show if noteworthy
            ts = time.strftime("%H:%M")
            incidents.append({
                "id": "TV-LIVE",
                "type": _classify_type(result),
                "speaker": str(result.get("identity_status") or "Unknown").replace("_", " "),
                "risk": imp_risk,
                "risk_band": band,
                "action": str(result.get("action", "—")).replace("_", " "),
                "timestamp": ts,
                "voice": result.get("voice_label", "—"),
                "identity": result.get("identity_status", "—"),
                "intent": str((result.get("intent") or {}).get("intent", "—")),
                "behaviour": "; ".join(result.get("behaviour_signals") or []) or "None",
                "context": "; ".join(result.get("context_signals") or []) or "None",
                "transcript": result.get("transcript", ""),
                "handshake": result.get("handshake_required", False),
                "_live": True,
            })

    incidents.extend(DEMO_INCIDENTS)
    return incidents


def _classify_type(result: dict) -> str:
    risk = result.get("interaction_risk", "LOW")
    intent = str((result.get("intent") or {}).get("intent", "")).lower()
    if "credential" in intent or "otp" in intent:
        return "Credential / OTP request"
    if "financial" in intent:
        return "Financial request"
    if "sensitive" in intent:
        return "Sensitive data request"
    if risk in ("HIGH", "CRITICAL"):
        return "High-risk interaction"
    return "Security event"


def render_incidents():
    render("""
    <div class="tv-page">
      <div>
        <h1>INCIDENTS <span class="tv-badge tv-badge-demo" style="font-size:12px;vertical-align:middle;margin-left:8px">DEMO DATA</span></h1>
        <p>Security events requiring review, verification or follow-up.</p>
      </div>
    </div>
    """)

    # Init selected incident
    if "incidents_selected" not in st.session_state:
        st.session_state.incidents_selected = None
        
    if "incident" in st.query_params:
        st.session_state.incidents_selected = st.query_params["incident"]
        st.query_params.clear()

    incidents = _get_incidents()
    search = st.text_input("Search incidents", placeholder="Search incidents…",
                           key="incidents_search", label_visibility="collapsed")
    if search:
        q = search.lower()
        incidents = [
            i for i in incidents
            if q in i["id"].lower() or q in i["type"].lower()
            or q in i["speaker"].lower() or q in i["action"].lower()
        ]

    # ── Layout ──────────────────────────────────────────────────────────────
    col_table, col_detail = st.columns([1.7, 1], gap="medium")

    with col_table:
        n_real = sum(1 for i in incidents if i.get("_live"))
        n_demo = len(incidents) - n_real
        render(f"""
        <div class="tv-card" style="padding:0">
          <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid var(--tv-border)">
            <div style="font-size:14px;font-weight:600;color:var(--tv-text)">Incident queue</div>
            <div style="font-size:12px;color:var(--tv-dim)">{len(incidents)} {'record' if len(incidents) == 1 else 'records'}{' · ' + str(n_demo) + ' simulated' if n_demo else ''}</div>
          </div>
        """)
        
        # Native column layout imitating a clean HTML table
        st.markdown('<div style="padding:0 16px;">', unsafe_allow_html=True)
        
        # Header
        hc = st.columns([1.2, 2.2, 1.5, 1.2, 1.5, 1, 0.4], vertical_alignment="center")
        hc[0].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Incident</span>', unsafe_allow_html=True)
        hc[1].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Type</span>', unsafe_allow_html=True)
        hc[2].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Speaker</span>', unsafe_allow_html=True)
        hc[3].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Risk</span>', unsafe_allow_html=True)
        hc[4].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Action</span>', unsafe_allow_html=True)
        hc[5].markdown('<span style="font-size:12px;font-weight:600;color:var(--tv-muted);text-transform:uppercase;">Timestamp</span>', unsafe_allow_html=True)
        
        st.markdown('<hr style="margin:8px 0;border-color:var(--tv-border);">', unsafe_allow_html=True)
        
        for idx, inc in enumerate(incidents):
            badge = _risk_badge(inc["risk"], inc["risk_band"])
            selected = st.session_state.incidents_selected == inc["id"]
            
            c = st.columns([1.2, 2.2, 1.5, 1.2, 1.5, 1, 0.4], vertical_alignment="center")
            c[0].markdown(f'<span style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{escape(inc["id"])}</span>', unsafe_allow_html=True)
            c[1].markdown(f'<span style="font-size:13.5px;color:var(--tv-text)">{escape(inc["type"])}</span>', unsafe_allow_html=True)
            c[2].markdown(f'<span style="font-size:13.5px;color:var(--tv-text)">{escape(inc["speaker"])}</span>', unsafe_allow_html=True)
            c[3].html(badge)
            c[4].markdown(f'<span style="font-size:13.5px;color:var(--tv-text)">{escape(inc["action"])}</span>', unsafe_allow_html=True)
            c[5].markdown(f'<span style="font-size:13.5px;color:var(--tv-dim)">{escape(inc["timestamp"])}</span>', unsafe_allow_html=True)
            
            # The click button
            if c[6].button("›", key=f"inc_btn_{inc['id']}", type="tertiary"):
                st.session_state.incidents_selected = inc["id"]
                st.rerun()
                
            if idx < len(incidents) - 1:
                st.markdown('<hr style="margin:2px 0;border-color:var(--tv-border);">', unsafe_allow_html=True)
            else:
                st.markdown('<div style="margin-bottom:8px"></div>', unsafe_allow_html=True)

        st.markdown('</div></div>', unsafe_allow_html=True)

    with col_detail:
        sel_id = st.session_state.incidents_selected
        if sel_id:
            sel_inc = next((i for i in incidents if i["id"] == sel_id), None)
            if sel_inc:
                render(_incident_detail_html(sel_inc))
                if st.button("✕ Close", key="inc_close", use_container_width=True):
                    st.session_state.incidents_selected = None
                    st.rerun()

                # Export functionality (preserved from old Reports)
                with st.expander("Export incident report"):
                    if st.button("Generate PDF report", use_container_width=True, key="inc_gen_pdf"):
                        try:
                            if sel_inc.get("_live") and st.session_state.get("last_result"):
                                rep = build_incident_report(st.session_state)
                            else:
                                # Mock report structure for demo incidents so export doesn't break
                                rep = {
                                    "report_id": sel_inc["id"],
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "scenario": sel_inc["type"],
                                    "interaction_risk": sel_inc["risk_band"],
                                    "trust_score": sel_inc["risk"],
                                    "recommended_action": sel_inc["action"],
                                    "voice_authenticity": "Suspicious",
                                    "identity_status": "Mismatch",
                                    "prototype_note": "Demo record export."
                                }

                            st.session_state.incident_report = rep
                            if REPORTLAB_AVAILABLE:
                                st.session_state.incident_report_pdf = build_incident_report_pdf(rep)
                                st.session_state.incident_report_filename = f"{rep.get('report_id', 'incident')}.pdf"
                                st.success("Report generated.")
                            else:
                                st.error("PDF generator unavailable (reportlab not installed).")
                        except Exception as exc:
                            st.error(str(exc))

                    if st.session_state.get("incident_report_pdf"):
                        st.download_button(
                            label="Download PDF",
                            data=st.session_state.incident_report_pdf,
                            file_name=st.session_state.incident_report_filename,
                            mime="application/pdf",
                            use_container_width=True,
                            key="inc_dl_pdf",
                        )
                        st.download_button(
                            label="Download JSON",
                            data=json.dumps(st.session_state.incident_report, indent=2),
                            file_name=st.session_state.incident_report_filename.replace(".pdf", ".json"),
                            mime="application/json",
                            use_container_width=True,
                            key="inc_dl_json",
                        )
        else:
            render("""
            <div class="tv-card" style="text-align:center;padding:40px 20px">
              <div style="font-size:24px;margin-bottom:10px">📋</div>
              <div style="font-size:14px;font-weight:500;color:var(--tv-text);margin-bottom:4px">Select an incident</div>
              <div style="font-size:13px;color:var(--tv-muted)">Click any row to view evidence, transcript and actions</div>
            </div>
            """)

    render("""<div class="tv-footer">TRUSTVOICE AI · demo records are illustrative — TV-LIVE reflects the most recent analysis</div>""")
