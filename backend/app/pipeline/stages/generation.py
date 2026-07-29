"""
Concept extraction + generation stage — produces summaries, flashcards,
quiz questions, mind map, and revision notes.

Real approach: one LLM call per chapter (or a small number of batched
calls) that is *strictly grounded* in that chapter's transcript text and
OCR'd slide content — never the model's general knowledge — mirroring
the product requirement that the AI chat "must answer using the lecture
content whenever possible" and "never hallucinate".

A minimal, structured-output prompt shape looks like:

    SYSTEM: You extract structured study material from a lecture
    transcript. Only use facts present in the provided text. If a concept
    isn't explicitly covered, omit it — do not invent content.

    USER: <chapter transcript + OCR text>

    Return JSON matching this schema: { key_concepts, formulas,
    exam_tips, flashcards, quiz_questions, summary_quick, summary_detailed,
    summary_bullet, summary_exam, summary_revision }

Each generated item stores a back-reference to the exact transcript
segment(s) it came from, so the frontend can cite a timestamp for
everything the AI produces (see `app/services/rag.py`).
"""

from __future__ import annotations

from app.pipeline.stage import PipelineContext

STAGE_ID = "generation"


def run(ctx: PipelineContext) -> PipelineContext:
    if not ctx.chapters:
        raise RuntimeError("generation requires chapters — run chaptering.py first")

    raise NotImplementedError(
        "Reference stub — implement grounded per-chapter LLM generation as "
        "described in the module docstring."
    )
