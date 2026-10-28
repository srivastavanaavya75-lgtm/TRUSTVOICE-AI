"""Live Monitor — prototype monitoring page."""

from __future__ import annotations

from html import escape

import streamlit as st

from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def render_live_monitor():
    render("""
    <div class="tv-page" style="align-items:center;border-bottom:0;padding-bottom:0">
      <div style="display:flex;align-items:center;gap:12px">
        <h1 style="margin:0">LIVE MONITOR</h1>
        <span class="tv-badge tv-badge-demo" style="font-size:11.5px">● Prototype</span>
      </div>
    </div>
    <p style="color:var(--tv-muted);font-size:13.5px;margin:0 0 20px 0">Visual foundation for authorized live audio-stream analysis.</p>
    """)

    col_btn, _ = st.columns([1.5, 8])
    with col_btn:
        if st.button("Start simulation", icon=":material/play_arrow:", type="primary", use_container_width=True):
            st.info("Simulation not active in this demo version.")

    st.warning("This prototype represents controlled live audio simulation. It does not intercept ordinary cellular calls or connect to cellular networks.", icon="⚠️")

    col1, col2 = st.columns([1.8, 1], gap="medium")

    with col1:
        render("""
        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Live audio</span>
            <span class="tv-section-head-meta">Awaiting simulation</span>
          </div>
          
          <div style="background:#F1F5F9;border-radius:8px;padding:24px;text-align:center;margin:12px 0 24px;color:var(--tv-dim);display:flex;justify-content:center;align-items:center;height:80px;font-family:monospace;font-size:24px;letter-spacing:2px;font-weight:700;color:#2563D6;opacity:0.6">
            ||||||||||||||||||||||||||||||||||||||||||
          </div>
          
          <div style="display:flex;justify-content:space-between;border-top:1px solid var(--tv-border);padding-top:16px">
            <div>
              <div style="font-size:12px;color:var(--tv-muted);font-weight:600;margin-bottom:4px">Current speaker</div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Not available</div>
            </div>
            <div>
              <div style="font-size:12px;color:var(--tv-muted);font-weight:600;margin-bottom:4px">Voice authenticity</div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Not available</div>
            </div>
            <div>
              <div style="font-size:12px;color:var(--tv-muted);font-weight:600;margin-bottom:4px">Current risk</div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Not available</div>
            </div>
          </div>
        </div>

        <div class="tv-card">
          <div class="tv-section-head">
            <span class="tv-section-head-title">Transcript stream</span>
          </div>
          <div style="height:120px;display:flex;align-items:center;justify-content:center;color:var(--tv-dim);font-size:13.5px">
            Transcript will appear when the simulation starts.
          </div>
        </div>
        """)

    with col2:
        render("""
        <div class="tv-card" style="padding:0">
          <div style="padding:16px;border-bottom:1px solid var(--tv-border)">
            <div class="tv-section-head-title">Current signals</div>
          </div>
          
          <div class="tv-evidence-row" style="padding:12px 16px">
            <span class="tv-evidence-label">Voice authenticity</span>
            <span class="tv-badge tv-badge-gray" style="font-size:11px">● Unavailable</span>
          </div>
          <div class="tv-evidence-row" style="padding:12px 16px">
            <span class="tv-evidence-label">Speaker identity</span>
            <span class="tv-badge tv-badge-gray" style="font-size:11px">● Unavailable</span>
          </div>
          <div class="tv-evidence-row" style="padding:12px 16px">
            <span class="tv-evidence-label">Intent</span>
            <span class="tv-badge tv-badge-gray" style="font-size:11px">● Unavailable</span>
          </div>
          <div class="tv-evidence-row" style="padding:12px 16px">
            <span class="tv-evidence-label">Behaviour</span>
            <span class="tv-badge tv-badge-gray" style="font-size:11px">● Unavailable</span>
          </div>
          <div class="tv-evidence-row" style="padding:12px 16px;border-bottom:0">
            <span class="tv-evidence-label">Context</span>
            <span class="tv-badge tv-badge-gray" style="font-size:11px">● Unavailable</span>
          </div>
        </div>
        
        <div class="tv-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
            <div style="width:36px;height:36px;background:#EFF6FF;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#2563D6">
              <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
            </div>
            <span class="tv-badge tv-badge-crit" style="background:#FEF2F2;color:#EF4444;border-color:#FEE2E2;font-size:11px">● Required</span>
          </div>
          <div style="font-size:14px;font-weight:600;color:var(--tv-text);margin-bottom:8px">Trust Handshake</div>
          <div style="font-size:13.5px;color:#475569;line-height:1.5">
            Independent identity verification recommended.<br><br>
            <span style="color:var(--tv-dim);font-size:13px">High impersonation risk detected. Do not authenticate speaker through a separate trusted channel before proceeding.</span>
          </div>
        </div>
        """)

        if st.button("→ Go to Analyze Audio", use_container_width=True, type="primary", key="lm_goto_analyze"):
            st.session_state.ui_nav = "Analyze Audio"
            st.rerun()

    render("""<div class="tv-footer">TRUSTVOICE AI · does not intercept cellular calls · prototype only</div>""")
