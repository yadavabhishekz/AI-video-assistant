"""
PDF export helpers for RECAP.

build_summary_pdf  -> title, summary, action items, key decisions, open questions
build_chat_pdf     -> the Q&A chat history for a meeting
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable
)

styles = getSampleStyleSheet()

heading_style = ParagraphStyle(
    "RecapHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8,
    textColor=colors.HexColor("#1a1410"),
)
title_style = ParagraphStyle(
    "RecapTitle", parent=styles["Title"], textColor=colors.HexColor("#b8772b"),
)
body_style = ParagraphStyle(
    "RecapBody", parent=styles["Normal"], fontSize=10.5, leading=15,
)


import re


def _as_list(items):
    return items if isinstance(items, list) else ([items] if items else [])


def _split_numbered_or_starred(text: str):
    """Splits a single blob like 'Here are the decisions: 1. A 2. B' into clean items."""
    text = text.strip()
    if not text:
        return []

    preamble = re.match(r"^(here('?s| are)[^:]{0,120}:)\s*", text, flags=re.IGNORECASE)
    if preamble:
        text = text[preamble.end():]

    numbered = [s.strip() for s in re.split(r"(?:(?<=^)|(?<=\s))\d+\.\s+", text) if s.strip()]
    if len(numbered) > 1:
        return numbered

    starred = [s.strip() for s in re.split(r"(?:(?<=^)|(?<=\s))\*\s+", text) if s.strip()]
    if len(starred) > 1:
        return starred

    return [text]


def parse_extracted_items(raw):
    """Normalizes either a list of strings or one numbered/starred blob string into clean items."""
    if isinstance(raw, list):
        out = []
        for item in raw:
            out.extend(parse_extracted_items(item))
        return out
    if not isinstance(raw, str):
        return [raw] if raw else []
    return _split_numbered_or_starred(raw)


def _bullet_section(story, heading, items):
    story.append(Paragraph(heading, heading_style))
    items = parse_extracted_items(items)
    if not items:
        story.append(Paragraph("None found.", body_style))
        return
    bullets = [ListItem(Paragraph(str(item), body_style)) for item in items]
    story.append(ListFlowable(bullets, bulletType="bullet", leftIndent=14))


def build_summary_pdf(result: dict) -> bytes:
    """result is the same dict returned by GET /meetings/{id} (the 'result' field)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    story = []

    story.append(Paragraph(result.get("title") or "Untitled Meeting", title_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e0d9c8")))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Summary", heading_style))
    summary_items = parse_extracted_items(result.get("summary"))
    if len(summary_items) > 1:
        bullets = [ListItem(Paragraph(str(item), body_style)) for item in summary_items]
        story.append(ListFlowable(bullets, bulletType="bullet", leftIndent=14))
    else:
        story.append(Paragraph(summary_items[0] if summary_items else "No summary available.", body_style))

    _bullet_section(story, "Action Items", result.get("action_items"))
    _bullet_section(story, "Key Decisions", result.get("key_decisions"))
    _bullet_section(story, "Open Questions", result.get("open_questions"))

    doc.build(story)
    return buffer.getvalue()


def build_chat_pdf(meeting_title: str, chat_history: list) -> bytes:
    """chat_history: list of {"role": "user"|"assistant", "content": str}"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    story = []

    story.append(Paragraph(f"Chat History — {meeting_title or 'Untitled Meeting'}", title_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#e0d9c8")))
    story.append(Spacer(1, 10))

    if not chat_history:
        story.append(Paragraph("No questions were asked for this meeting.", body_style))
    else:
        for turn in chat_history:
            role = "You" if turn.get("role") == "user" else "Assistant"
            label_style = ParagraphStyle(
                "RecapLabel", parent=body_style,
                textColor=colors.HexColor("#b8772b") if role == "You" else colors.HexColor("#2f7a68"),
                fontName="Helvetica-Bold",
            )
            story.append(Paragraph(role, label_style))
            story.append(Paragraph(str(turn.get("content", "")), body_style))
            story.append(Spacer(1, 8))

    doc.build(story)
    return buffer.getvalue()
