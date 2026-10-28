"""Incident report generation."""

from html import escape
import json

import streamlit as st

from ui.components import render
from ui.console import render_topbar
from utils.reporting import REPORTLAB_AVAILABLE, build_incident_report, build_incident_report_pdf


def _fmt_intent(rep: dict) -> str:
    intent = rep.get("intent") or {}
    if isinstance(intent, dict):
        return str(intent.get("intent") or "—").replace("_", " ")
    return str(intent or "—").replace("_", " ")


def _fmt_list(value) -> str:
    if not value:
        return "None recorded"
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def render_reports():
    render_topbar("Reports")
    render(st, """
    <div class="tv-card">
      <div class="tv-card-title">Incident report</div>
      <div class="tv-muted">Generate a summary from the latest analysis in this session. Prototype limitations stay attached to the export.</div>
    </div>
    """)
    if st.button("Generate incident report", use_container_width=True):
        try:
            report = build_incident_report(st.session_state)
            st.session_state.incident_report = report
            if REPORTLAB_AVAILABLE:
                st.session_state.incident_report_pdf = build_incident_report_pdf(report)
                st.session_state.incident_report_filename = (
                    f"{report.get('report_id', 'trustvoice_incident_report')}.pdf"
                )
            else:
                st.session_state.incident_report_pdf = None
                st.warning("PDF generator unavailable. Install reportlab to enable PDF reports.")
        except Exception as exc:
            st.error(f"Report generation failed: {type(exc).__name__}: {exc}")

    rep = st.session_state.get("incident_report")
    if not rep:
        st.caption("Run an analysis, then generate a report from the latest result.")
        return

    factors = rep.get("risk_factors") or {}
    factor_lines = "".join(
        f"<tr><td>{escape(str(k))}</td><td class='num'>{escape(str(v))}</td></tr>"
        for k, v in factors.items()
    ) or "<tr><td colspan='2'>None</td></tr>"
    drivers = "".join(
        f"<li>{escape(str(d))}</li>" for d in (rep.get("decision_drivers") or [])
    ) or "<li>None</li>"
    audio_q = rep.get("audio_quality")
    audio_q_text = audio_q.get("quality", "—") if isinstance(audio_q, dict) else (audio_q or "—")

    render(st, f"""
    <div class="tv-report">
      <div class="tv-card">
        <div class="tv-card-title">Summary</div>
        <table class="tv-table">
          <tr><td>Report ID</td><td>{escape(str(rep.get('report_id', '—')))}</td></tr>
          <tr><td>Generated</td><td>{escape(str(rep.get('generated_at', '—')))}</td></tr>
          <tr><td>Source</td><td>{escape(str(rep.get('source', '—')))}</td></tr>
          <tr><td>Scenario</td><td>{escape(str(rep.get('scenario', '—')))}</td></tr>
        </table>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Risk decision</div>
        <table class="tv-table">
          <tr><td>Trust score</td><td class="num">{escape(str(rep.get('trust_score', '—')))} / 100</td></tr>
          <tr><td>Interaction risk</td><td>{escape(str(rep.get('interaction_risk', '—')))}</td></tr>
          <tr><td>Recommended action</td><td>{escape(str(rep.get('recommended_action', '—')))}</td></tr>
          <tr><td>Handshake</td><td>{'required' if rep.get('handshake_required') else 'not required'}</td></tr>
        </table>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Transcript</div>
        <p>{escape(str(rep.get('transcript') or 'No transcript recorded.'))}</p>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Signal breakdown</div>
        <table class="tv-table">
          <tr><td>Voice authenticity</td><td>{escape(str(rep.get('voice_authenticity', '—')))}</td></tr>
          <tr><td>Identity</td><td>{escape(str(rep.get('identity_status') or '—').replace('_', ' '))}</td></tr>
          <tr><td>Audio quality</td><td>{escape(str(audio_q_text))}</td></tr>
          <tr><td>Model</td><td>{escape(str(rep.get('model') or '—'))}</td></tr>
        </table>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Key indicators</div>
        <table class="tv-table">
          <tr><td>Intent</td><td>{escape(_fmt_intent(rep))}</td></tr>
          <tr><td>Behaviour</td><td>{escape(_fmt_list(rep.get('behaviour_signals')))}</td></tr>
          <tr><td>Context</td><td>{escape(_fmt_list(rep.get('context_signals')))}</td></tr>
          {factor_lines}
        </table>
        <div class="tv-why"><ul>{drivers}</ul></div>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Recommended action</div>
        <p>{escape(str(rep.get('recommended_action') or '—'))}</p>
        <p class="tv-muted">{escape(str(rep.get('action_detail') or ''))}</p>
      </div>

      <div class="tv-card" style="margin-top:12px">
        <div class="tv-card-title">Prototype limitations</div>
        <p class="tv-note">{escape(str(rep.get('prototype_note', '')))}</p>
      </div>
    </div>
    """)

    d1, d2 = st.columns(2)
    with d1:
        if st.session_state.get("incident_report_pdf"):
            st.download_button(
                "Download PDF",
                st.session_state.incident_report_pdf,
                st.session_state.get("incident_report_filename", "trustvoice_incident_report.pdf"),
                "application/pdf",
                use_container_width=True,
            )
    with d2:
        st.download_button(
            "Download JSON",
            json.dumps(rep, indent=2, default=str),
            "trustvoice_incident_report.json",
            "application/json",
            use_container_width=True,
        )

    with st.expander("Technical JSON"):
        st.code(json.dumps(rep, indent=2, default=str), language="json")
