"""Trusted Speakers — registered voice identity gallery."""

from __future__ import annotations

import time
from html import escape

import streamlit as st

from models.speaker_registry import (
    MAX_SAMPLES,
    MIN_SAMPLES,
    SAMPLE_FORMATS,
    create_profile,
    delete_profile,
    enroll_profile,
    get_profile,
    list_profiles,
    re_enroll_profile,
    validate_sample,
)
from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────

def _enrolled_badge(enrolled: bool) -> str:
    if enrolled:
        return '<span class="tv-badge tv-badge-ok">● Active</span>'
    return '<span class="tv-badge tv-badge-warn">● Review</span>'


def _ts_str(ts: float | None) -> str:
    if not ts:
        return "—"
    t = time.localtime(ts)
    # %-d is Linux-only; strip leading zero manually for Windows compatibility
    return time.strftime("%d %b %Y", t).lstrip("0")


def _status_str(profile: dict) -> str:
    enrolled = profile.get("enrolled", False)
    samples = len(profile.get("samples") or [])
    if not enrolled:
        if samples == 0:
            return "No samples"
        return "Review needed"
    return "Enrolled"


# ── Profile detail panel ───────────────────────────────────────────────────

def _render_profile_detail(profile_id: str):
    profile = get_profile(profile_id)
    if not profile:
        render("""<div class="tv-card"><div class="tv-muted">Profile not found.</div></div>""")
        return

    name = profile.get("name", "—")
    role = profile.get("role", "—")
    enrolled = profile.get("enrolled", False)
    samples = profile.get("samples") or []
    enrolled_at = profile.get("enrolled_at")
    badge = _enrolled_badge(enrolled)
    sample_count = len(samples)

    render(f"""
    <div class="tv-card">
      <div class="tv-card-title">Speaker profile</div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <div class="tv-spk-avatar" style="width:38px;height:38px;font-size:16px">👤</div>
        <div>
          <div style="font-size:15px;font-weight:700;color:var(--tv-text)">{escape(name)}</div>
          <div style="font-size:12.5px;color:var(--tv-muted)">{escape(role)}</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">
        <div>
          <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Enrollment</div>
          <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{'Enrolled' if enrolled else 'Not enrolled'}</div>
        </div>
        <div>
          <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Voice samples</div>
          <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{sample_count} sample{'s' if sample_count != 1 else ''}</div>
        </div>
        <div>
          <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Identity evidence</div>
          <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{'Available' if enrolled else 'Pending'}</div>
        </div>
        <div>
          <div style="font-size:11.5px;color:var(--tv-muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">Last updated</div>
          <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">{_ts_str(enrolled_at or profile.get('created_at'))}</div>
        </div>
      </div>
      <div style="padding:10px;background:var(--tv-surface);border-radius:6px;border:1px solid var(--tv-border);
        font-size:12px;color:var(--tv-muted);line-height:1.55;margin-bottom:12px">
        Similarity supports identity assessment. It does not independently prove who is speaking.
      </div>
    </div>
    """)

    # Action buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⊕ Add sample", use_container_width=True, key=f"spk_add_{profile_id}"):
            st.session_state.speakers_view = "enroll"
            st.rerun()
    with c2:
        if st.button("↺ Re-enroll", use_container_width=True, key=f"spk_reenroll_{profile_id}"):
            re_enroll_profile(profile_id)
            st.success("Enrollment cleared. Upload new samples to re-enroll.")
            st.rerun()

    if st.button("🗑 Delete speaker", use_container_width=True, key=f"spk_delete_{profile_id}",
                 type="secondary"):
        st.session_state.speakers_confirm_delete = profile_id
        st.rerun()

    # Confirm delete
    if st.session_state.get("speakers_confirm_delete") == profile_id:
        st.warning(f"Delete **{name}**? This cannot be undone.")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("Confirm delete", use_container_width=True, key="spk_del_conf", type="primary"):
                delete_profile(profile_id)
                st.session_state.speakers_selected_id = None
                st.session_state.speakers_confirm_delete = None
                st.success("Profile deleted.")
                st.rerun()
        with dc2:
            if st.button("Cancel", use_container_width=True, key="spk_del_cancel"):
                st.session_state.speakers_confirm_delete = None
                st.rerun()

    # Sample details (if enrolled)
    if samples:
        render("""<div class="tv-card" style="margin-top:0">""")
        render("""<div class="tv-card-title">Voice samples</div>""")
        rows = ""
        for s in samples:
            dur = s.get("duration")
            dur_s = f"{dur:.1f} s" if dur is not None else "—"
            q = s.get("quality", "—")
            rows += f"""
            <tr>
              <td style="font-weight:600">{s.get('index', '—')}</td>
              <td>{escape(str(s.get('filename', '—')))}</td>
              <td class="num">{escape(dur_s)}</td>
              <td>{escape(q)}</td>
            </tr>"""
        render(f"""
        <table class="tv-table">
          <tr><th>#</th><th>File</th><th class="num">Duration</th><th>Quality</th></tr>
          {rows}
        </table>
        """)
        render("""</div>""")


# ── Enrollment form ────────────────────────────────────────────────────────

def _render_enrollment_form(profile_id: str):
    profile = get_profile(profile_id)
    if not profile:
        st.error("Profile not found.")
        return

    render(f"""
    <div class="tv-card">
      <div class="tv-card-title">Voice enrollment — {escape(profile.get('name', ''))}</div>
      <div class="tv-muted" style="margin-bottom:12px">
        Upload <strong>{MIN_SAMPLES}–{MAX_SAMPLES} voice samples</strong> of at least 1.5 s each.
        Accepted: WAV · MP3 · M4A · FLAC · OGG · AAC
      </div>
    </div>
    """)

    uploaded_files = st.file_uploader(
        f"Upload {MIN_SAMPLES}–{MAX_SAMPLES} voice samples",
        type=SAMPLE_FORMATS,
        accept_multiple_files=True,
        key=f"enroll_upload_{profile_id}",
    )

    if not uploaded_files:
        st.caption("No files selected yet.")
    else:
        count = min(len(uploaded_files), MAX_SAMPLES)
        if len(uploaded_files) > MAX_SAMPLES:
            st.warning(f"Only first {MAX_SAMPLES} files will be used.")
        if count < MIN_SAMPLES:
            st.warning(f"Please upload at least {MIN_SAMPLES} samples. Got {count}.")

        # Validate each sample
        validation_results = []
        render("""<div class="tv-card"><div class="tv-card-title">Sample validation</div>""")
        for i, f in enumerate(uploaded_files[:MAX_SAMPLES]):
            raw = f.getvalue()
            result = validate_sample(raw, f.name)
            result["filename"] = f.name
            validation_results.append(result)

            ok = result.get("ok", False)
            dur = result.get("duration")
            dur_s = f"{dur:.1f} s" if dur is not None else "—"
            badge = f'<span class="tv-badge tv-badge-ok">✓ OK · {escape(dur_s)}</span>' if ok else \
                    f'<span class="tv-badge tv-badge-crit">✕ Failed</span>'
            render(f"""
            <div class="tv-evidence-row">
              <span class="tv-evidence-label">Sample {i+1} — {escape(f.name)}</span>
              <span>{badge}</span>
            </div>""")

            if not ok:
                for err in result.get("errors", []):
                    st.error(f"Sample {i+1}: {err}")
            elif result.get("warnings"):
                for w in result["warnings"]:
                    st.caption(f"⚠ Sample {i+1}: {w}")
        render("""</div>""")

        valid_count = sum(1 for r in validation_results if r.get("ok"))
        st.caption(f"{valid_count} of {count} sample(s) passed validation.")

        if valid_count >= MIN_SAMPLES:
            if st.button(
                f"Enroll speaker ({valid_count} samples)",
                use_container_width=True,
                type="primary",
                key=f"enroll_btn_{profile_id}",
            ):
                with st.spinner("Generating voice embedding…"):
                    try:
                        enroll_profile(
                            profile_id, validation_results,
                            model_key=st.session_state.get("model_choice", "aasist"),
                        )
                        st.success(f"✓ {profile.get('name')} enrolled with {valid_count} samples.")
                        st.session_state.speakers_view = "gallery"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Enrollment failed: {exc}")
        else:
            st.error(f"Need at least {MIN_SAMPLES} valid samples. Fix errors above.")

    if st.button("← Back", use_container_width=True, key="enroll_back"):
        st.session_state.speakers_view = "gallery"
        st.rerun()


# ── Create-profile form ────────────────────────────────────────────────────

def _render_create_form():
    render("""
    <div class="tv-page">
      <div>
        <h1>TRUSTED SPEAKERS</h1>
        <p>Register a new voice identity.</p>
      </div>
    </div>
    """)
    render("""<div class="tv-card">""")
    render("""<div class="tv-card-title">New speaker profile</div>""")
    with st.form("create_speaker_form", clear_on_submit=True):
        name = st.text_input("Full name *", placeholder="e.g. Priya Sharma")
        role = st.text_input("Role / department", placeholder="e.g. Branch Manager")
        submitted = st.form_submit_button("Create profile", use_container_width=True)
    render("""</div>""")

    if submitted:
        if not name.strip():
            st.error("Name is required.")
        else:
            try:
                profile = create_profile(name, role)
                st.session_state.speakers_selected_id = profile["id"]
                st.session_state.speakers_view = "enroll"
                st.success(f"Profile created for **{profile['name']}**. Upload voice samples below.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if st.button("← Back to gallery", use_container_width=True, key="create_back"):
        st.session_state.speakers_view = "gallery"
        st.rerun()


# ── Main gallery ───────────────────────────────────────────────────────────

def render_speakers():
    # Init state
    for key, val in [
        ("speakers_view", "gallery"),
        ("speakers_selected_id", None),
        ("speakers_confirm_delete", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = val

    view = st.session_state.get("speakers_view", "gallery")

    if view == "create":
        _render_create_form()
        return

    if view == "enroll" and st.session_state.get("speakers_selected_id"):
        render("""
        <div class="tv-page">
          <div><h1>TRUSTED SPEAKERS</h1><p>Voice enrollment.</p></div>
        </div>""")
        _render_enrollment_form(st.session_state.speakers_selected_id)
        return

    # Gallery view
    render("""
    <div class="tv-page" style="margin-bottom:16px">
      <div>
        <h1>TRUSTED SPEAKERS</h1>
        <p>Registered voice identities used as supporting identity evidence.</p>
      </div>
    </div>
    """)

    # Register button at top right
    col_gap, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("+ Register speaker", use_container_width=True, type="primary", key="spk_register"):
            st.session_state.speakers_view = "create"
            st.rerun()

    profiles = list_profiles()
    col_table, col_profile = st.columns([1.6, 1], gap="medium")

    with col_table:
        render(f"""
        <div class="tv-card" style="padding:0">
          <div style="display:flex;justify-content:space-between;align-items:center;
            padding:14px 16px;border-bottom:1px solid var(--tv-border)">
            <div style="font-size:14px;font-weight:600;color:var(--tv-text)">Speaker registry</div>
            <div style="font-size:12px;color:var(--tv-dim)">{len(profiles)} registered</div>
          </div>
        """)

        if not profiles:
            render("""
            <div style="padding:32px 16px;text-align:center">
              <div style="font-size:14px;color:var(--tv-muted)">No speakers registered yet.</div>
              <div style="font-size:12.5px;color:var(--tv-dim);margin-top:4px">
                Click "+ Register speaker" to add the first voice identity.
              </div>
            </div>""")
        else:
            render("""
            <table class="tv-table">
              <tr>
                <th></th>
                <th>Name</th>
                <th>Role</th>
                <th>Enrollment</th>
                <th>Voice samples</th>
                <th>Status</th>
                <th>Last updated</th>
              </tr>
            """)
            for p in profiles:
                full = get_profile(p["id"])
                enrolled = p.get("enrolled", False)
                badge = _enrolled_badge(enrolled)
                status = _status_str(full or p)
                ts = _ts_str(p.get("enrolled_at") or p.get("created_at"))
                sample_count = p.get("sample_count", 0)
                selected = st.session_state.speakers_selected_id == p["id"]
                row_bg = "#EFF6FF" if selected else "transparent"

                render(f"""
                <tr style="background:{row_bg}">
                  <td style="width:32px;padding:8px 6px 8px 16px">
                    <div class="tv-spk-avatar">👤</div>
                  </td>
                  <td style="font-weight:600">{escape(p['name'])}</td>
                  <td style="color:var(--tv-muted)">{escape(p.get('role') or '—')}</td>
                  <td>{'Enrolled' if enrolled else 'Not enrolled'}</td>
                  <td>{sample_count} sample{'s' if sample_count != 1 else ''}</td>
                  <td>{badge}</td>
                  <td style="color:var(--tv-dim)">{escape(ts)}</td>
                </tr>
                """)
                if st.button("", key=f"spk_sel_{p['id']}", help=f"View {p['name']}"):
                    st.session_state.speakers_selected_id = p["id"]
                    st.rerun()

            render("""</table>""")
        render("""</div>""")  # close card

    with col_profile:
        sel_id = st.session_state.get("speakers_selected_id")
        if sel_id and any(p["id"] == sel_id for p in profiles):
            _render_profile_detail(sel_id)
        else:
            render("""
            <div class="tv-card" style="text-align:center;padding:40px 20px">
              <div style="font-size:24px;margin-bottom:10px">👤</div>
              <div style="font-size:14px;font-weight:500;color:var(--tv-text);margin-bottom:4px">
                Select a speaker
              </div>
              <div style="font-size:13px;color:var(--tv-muted)">
                Click a row to view enrollment details and manage voice samples.
              </div>
            </div>
            """)

    render("""<div class="tv-footer">TRUSTVOICE AI · voice profiles processed locally · not a certified identity system</div>""")
