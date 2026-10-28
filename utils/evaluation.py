"""Labelled anti-spoof evaluation. Metrics are shown only for real labelled samples."""

from __future__ import annotations

from models.antispoof import analyze_audio_bytes, sigmoid
from risk.config import DEFAULT_BONA_THRESHOLD


def compute_eer(scores, labels):
    pairs = sorted(zip(scores, labels))
    candidates = sorted(set(scores))
    n_bona = sum(1 for l in labels if l == 1)
    n_spoof = sum(1 for l in labels if l == 0)
    if not n_bona or not n_spoof:
        return None, None
    best = None
    for thr in candidates + [max(candidates) + 1e-6]:
        far = sum(1 for s, l in pairs if l == 0 and s >= thr) / n_spoof
        frr = sum(1 for s, l in pairs if l == 1 and s < thr) / n_bona
        gap = abs(far - frr)
        if best is None or gap < best[0]:
            best = (gap, (far + frr) / 2.0, thr)
    return best[1], best[2]


def evaluate_labeled_voice_set(
    uploaded_files,
    threshold=None,
    model_key="aasist",
    band=0.0,
    threshold_source="evaluation",
):
    if threshold is None:
        threshold = DEFAULT_BONA_THRESHOLD

    rows, scores, labels = [], [], []
    for uploaded in uploaded_files or []:
        name = str(getattr(uploaded, "name", ""))
        raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded[1]
        upper = name.upper()
        if upper.startswith(("REAL_", "REAL-", "BONAFIDE_", "BONA_")):
            truth = "REAL"
        elif upper.startswith(("SPOOF_", "SPOOF-", "FAKE_", "FAKE-")):
            truth = "SPOOF"
        else:
            continue

        result = analyze_audio_bytes(
            raw, name, model_key=model_key, threshold=threshold,
            band=band, threshold_source=threshold_source, allow_download=False,
        )
        anti = result.get("anti_spoof") or {}
        if not anti:
            rows.append({
                "file": name, "truth": truth, "prediction": "ERROR",
                "authenticity_score": None, "cm_score": None,
                "error": "; ".join(result.get("limitations", [])) or "No model output",
            })
            continue

        score01 = float(anti.get("authenticity_score", 0)) / 100.0
        pred = "REAL" if score01 >= threshold else "SPOOF"
        rows.append({
            "file": name, "truth": truth, "prediction": pred,
            "authenticity_score": anti.get("authenticity_score"),
            "cm_score": anti.get("cm_score"),
            "error": "",
        })
        scores.append(float(anti.get("cm_score", 0.0)))
        labels.append(1 if truth == "REAL" else 0)

    valid = [r for r in rows if r["prediction"] in {"REAL", "SPOOF"}]
    n_real = sum(1 for r in valid if r["truth"] == "REAL")
    n_spoof = sum(1 for r in valid if r["truth"] == "SPOOF")
    if not valid:
        return {"rows": rows, "n": 0, "n_real": 0, "n_spoof": 0}

    tp = sum(r["truth"] == "SPOOF" and r["prediction"] == "SPOOF" for r in valid)
    tn = sum(r["truth"] == "REAL" and r["prediction"] == "REAL" for r in valid)
    fp = sum(r["truth"] == "REAL" and r["prediction"] == "SPOOF" for r in valid)
    fn = sum(r["truth"] == "SPOOF" and r["prediction"] == "REAL" for r in valid)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    eer, eer_cm_threshold = compute_eer(scores, labels)
    suggested = sigmoid(eer_cm_threshold) if eer_cm_threshold is not None else None
    far = fn / n_spoof if n_spoof else None
    frr = fp / n_real if n_real else None

    return {
        "rows": rows,
        "n": len(valid),
        "n_real": n_real,
        "n_spoof": n_spoof,
        "total_uploaded": len(rows),
        "threshold_used": round(float(threshold), 4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": (tp + tn) / len(valid),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "far": far,
        "frr": frr,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "fnr": fn / (fn + tp) if fn + tp else 0.0,
        "eer": eer,
        "suggested_threshold": suggested,
        "classes_present": len(set(labels)),
        "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "false_positives": [r["file"] for r in valid if r["truth"] == "REAL" and r["prediction"] == "SPOOF"],
        "false_negatives": [r["file"] for r in valid if r["truth"] == "SPOOF" and r["prediction"] == "REAL"],
    }
