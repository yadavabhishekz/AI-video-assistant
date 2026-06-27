"""
FastAPI backend for the AI Meeting Assistant pipeline.

Wraps the existing pipeline (utils.audio_processor, core.transcriber,
core.summarizer, core.extractor, core.rag_engine) behind a small API:

  POST   /meetings                  -> submit a source, returns {meeting_id}
  GET    /meetings/{meeting_id}     -> poll status + result
  POST   /meetings/{meeting_id}/ask -> ask a question about the meeting (RAG)
  DELETE /meetings/{meeting_id}     -> drop a meeting from memory

Run with:  uvicorn main:app --reload
"""

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import shutil
import tempfile
import traceback
from datetime import datetime
from threading import Thread

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question
from core.pdf_export import build_summary_pdf

app = FastAPI(title="AI Meeting Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store: {meeting_id: {...}}. Swap for a DB if you need persistence.
MEETINGS: dict[str, dict] = {}


class CreateMeetingRequest(BaseModel):
    source: str  # YouTube URL or local file path
    language: str = "english"


class AskRequest(BaseModel):
    question: str


def _update(meeting_id: str, **fields):
    MEETINGS[meeting_id].update(fields)
    MEETINGS[meeting_id]["updated_at"] = datetime.utcnow().isoformat()


def _process_meeting(meeting_id: str, source: str, language: str):
    try:
        _update(meeting_id, status="fetching_audio")
        chunks = process_input(source)

        _update(meeting_id, status="transcribing")
        transcript = transcribe_all(chunks, language)

        _update(meeting_id, status="summarizing")
        title = generate_title(transcript)
        summary = summarize(transcript)

        _update(meeting_id, status="extracting")
        action_items = extract_action_items(transcript)
        decisions = extract_key_decisions(transcript)
        questions = extract_questions(transcript)

        _update(meeting_id, status="indexing")
        rag_chain = build_rag_chain(transcript, meeting_id=meeting_id)
        MEETINGS[meeting_id]["_rag_chain"] = rag_chain  # kept server-side only

        _update(
            meeting_id,
            status="done",
            result={
                "title": title,
                "transcript": transcript,
                "summary": summary,
                "action_items": action_items,
                "key_decisions": decisions,
                "open_questions": questions,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _update(meeting_id, status="error", error=str(exc), traceback=traceback.format_exc())


@app.post("/meetings")
def create_meeting(req: CreateMeetingRequest):
    meeting_id = str(uuid.uuid4())
    MEETINGS[meeting_id] = {
        "meeting_id": meeting_id,
        "status": "queued",
        "source": req.source,
        "language": req.language,
        "result": None,
        "error": None,
        "chat_history": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    Thread(target=_process_meeting, args=(meeting_id, req.source, req.language), daemon=True).start()
    return {"meeting_id": meeting_id, "status": "queued"}


@app.post("/meetings/upload")
def create_meeting_from_upload(file: UploadFile = File(...), language: str = Form("english")):
    meeting_id = str(uuid.uuid4())
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    tmp_path = os.path.join(tempfile.gettempdir(), f"{meeting_id}{suffix}")
    with open(tmp_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    MEETINGS[meeting_id] = {
        "meeting_id": meeting_id,
        "status": "queued",
        "source": tmp_path,
        "language": language,
        "result": None,
        "error": None,
        "chat_history": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    Thread(target=_process_meeting, args=(meeting_id, tmp_path, language), daemon=True).start()
    return {"meeting_id": meeting_id, "status": "queued"}



@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    meeting = MEETINGS.get(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {
        "meeting_id": meeting["meeting_id"],
        "status": meeting["status"],
        "result": meeting["result"],
        "error": meeting["error"],
        "created_at": meeting["created_at"],
        "updated_at": meeting.get("updated_at"),
    }


@app.post("/meetings/{meeting_id}/ask")
def ask(meeting_id: str, req: AskRequest):
    meeting = MEETINGS.get(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Meeting not ready yet (status: {meeting['status']})")
    rag_chain = meeting.get("_rag_chain")
    answer = ask_question(rag_chain, req.question)
    return {"answer": answer}


@app.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: str):
    if meeting_id not in MEETINGS:
        raise HTTPException(status_code=404, detail="Meeting not found")
    del MEETINGS[meeting_id]
    return {"deleted": meeting_id}


@app.get("/meetings/{meeting_id}/export/summary")
def export_summary_pdf(meeting_id: str):
    meeting = MEETINGS.get(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting["status"] != "done" or not meeting["result"]:
        raise HTTPException(status_code=409, detail=f"Meeting not ready yet (status: {meeting['status']})")

    pdf_bytes = build_summary_pdf(meeting["result"])
    filename = f"recap-summary-{meeting_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
def health():
    return {"ok": True}


# Serve the static frontend (frontend/index.html) from the same process.
# Requires fastapi>=0.138.0. API routes above always take precedence.
app.frontend("/", directory="frontend")