"""Model evaluation lab. Metrics appear only for labelled user samples."""

from datetime import datetime

import streamlit as st

from models.antispoof import MODEL_REGISTRY
from ui.components import render
from ui.console import render_topbar
from utils.evaluation import evaluate_labeled_voice_set


def render_evaluation():
    render_topbar("Evaluation Lab")
    c1, c2 = st.columns([1, 1.2], gap="medium")
    with c1:
        render(st, """
        <div class="tv-card">
          <div class="tv-card-title">Label requirements</div>
          <div class="tv-muted">Filename prefixes REAL_ / SPOOF_ (also BONAFIDE_ / FAKE_) label samples.</div>
          <div class="tv-note">No metrics are shown until labelled files are actually evaluated. Figures describe only the files you uploaded, not a published accuracy claim.</div>
        </div>
        """)
        eval_files = st.file_uploader(
            "Dataset upload",
            type=["wav", "mp3", "m4a", "ogg", "flac", "mp4", "webm", "mov", "mkv", "avi"],
            accept_multiple_files=True,
            key="evaluation_dataset",
        )
        if st.button("Run labelled evaluation", use_container_width=True):
            if not eval_files:
                st.warning("Upload labelled REAL_ and SPOOF_ files first.")
            else:
                with st.spinner("Evaluating labelled audio…"):
                    try:
                        st.session_state.accuracy_eval = evaluate_labeled_voice_set(
                            eval_files,
                            threshold=float(st.session_state.bona_threshold),
                            model_key=st.session_state.model_choice,
                        )
                    except Exception as exc:
                        st.session_state.accuracy_eval = {"error": f"{type(exc).__name__}: {exc}"}

    ev = st.session_state.get("accuracy_eval")
    with c2:
        if not ev:
            render(st, """
            <div class="tv-card">
              <div class="tv-card-title">Results</div>
              <div class="tv-muted">No evaluation has been run in this session.</div>
              <div class="tv-note">Upload labelled files and run evaluation to see metrics.</div>
            </div>
            """)
            return
        if ev.get("error"):
            st.error(ev["error"])
            return
        if not ev.get("n"):
            st.warning("No valid labelled samples found. Use REAL_… and SPOOF_… filenames.")
            return

        far, frr, eer = ev.get("far"), ev.get("frr"), ev.get("eer")
        render(st, f"""
        <div class="tv-card">
          <div class="tv-card-title">Metrics on this labelled set</div>
          <table class="tv-table">
            <tr><th>Metric</th><th class="num">Value</th></tr>
            <tr><td>Accuracy</td><td class="num">{ev['accuracy']*100:.1f}%</td></tr>
            <tr><td>Precision</td><td class="num">{ev['precision']*100:.1f}%</td></tr>
            <tr><td>Recall</td><td class="num">{ev['recall']*100:.1f}%</td></tr>
            <tr><td>F1</td><td class="num">{ev['f1']*100:.1f}%</td></tr>
            <tr><td>FAR (spoof accepted as authentic)</td><td class="num">{'n/a' if far is None else f'{far*100:.1f}%'}</td></tr>
            <tr><td>FRR (authentic rejected as spoof)</td><td class="num">{'n/a' if frr is None else f'{frr*100:.1f}%'}</td></tr>
            <tr><td>EER</td><td class="num">{'n/a' if eer is None else f'{eer*100:.2f}%'}</td></tr>
          </table>
        </div>
        """)

        cm = ev.get("confusion") or {}
        render(st, f"""
        <div class="tv-card" style="margin-top:12px">
          <div class="tv-card-title">Confusion matrix</div>
          <table class="tv-table">
            <tr><th></th><th class="num">Pred authentic</th><th class="num">Pred spoof</th></tr>
            <tr><td>Truth authentic</td><td class="num">{cm.get('tn', 0)}</td><td class="num">{cm.get('fp', 0)}</td></tr>
            <tr><td>Truth spoof</td><td class="num">{cm.get('fn', 0)}</td><td class="num">{cm.get('tp', 0)}</td></tr>
          </table>
          <div class="tv-note">
            Samples: {ev['n']} valid ({ev.get('n_real', 0)} real, {ev.get('n_spoof', 0)} spoof) ·
            False positives: {ev.get('fp', 0)} · False negatives: {ev.get('fn', 0)}
          </div>
        </div>
        """)

    if ev.get("false_positives"):
        st.write("False positives (authentic → spoof):", ev["false_positives"])
    if ev.get("false_negatives"):
        st.write("False negatives (spoof → authentic):", ev["false_negatives"])

    n_real, n_spoof = ev.get("n_real", 0), ev.get("n_spoof", 0)
    render(st, f"""
    <div class="tv-card" style="margin-top:12px">
      <div class="tv-card-title">Threshold</div>
      <table class="tv-table">
        <tr><td>Current threshold</td><td class="num">{st.session_state.bona_threshold:.3f}</td></tr>
        <tr><td>Decision band</td><td class="num">±{st.session_state.decision_band:.3f}</td></tr>
        <tr><td>Source</td><td>{st.session_state.threshold_source}</td></tr>
        <tr><td>Active model</td><td>{MODEL_REGISTRY[st.session_state.model_choice]['label']}</td></tr>
      </table>
    </div>
    """)

    if ev.get("eer") is not None and ev.get("suggested_threshold") is not None:
        st.info(
            f"EER on this set: {ev['eer']*100:.2f}%. "
            f"Suggested operating threshold from these files: {ev['suggested_threshold']:.3f}."
        )
        if st.button("Adopt threshold from this labelled set", use_container_width=True):
            st.session_state.bona_threshold = float(ev["suggested_threshold"])
            st.session_state.threshold_source = (
                f"calibrated on {ev['n']} labelled samples, "
                f"{datetime.now().strftime('%d %b %Y %H:%M')}"
            )
            st.success("Threshold updated for this session. Re-run live analysis to refresh verdicts.")
            st.rerun()
    elif n_real < 1 or n_spoof < 1:
        st.warning("Threshold not calibrated — using prototype default. EER needs both REAL_ and SPOOF_ files.")
    else:
        st.warning("Threshold not calibrated — using prototype default.")

    if ev["n"] < 30:
        st.warning(
            f"Only {ev['n']} labelled samples. Figures this small have wide error bars and "
            "must not be quoted as product accuracy."
        )

    render(st, '<div class="tv-section">Evaluation result</div>')
    st.dataframe(ev["rows"], use_container_width=True, hide_index=True)
    st.caption("Measured on this labelled set only.")
