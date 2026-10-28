"""Small HTML fragments. Color is never the only signal."""

import re
from datetime import datetime
from html import escape

from ui.theme import COLORS, status_color


def render(st, html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def meter(value: int, color: str | None = None) -> str:
    width = max(2, min(100, int(value)))
    c = color or COLORS["accent"]
    return f'<div class="tv-bar"><i style="width:{width}%;background:{c}"></i></div>'


def analysis_mode(source: str | None) -> str:
    s = (source or "Idle").upper()
    if s.startswith("DEMO"):
        return "DEMO"
    if s.startswith("LIVE"):
        return "LIVE"
    return "IDLE"


def page_header(title: str, subtitle: str, mode: str) -> str:
    now = datetime.now().strftime("%d %b %Y %H:%M")
    return f"""
    <div class="tv-page">
      <div>
        <h1>{escape(title)}</h1>
        <p>{escape(subtitle)}</p>
      </div>
      <div class="tv-page-meta">
        <div class="tv-status"><span class="tv-dot"></span>Analysis Engine Online</div>
        <div style="margin-top:4px">Mode: {escape(mode)}</div>
        <div class="tv-dim" style="margin-top:4px">Local time {escape(now)}</div>
      </div>
    </div>
    """


def _ring(risk: str | None) -> str:
    band = str(risk or "").upper()
    cls = "idle"
    if band == "LOW":
        cls = "ok"
    elif band in {"ELEVATED", "MEDIUM"}:
        cls = "warn"
    elif band in {"HIGH", "CRITICAL"}:
        cls = "crit"
    return f'<div class="tv-ring {cls}" aria-hidden="true"></div>'


def decision_block(result: dict) -> str:
    score = int(result.get("trust_score") or 0)
    risk = result.get("interaction_risk") or "—"
    action = result.get("action") or "—"
    source = result.get("source") or "—"
    rc = status_color(risk)
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Current decision</div>
      <div class="tv-decision">
        {_ring(risk)}
        <div>
          <div class="tv-value">{score} <span class="tv-muted">/ 100</span></div>
          <div class="tv-decision-risk" style="color:{rc};margin-top:8px">{escape(str(risk))}</div>
          <div class="tv-decision-action">{escape(str(action))}</div>
        </div>
      </div>
      <div class="tv-note">Mode {escape(analysis_mode(str(source)))}. Decision support, not a probability. Voice authenticity is not identity or authorization.</div>
    </div>
    """


def idle_decision() -> str:
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Current decision</div>
      <div class="tv-decision">
        {_ring(None)}
        <div>
          <div class="tv-value tv-muted">—</div>
          <div class="tv-decision-risk" style="margin-top:8px">Awaiting analysis</div>
          <div class="tv-decision-action">Upload audio or type a transcript, then run analysis.</div>
        </div>
      </div>
    </div>
    """


def audio_analysis_card(audio: dict | None, processing: bool = False) -> str:
    audio = audio or {}
    anti = audio.get("anti_spoof") or {}
    quality = audio.get("quality_gate") or {}
    asr = audio.get("asr") or {}
    has_audio = bool(audio.get("duration") is not None or audio.get("file") or anti or asr)
    env = audio.get("envelope")
    wave = waveform(env, animated=processing) if has_audio or env else '<div class="tv-muted">No audio in this session.</div>'
    fname = audio.get("file") or "—"
    fmt = audio.get("format") or "—"
    dur = audio.get("duration")
    dur_s = f"{dur} s" if dur is not None else "—"
    q = quality.get("quality") or "—"
    proc = "Complete" if anti or asr else ("Idle" if not has_audio else "Decoded")
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Audio analysis</div>
      {wave}
      <div class="tv-row"><span>File</span><span>{escape(str(fname))}</span></div>
      <div class="tv-row"><span>Format</span><span>{escape(str(fmt))}</span></div>
      <div class="tv-row"><span>Duration</span><span>{escape(str(dur_s))}</span></div>
      <div class="tv-row"><span>Quality</span><span>{escape(str(q))}</span></div>
      <div class="tv-row"><span>State</span><span>{escape(proc)}</span></div>
    </div>
    """


def signal_rows(factors: dict | None, identity_status: str | None = None, result: dict | None = None) -> str:
    result = result or {}
    intent = (result.get("intent") or {}).get("intent") if result else None
    behaviour = (result.get("behaviour") or {}) if result else {}
    context = (result.get("context") or {}) if result else {}
    voice = result.get("voice_display") or result.get("voice_label")

    specs = [
        ("Voice authenticity", voice.replace("_", " ") if voice else "NOT AVAILABLE", "Voice Authenticity"),
        ("Speaker identity", (identity_status or "NOT_AVAILABLE").replace("_", " "), "Speaker Identity"),
        ("Intent analysis", (intent or "NOT AVAILABLE").replace("_", " "), "Intent Safety"),
        ("Behaviour analysis", str(behaviour.get("behaviour_level") or "NOT AVAILABLE"), "Behaviour Safety"),
        ("Context analysis", str(context.get("context_level") or "NOT AVAILABLE"), "Context Safety"),
    ]
    cells = []
    for title, state, key in specs:
        bar = ""
        if factors and isinstance(factors.get(key), (int, float)):
            val = int(factors[key])
            color = COLORS["accent"] if val >= 70 else (COLORS["amber"] if val >= 40 else COLORS["red"])
            bar = meter(val, color)
            state = f"{escape(str(state))} · {val}"
        else:
            state = escape(str(state))
        cells.append(
            f'<div class="tv-signal"><div class="name">{title}</div>'
            f'<div class="val">{state}</div>{bar}</div>'
        )
    return f'<div class="tv-signals">{"".join(cells)}</div>'


def entity_lines(entities) -> str:
    if not entities:
        return "None"
    return "<br>".join(
        f"{escape(e.get('type','?'))} → {escape(str(e.get('value','')))}" for e in entities
    )


def waveform(envelope, animated: bool = False) -> str:
    bars = envelope or [16, 28, 22, 40, 18, 36, 24]
    html = "".join(f'<i style="height:{int(h)}px"></i>' for h in bars)
    cls = "tv-wave live" if animated else "tv-wave"
    return f'<div class="{cls}">{html}</div>'


def utterances_from_transcript(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _tag_class(tag: str) -> str:
    t = str(tag).lower()
    if any(k in t for k in ("credential", "otp", "threat", "financial", "secret", "block")):
        return "tv-tag crit"
    if any(k in t for k in ("urgency", "authority", "pressure", "anomaly", "sensitive")):
        return "tv-tag warn"
    return "tv-tag"


def conversation_timeline(utterances: list[str], speaker: str = "Caller", tags: list | None = None) -> str:
    if not utterances:
        return '<div class="tv-muted">No conversation yet.</div>'
    tag_html = ""
    if tags:
        tag_html = "".join(
            f'<span class="{_tag_class(t)}">{escape(str(t).replace("_", " "))}</span>'
            for t in tags if t
        )
    rows = []
    last = len(utterances) - 1
    for i, line in enumerate(utterances):
        extra = f'<div>{tag_html}</div>' if tag_html and i == last else "<div></div>"
        rows.append(
            f'<div class="tv-utt"><div class="who">{i+1:02d}</div>'
            f'<div class="said">“{escape(line)}”</div>{extra}</div>'
        )
    return f'<div class="tv-timeline">{"".join(rows)}</div>'


def conversation_intel(transcript: str, source: str, asr: dict | None, result: dict | None) -> str:
    asr = asr or {}
    result = result or {}
    empty = not (transcript or "").strip()
    failed = asr and asr.get("status") not in {None, "success"} and empty
    body = ""
    if failed:
        body = (
            f'<div class="tv-note">Conversation content: unavailable</div>'
            f'<div class="tv-dim">ASR status: {escape(str(asr.get("status") or "—"))} '
            f'{escape(str(asr.get("error") or ""))}</div>'
        )
    else:
        tags = []
        intent = (result.get("intent") or {}).get("intent") if result else None
        if intent and intent not in {"normal_conversation", "unknown", "unavailable", None}:
            tags.append(intent)
        tags.extend(list((result.get("behaviour") or {}).get("signals") or []))
        body = conversation_timeline(utterances_from_transcript(transcript), tags=tags)
    src = escape(source or "NONE")
    note = "ASR-generated transcript is not guaranteed to be accurate." if source == "ASR" else ""
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Conversation intelligence</div>
      <div class="tv-dim" style="margin-bottom:8px">Transcript source: {src}</div>
      {body}
      <div class="tv-note">{escape(note)}</div>
    </div>
    """


def risk_breakdown(result: dict | None) -> str:
    if not result:
        return """
        <div class="tv-card">
          <div class="tv-card-title">Risk breakdown</div>
          <div class="tv-muted">No data available. Run an analysis to see why a decision was reached.</div>
        </div>
        """
    factors = result.get("factor_display") or {}
    rows = []
    for title, key in (
        ("Voice authenticity", "Voice Authenticity"),
        ("Speaker identity", "Speaker Identity"),
        ("Intent", "Intent Safety"),
        ("Behaviour", "Behaviour Safety"),
        ("Context", "Context Safety"),
    ):
        raw = factors.get(key)
        if isinstance(raw, (int, float)):
            val = int(raw)
            color = COLORS["accent"] if val >= 70 else (COLORS["amber"] if val >= 40 else COLORS["red"])
            rows.append(
                f'<div class="tv-row"><span>{title}</span><span>{val}</span></div>{meter(val, color)}'
            )
        else:
            rows.append(f'<div class="tv-row"><span>{title}</span><span>NOT AVAILABLE</span></div>')
    why = why_this_risk(result.get("drivers"))
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Risk breakdown</div>
      {''.join(rows)}
      <div class="tv-section">Why this decision</div>
      {why}
    </div>
    """


def pipeline_block(audio: dict | None, result: dict | None, source: str | None = None) -> str:
    audio = audio or {}
    anti = audio.get("anti_spoof")
    asr = audio.get("asr") or {}
    decoded = audio.get("duration") is not None or audio.get("decode_path") or audio.get("file")
    demo = analysis_mode(source) == "DEMO"

    stages = []
    if demo:
        stages = [
            ("Decode", "Unavailable", "fail"),
            ("AASIST", "Unavailable", "fail"),
            ("ASR", "Unavailable", "fail"),
        ]
    else:
        if audio.get("user_error") and not decoded:
            stages.append(("Decode", "Failed", "fail"))
        elif decoded:
            stages.append(("Decode", "Completed", "done"))
        else:
            stages.append(("Decode", "Queued", ""))
        if anti:
            stages.append(("AASIST", "Completed", "done"))
        elif audio.get("voice_error") or decoded:
            stages.append(("AASIST", "Unavailable", "fail"))
        else:
            stages.append(("AASIST", "Queued", ""))
        ast = asr.get("status")
        if ast == "success":
            stages.append(("ASR", "Completed", "done"))
        elif ast in {"error", "unavailable", "decode_failed", "no_speech", "too_long"}:
            label = "Failed" if ast == "error" else "Unavailable"
            stages.append(("ASR", label, "fail"))
        else:
            stages.append(("ASR", "Queued", ""))
    fused = bool(result)
    for name in ("Intent", "Behaviour", "Context", "Fusion"):
        stages.append((name, "Completed", "done") if fused else (name, "Queued", ""))

    cells = "".join(
        f'<div class="tv-stage {cls}"><div class="nm">{escape(n)}</div><div class="st">{escape(st)}</div></div>'
        for n, st, cls in stages
    )
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Analysis pipeline</div>
      <div class="tv-pipe">{cells}</div>
      <div class="tv-note">Stages reflect this session’s completed work. Demo scenarios skip live AASIST/ASR.</div>
    </div>
    """


def why_this_risk(drivers: list | None) -> str:
    items = drivers or ["No analysis yet"]
    lis = "".join(f"<li>{escape(str(d))}</li>" for d in items)
    return f'<div class="tv-why"><ul>{lis}</ul></div>'


def handshake_block(detail: str) -> str:
    return f"""
    <div class="tv-handshake">
      <h3>Trust handshake required</h3>
      <div class="tv-label" style="margin-top:6px">Independent verification is recommended before proceeding.</div>
      <p class="tv-muted" style="margin:6px 0">Caller identity alone is not sufficient authorization.</p>
      <p class="tv-note">{escape(detail or "")} This handshake is simulated in the prototype — it does not contact a phone, bank, or device service. Use Confirm / Deny / No response below to complete the simulated check.</p>
    </div>
    """


def score_trail(scores: list[int]) -> str:
    if not scores:
        return ""
    joined = " <span>→</span> ".join(str(int(s)) for s in scores)
    return (
        f'<div class="tv-section">Illustrative scenario progression</div>'
        f'<div class="tv-trail">{joined}</div>'
        f'<div class="tv-note">Not a measured model accuracy or probability.</div>'
    )


def scenario_choice(letter: str, title: str, subtitle: str, active: bool) -> str:
    cls = "tv-choice active" if active else "tv-choice"
    return f"""
    <div class="{cls}">
      <div class="id">[{escape(letter)}]</div>
      <div class="title">{escape(title)}</div>
      <div class="sub">{escape(subtitle)}</div>
    </div>
    """


def recommended_action_card(result: dict | None) -> str:
    if not result:
        return """
        <div class="tv-card">
          <div class="tv-card-title">Recommended action</div>
          <div class="tv-muted">No data available.</div>
        </div>
        """
    action = result.get("action") or "—"
    detail = result.get("action_detail") or ""
    return f"""
    <div class="tv-card">
      <div class="tv-card-title">Recommended action</div>
      <div class="tv-label">{escape(str(action))}</div>
      <div class="tv-note">{escape(str(detail))}</div>
    </div>
    """
