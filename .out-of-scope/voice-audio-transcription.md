# Speech-to-text for videos and voice notes

This project does not transcribe audio. A clip's sound track is not recorded, analysed or
stored as text, and the coach cannot hear what you say while filming. That is deliberate.

## Why this is out of scope

Not because it would be technically hard — it is because **the decision belongs to the user
and they have not asked for it yet**, and every option costs something real:

| Option | Why not (as of 2026-10-05) |
|---|---|
| OpenAI Whisper API | The most accurate and the least code, but **direct OpenAI from Hong Kong is a 403** (measured; see AGENTS.md) — it would need a proxy hop |
| DeepSeek | The key is already configured, but DeepSeek has **no audio model** (V4 is text + vision only) |
| Local whisper.cpp / faster-whisper | Fully offline and the only option consistent with local-first, but a new dependency plus a 100 MB–1.5 GB model file, and speed on Apple Silicon is unmeasured |
| Browser Web Speech API | Zero dependencies, but it uploads the audio to the browser vendor (contradicts local-first) and Cantonese accuracy is weak |

Recorded 2026-10-05, when the user was asked directly: **「暫時唔做」** (not now).

Two supporting facts make the deferral cheap:

- `video.extract_frames()` sends only picture frames to the vision model, and
  `compress_video()` re-encodes with `-an` (**strips the audio track**). A clip's sound has
  therefore never existed anywhere in the pipeline — nothing is leaking or being lost that
  the product once promised.
- `prompts.RECORDING_GUIDE` and `app/guide.py`「點樣記錄最準確」both **already say so**:
  「拍片／講出嚟嘅聲唔會記錄，飲食產品要打落對話」. The guide is honest about the limit
  instead of implying a capability that does not exist. That wording is a product fact —
  do not soften it for the sake of sounding more capable.

## What would change this

A request from the user to record by speaking, plus one decision: local model (privacy, big
download) or cloud STT (small code, third party). Then the implementation has four parts:
`app/video.py` (keep or separately store the audio), a new `app/transcribe.py`, a voice
button in `frontend/src/components/Chat.tsx`, and wiring the transcript into `graph` as
`user_text` or as an extractable self-reported event.

If that happens, delete this file and open a fresh issue. Per the triage convention an
existing issue is not reopened; it is a historical record of an earlier decision.

## Prior requests

- [#26](https://github.com/shulaplai/male_skincare_agent/issues/26): "語音／影片聲軌冇轉文字
  （「講出嚟就得」做唔到）" — left open and labelled `ready-for-human`, because it is a real
  product question waiting on a decision, not an invalid request.
