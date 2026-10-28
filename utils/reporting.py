"""Incident report JSON + PDF. Prototype estimates are not labelled as probabilities."""

from __future__ import annotations

import io
from datetime import datetime
from html import escape

from models.intent import describe_intent
from risk.config import FUSION_WEIGHTS

try:
    from reportlab.lib import colors as pdf_colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def build_incident_report(session: dict) -> dict:
    result = session.get("last_result") or {}
    return {
        "report_id": f"TV-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": session.get("analysis_source", result.get("source", "LIVE")),
        "scenario": session.get("scenario", "Conversation analysis"),
        "trust_score": result.get("trust_score", session.get("score")),
        "interaction_risk": result.get("interaction_risk"),
        "voice_authenticity": result.get("voice_display"),
        "identity_status": result.get("identity_status"),
        "intent": result.get("intent"),
        "entities": result.get("entities"),
        "behaviour_signals": result.get("behaviour_signals"),
        "context_signals": result.get("context_signals"),
        "decision_drivers": result.get("drivers"),
        "recommended_action": result.get("action"),
        "action_detail": result.get("action_detail"),
        "handshake_required": result.get("handshake_required"),
        "handshake": session.get("handshake_result"),
        "audio_quality": (session.get("last_analysis") or {}).get("quality_gate"),
        "model": ((session.get("last_analysis") or {}).get("anti_spoof") or {}).get("model"),
        "threshold_information": {
            "threshold": session.get("bona_threshold"),
            "decision_band": session.get("decision_band"),
            "source": session.get("threshold_source"),
        },
        "evaluation": session.get("accuracy_eval") if (session.get("accuracy_eval") or {}).get("n") else None,
        "risk_factors": result.get("factor_display") or session.get("factors"),
        "fusion_weights": FUSION_WEIGHTS,
        "transcript": result.get("transcript") or session.get("transcript"),
        "last_analysis": session.get("last_analysis"),
        "prototype_note": (
            "Dynamic Trust Score is a prototype decision-support value, not a probability. "
            "Countermeasure scores are uncalibrated unless the evaluation lab has fitted a threshold. "
            "This report is not a certified fraud verdict."
        ),
    }


def build_incident_report_pdf(rep: dict) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("PDF generation requires reportlab. Install it with: pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"TRUSTVOICE AI Incident Report {rep.get('report_id', '')}",
        author="TRUSTVOICE AI",
    )
    ink = pdf_colors.HexColor("#12151a")
    muted = pdf_colors.HexColor("#5c6570")
    line = pdf_colors.HexColor("#d0d5db")
    wash = pdf_colors.HexColor("#f3f5f7")
    accent = pdf_colors.HexColor("#2f6fed")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TVTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                                 fontSize=16, leading=20, textColor=ink, spaceAfter=4)
    sub_style = ParagraphStyle("TVSub", parent=styles["Normal"], fontSize=8.5, leading=12,
                               textColor=muted, spaceAfter=10)
    section_style = ParagraphStyle("TVSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
                                   fontSize=10, leading=13, textColor=ink, spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle("TVBody", parent=styles["BodyText"], fontSize=8.7, leading=13,
                                textColor=ink, spaceAfter=5)
    small_style = ParagraphStyle("TVSmall", parent=styles["BodyText"], fontSize=7.5, leading=10.5,
                                 textColor=muted)
    white_small = ParagraphStyle("TVWhiteSmall", parent=small_style, textColor=pdf_colors.white)
    white_body = ParagraphStyle("TVWhiteBody", parent=body_style, textColor=pdf_colors.white)
    center_small = ParagraphStyle("TVCenterSmall", parent=small_style, alignment=TA_CENTER)

    def safe(value):
        return escape(str(value if value is not None else "—"))

    score = int(rep.get("trust_score", 0) or 0)
    story = []
    header = Table([[
        Paragraph("TRUSTVOICE AI", ParagraphStyle("Brand", parent=title_style,
                                                  textColor=pdf_colors.white, fontSize=15)),
        Paragraph("CONVERSATION SECURITY REPORT", ParagraphStyle("HeaderRight", parent=white_small,
                                                                 alignment=2, fontSize=8.5)),
    ]], colWidths=[105 * mm, 70 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ink),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LINEBELOW", (0, -1), (-1, -1), 2, accent),
    ]))
    story += [header, Spacer(1, 7)]
    story.append(Paragraph(
        f"Report ID: <b>{safe(rep.get('report_id'))}</b> &nbsp;&nbsp; Generated: {safe(rep.get('generated_at'))} "
        f"&nbsp;&nbsp; Source: {safe(rep.get('source'))}",
        sub_style,
    ))

    summary = Table([
        [Paragraph("TRUST SCORE", center_small), Paragraph("INTERACTION RISK", center_small),
         Paragraph("VOICE AUTHENTICITY", center_small), Paragraph("ACTION", center_small)],
        [Paragraph(f"{score} / 100", ParagraphStyle("ss", parent=body_style, alignment=TA_CENTER,
                                                    fontSize=14, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("interaction_risk")), ParagraphStyle("sr", parent=body_style,
                                                                     alignment=TA_CENTER, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("voice_authenticity")), ParagraphStyle("sv", parent=body_style,
                                                                       alignment=TA_CENTER, fontName="Helvetica-Bold")),
         Paragraph(safe(rep.get("recommended_action")), ParagraphStyle("sa", parent=body_style,
                                                                       alignment=TA_CENTER, fontSize=8))],
    ], colWidths=[43 * mm, 43 * mm, 44 * mm, 44 * mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), wash),
        ("BOX", (0, 0), (-1, -1), 0.6, line),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [summary, Spacer(1, 6)]

    story.append(Paragraph("COMPONENT SCORES", section_style))
    factor_rows = [["Component", "Weight", "Score", "Notes"]]
    factors = rep.get("risk_factors") or {}
    labels = [
        ("Voice Authenticity", "voice_authenticity"),
        ("Speaker Identity", "speaker_identity"),
        ("Intent Safety", "intent_safety"),
        ("Behaviour Safety", "behaviour_safety"),
        ("Context Safety", "context_safety"),
    ]
    for label, key in labels:
        value = factors.get(label, factors.get(key, "—"))
        factor_rows.append([label, f"{FUSION_WEIGHTS.get(key, 0):.0%}", str(value), "Prototype weight"])
    table = Table(factor_rows, colWidths=[55 * mm, 25 * mm, 30 * mm, 64 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ink),
        ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, line),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, wash]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph("IDENTITY / INTENT / ENTITIES", section_style))
    story.append(Paragraph(f"Identity status: <b>{safe(rep.get('identity_status'))}</b>", body_style))
    story.append(Paragraph(f"Intent: {safe(describe_intent(rep.get('intent')))}", body_style))
    ents = rep.get("entities") or []
    if ents:
        story.append(Paragraph("Entities: " + ", ".join(
            f"{e.get('type')}={e.get('value')}" for e in ents
        ), body_style))
    else:
        story.append(Paragraph("Entities: none extracted", body_style))
    story.append(Paragraph(
        "Behaviour signals: " + (", ".join(rep.get("behaviour_signals") or []) or "none"),
        body_style,
    ))
    story.append(Paragraph(
        "Context signals: " + (", ".join(rep.get("context_signals") or []) or "none"),
        body_style,
    ))

    if rep.get("decision_drivers"):
        story.append(Paragraph("DECISION DRIVERS", section_style))
        for item in rep["decision_drivers"]:
            story.append(Paragraph(f"&bull; {safe(item)}", body_style))

    story.append(Paragraph("RECOMMENDED ACTION", section_style))
    action_table = Table([[Paragraph(
        f"<b>{safe(rep.get('recommended_action'))}</b><br/>{safe(rep.get('action_detail'))}",
        ParagraphStyle("Action", parent=white_body, fontSize=9, leading=13),
    )]], colWidths=[174 * mm])
    action_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ink),
        ("BOX", (0, 0), (-1, -1), 1, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(action_table)

    hs = rep.get("handshake")
    story.append(Paragraph("TRUST HANDSHAKE", section_style))
    if rep.get("handshake_required"):
        story.append(Paragraph(
            "Handshake required: voice identity alone is not sufficient authorization.",
            body_style,
        ))
    if hs:
        status = safe(hs.get("status")) if isinstance(hs, dict) else safe(hs)
        msg = safe(hs.get("message", "")) if isinstance(hs, dict) else ""
        story.append(Paragraph(f"Status: <b>{status}</b> — {msg} (demo / simulated unless integrated).", body_style))
    else:
        story.append(Paragraph("No handshake recorded for this session.", body_style))

    if rep.get("transcript"):
        story.append(Paragraph("TRANSCRIPT", section_style))
        t = Table([[Paragraph(safe(rep["transcript"]), white_body)]], colWidths=[174 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ink),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(t)

    story.append(Paragraph("AUDIO / MODEL", section_style))
    technical = [["Field", "Value"], ["Model", safe(rep.get("model"))]]
    thr = rep.get("threshold_information") or {}
    technical.append([
        "Threshold",
        f"{thr.get('threshold')} ± {thr.get('decision_band')} · {thr.get('source')}",
    ])
    quality = rep.get("audio_quality") or {}
    if quality:
        technical.append(["Audio quality", safe(quality.get("quality"))])
        if quality.get("issues"):
            technical.append(["Quality issues", safe("; ".join(quality["issues"]))])
    last = rep.get("last_analysis") if isinstance(rep.get("last_analysis"), dict) else None
    if last:
        for key in ["file", "file_hash", "duration", "sample_rate", "analysis_mode"]:
            if last.get(key) is not None:
                technical.append([key.replace("_", " ").title(), safe(last.get(key))])
        anti = last.get("anti_spoof") or {}
        for key in ["verdict", "authenticity_score", "cm_score", "windows_used",
                    "engine_stable", "threshold_source"]:
            if key in anti:
                technical.append([key.replace("_", " ").title(), safe(anti.get(key))])
    tech_table = Table(technical, colWidths=[58 * mm, 116 * mm], repeatRows=1)
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ink),
        ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, line),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [pdf_colors.white, wash]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tech_table)

    ev = rep.get("evaluation")
    if ev and ev.get("n"):
        story.append(Paragraph("EVALUATION (this session's labelled set only)", section_style))
        story.append(Paragraph(
            f"n={ev.get('n')} · accuracy={ev.get('accuracy')} · FAR={ev.get('far')} · "
            f"FRR={ev.get('frr')} · EER={ev.get('eer')}",
            body_style,
        ))

    story.append(Spacer(1, 8))
    story.append(Paragraph(safe(rep.get("prototype_note")), small_style))
    story.append(Paragraph(
        "Prototype processing is local to the application environment. Voice/audio data should "
        "be treated as sensitive and retained only as long as necessary. No compliance certification "
        "is claimed.",
        small_style,
    ))

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.6)
        canvas.line(15 * mm, 10 * mm, 195 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(15 * mm, 6 * mm, "TRUSTVOICE AI · prototype")
        canvas.drawRightString(195 * mm, 6 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
