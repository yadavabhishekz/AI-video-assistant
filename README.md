# RECAP — AI Meeting & Video Assistant

> **Transcribe · Summarize · Decide · Chat**
> Drop a YouTube link or a local video/audio file — RECAP turns it into a structured meeting report and lets you chat with the content via RAG.

---

# Demo Video

https://www.loom.com/share/90de82b0cac647ef9a641d81eb24bbba

---

## What it does

RECAP is a full-stack AI pipeline that ingests any video or audio source, extracts a full transcript, and runs a suite of LLM-powered analyses on it:

- **Transcription** — Groq-hosted Whisper (`whisper-large-v3-turbo`) for English; Sarvam AI (`saaras:v2.5`) for Hinglish (transcribes *and* translates to English in one shot)
- **Summarization** — Map-reduce chain over chunked transcript using Llama 3.3-70B on Groq
- **Structured Extraction** — Action items (with owner + deadline), key decisions, and open/unresolved questions
- **RAG Q&A** — Ask anything about the meeting; answers are grounded in the transcript via ChromaDB + `all-MiniLM-L6-v2` embeddings, with each meeting kept in its own isolated collection

---

## Architecture

```
Input (YouTube URL / local file upload)
        │
        ▼
utils/audio_processor.py
  ├── yt-dlp          → downloads YouTube audio
  ├── pydub/ffmpeg    → converts to 16 kHz mono WAV
  └── chunker         → splits into 10-min WAV chunks
        │
        ▼
core/transcriber.py
  ├── English  → Groq Whisper (whisper-large-v3-turbo, hosted API)
  └── Hinglish → Sarvam AI saaras:v2.5  (STT + translate)
        │
        ▼
  Full Transcript (plain text)
        │
        ├──► core/summarizer.py   → map-reduce summary  (Llama 3.3-70B via Groq)
        ├──► core/extractor.py    → action items / decisions / open questions
        └──► core/vector_store.py → ChromaDB (all-MiniLM-L6-v2 embeddings, per-meeting collection)
                                         │
                                         ▼
                                  core/rag_engine.py
                                  LCEL RAG chain → /ask endpoint
```

### API layer (`backend.py` — FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/meetings` | Submit a YouTube URL; returns `meeting_id` |
| `POST` | `/meetings/upload` | Upload a local audio/video file directly (multipart) |
| `GET` | `/meetings/{id}` | Poll status (`queued → fetching_audio → transcribing → summarizing → extracting → indexing → done`) and retrieve result |
| `POST` | `/meetings/{id}/ask` | Ask a question about the meeting (RAG) |
| `DELETE` | `/meetings/{id}` | Remove a meeting from memory |
| `GET` | `/health` | Health check |

Each meeting is processed in a background thread so the API stays non-blocking. Meeting state is held in-memory (swap the `MEETINGS` dict for a DB if you need persistence across restarts).

The backend also serves the frontend directly via FastAPI's built-in `app.frontend()` (added in FastAPI 0.138.0), so the whole app — API + UI — runs as a single process. No separate static host or second deployment needed.

### Frontend (`frontend/index.html`)

A single-file vanilla HTML/CSS/JS app named **RECAP** — no build step, no framework.

- Tabs for YouTube URL or file upload
- Animated RECAP-style progress bar that reflects real pipeline stages
- Results grid: summary, action items, key decisions, open questions, full transcript
- Chat panel with polling `/ask` for RAG Q&A
- Design: dark amber theme, `Fraunces` serif + `JetBrains Mono`
- Served same-origin from the FastAPI backend, so it talks to relative API paths (no hardcoded host)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (≥0.138.0) + Uvicorn |
| LLM | Groq API — Llama 3.3-70B Versatile |
| STT (English) | Groq — Whisper Large v3 Turbo (hosted API) |
| STT (Hinglish) | Sarvam AI — saaras:v2.5 |
| LLM Orchestration | LangChain LCEL (chains, prompts, parsers) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector Store | ChromaDB (local, persisted, one collection per meeting) |
| Audio Processing | yt-dlp, pydub, ffmpeg |
| Frontend | Vanilla HTML/CSS/JS, served by FastAPI's `app.frontend()` |

---

## Project Structure

```
RECAP/
├── backend.py              # FastAPI app — REST API + serves the frontend
├── main.py                 # CLI entry point (run pipeline interactively)
├── test.py                 # Quick smoke-test script
├── requirements.txt
├── .env.example
│
├── core/
│   ├── transcriber.py      # Dual-engine STT: Groq Whisper (hosted) + Sarvam AI
│   ├── summarizer.py       # Map-reduce summarization (LangChain LCEL)
│   ├── extractor.py        # Action items / decisions / questions extraction
│   ├── rag_engine.py       # Build & query RAG chain over transcript (per meeting_id)
│   └── vector_store.py     # ChromaDB build, load, retriever factory (per-meeting collections)
│
├── utils/
│   └── audio_processor.py  # YouTube download, WAV conversion, chunking
│
└── frontend/
    └── index.html          # Single-file web UI ("RECAP")
```

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- FFmpeg installed and on PATH (`brew install ffmpeg` / `apt install ffmpeg`)

### Install dependencies

```bash
pip install -r requirements.txt
```

> Requires `fastapi>=0.138.0` for `app.frontend()` to be available. If upgrading from an older FastAPI version, run `pip install --upgrade "fastapi>=0.138.0"`.

### Configure environment

```bash
cp .env.example .env
# Fill in your keys:
# GROQ_API_KEY=...
# SARVAM_API_KEY=...       # only needed for Hinglish transcription
```

### Run

**API + UI (recommended — single process)**
```bash
uvicorn backend:app --reload
# open http://localhost:8000 — FastAPI serves both the API and the RECAP UI
```

**CLI**
```bash
python main.py
# Enter YouTube URL or local file path when prompted
```

---

## Example Flow

1. Open RECAP in the browser, choose **YouTube URL** or **Upload file**, and hit **Run pipeline**
2. Watch the progress bar move through: Fetch → Transcribe → Summarize → Extract → Index
3. View the generated title, bullet-point summary, action items with owners, key decisions, and open questions
4. Switch to the **Chat** panel and ask: *"Who is responsible for the Q3 report?"* or *"What was decided about the budget?"*

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ | Groq API key (used for both Whisper STT and Llama LLM) |
| `SARVAM_API_KEY` | ⚠️ Hinglish only | Sarvam AI key for Hindi/Hinglish transcription |
| `GROQ_WHISPER_MODEL` | Optional | Defaults to `whisper-large-v3-turbo` |
| `SARVAM_STT_MODEL` | Optional | Defaults to `saaras:v2.5` |

---

## Notes

- ChromaDB data is persisted locally in `vector_db/`. Each meeting gets its own collection (keyed by `meeting_id`), so chat answers stay scoped to that meeting and don't leak across users/sessions.
- Audio chunks are written to a temp/`downloads/` directory and are gitignored.
- The Sarvam STT endpoint accepts max 30s audio; `transcriber.py` automatically splits chunks into 25s pieces before sending.
- For very long meetings, summarization uses a map-reduce approach — each chunk is summarized independently, then combined into a final summary.
- Meeting state and vector collections live in memory/disk on the running server process — they don't survive a restart or redeploy unless you attach persistent storage or move to a DB-backed store.
