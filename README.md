# TRUSTVOICE AI

SIH (Smart India Hackathon) prototype for **AI-powered conversation security**:
voice authenticity, speaker identity *status*, intent, social-engineering
indicators, and context are analysed separately and fused into a
**Dynamic Trust Score** (decision support, not a probability).

Core idea: **a real voice is not a safe conversation.**

This is a local prototype, not a production security product. It does **not**
intercept ordinary cellular calls, enroll a real user gallery, or claim
calibrated detector accuracy.

## Capabilities

- **Anti-spoofing:** optional AASIST / W2V2-AASIST ONNX countermeasures
  (`models/aasist.onnx` is the small default). Output is an *authenticity
  score* plus LIKELY AUTHENTIC / LIKELY SPOOF / INCONCLUSIVE, with an
  uncertainty band. Poor audio is inconclusive, not an alarm.
- **ASR:** local faster-whisper on CPU (default model `base`, with `small`,
  `tiny`, `base.en`, `small.en` selectable in Settings or via `TRUSTVOICE_ASR_MODEL`).
  Includes beam search (size=5), dynamic range audio normalization, domain vocabulary
  prompting (OTP, wire transfer, banking terms), and dual VAD/language fallbacks.
  First load is cached in process. Transcripts are **not** guaranteed 100% accurate.
  ASR does not decide whether a voice is synthetic.
- **Interaction analysis:** TF-IDF + logistic regression intent classifier,
  regex entities, behavioural cues, context anomalies, conversation state.
- **Fusion:** prototype weights in `risk/config.py`. Hard gates require
  *combinations* (for example OTP solicitation + pressure + unverified
  identity), not a single keyword.
- **Trust Handshake:** simulated independent verification UI when interaction
  risk is CRITICAL. Buttons do not contact a device or telecom service.
- **Evaluation lab:** metrics (accuracy, precision, recall, F1, FAR, FRR, EER,
  confusion matrix) appear **only** when you upload labelled `REAL_` / `SPOOF_`
  files. No placeholder numbers.

## Not implemented / not claimed

- ASR is bundled as **local faster-whisper**, not an in-house trained model
  and not a cloud LLM. Default `tiny` is multilingual enough for mixed
  English/Indian-language speech in a demo, but **language accuracy has not
  been evaluated** here. Manual transcript entry remains available and
  **overrides** ASR for scoring when you type text.
- ASR failure or no-speech does **not** mean the conversation is benign —
  interaction analysis simply does not run until a transcript exists.
- No live speaker enrollment. Identity is `VERIFIED` / `UNVERIFIED` /
  `NOT_AVAILABLE` / `MISMATCH` for the demo — unavailable is not “malicious”.
- No telecom, SS7, or cellular tap.
- Raw countermeasure scores are **not** calibrated probabilities unless you
  fit a threshold in the evaluation lab.

## Run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Optional PDF reports: `python -m pip install reportlab`

Place a larger W2V2-AASIST ONNX file in `models/` or set `TRUSTVOICE_MODEL_PATH`
to run a different checkpoint. First-run download is attempted only if the
file is missing.

ASR weights download once into the Hugging Face cache **on the server**. End-user
laptops do not install Whisper. Streamlit Cloud / Codespaces should install
`packages.txt` (`ffmpeg`) so MP3/M4A/WhatsApp/WebM decode reliably; `imageio-ffmpeg`
is a bundled fallback. Default model is `TRUSTVOICE_ASR_MODEL=base` (or select in Settings). Clips longer
than `TRUSTVOICE_ASR_MAX_SEC` (default 120) are transcribed only for the first
window, with a note. Evaluation-lab anti-spoof runs do **not** load Whisper.

## Live analysis vs demo scenarios

| Mode | What it is |
| --- | --- |
| **LIVE / UPLOADED ANALYSIS** | Decode audio → AASIST (if possible) → local ASR → existing intent / behaviour / context / fusion on the transcript (typed text overrides ASR). |
| **DEMO SCENARIO** | Scripted dialogue run through the *same* interaction engine. Voice labels in the script are illustrative, not live AASIST measurements. Demo scripts do not call ASR. |

Do not mix the two when presenting scores.

## Demo scenarios

- **A — unknown caller:** Hello → bank pretext → account number → OTP → urgency/threat. Trust should fall.
- **B — verified identity:** greeting → employee database → personal email → secrecy. Trust should fall even though identity is verified (identity ≠ authorization).

There is also a **benign / contrast** button list (meetings, security advice, credential asks) so judges can see that ordinary language does not automatically become CRITICAL.

## Evaluate anti-spoofing

In **Evaluation**, upload files named `REAL_…` and `SPOOF_…`. If both classes
are present, EER and a suggested threshold can be derived. If not, the UI
states that the threshold is the prototype default.

## Tests

```bash
python -m unittest tests.test_pipeline tests.test_asr
```

ASR unit tests **mock** the Whisper boundary. They do not download weights or
claim measured transcription accuracy.

## Layout

```
app.py                 Streamlit entry
ui/                    SOC-style console, demo, evaluation, reports, settings
models/                anti-spoof, ASR, intent, entities
risk/                  behaviour, context, fusion, pipeline
demo/                  scripted scenarios
utils/                 audio, state, evaluation, reporting
```

## Privacy

Prototype processing is local to the application environment. Voice/audio
data should be treated as sensitive and retained only as long as necessary.
No compliance certification is claimed.
