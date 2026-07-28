"""
Retrieval-Augmented Generation service for the per-lecture AI chat.

Real approach:
  1. Every `TranscriptSegment` was embedded during `transcription.py`.
  2. On a chat query, embed the query with the same model
     (`settings.embeddings_model`) and retrieve the top-k most similar
     transcript segments (cosine similarity; `pgvector` in Postgres, or a
     dedicated vector store like Qdrant for larger corpora).
  3. Build a grounded prompt:

       SYSTEM: Answer only using the provided lecture excerpts. If the
       excerpts don't contain the answer, say so explicitly — never guess.
       Always include the timestamp of every excerpt you use.

       CONTEXT:
       [12:34] "..."
       [18:02] "..."

       QUESTION: {user question}

  4. Parse the model's citations back into `ChatCitationOut` entries
     (chapter_id + timestamp_sec) so the frontend's `VideoChatPanel` can
     render clickable "jump to timestamp" chips — exactly like the
     simulated `generateAnswer()` function in
     `src/components/dashboard/student/video/VideoChatPanel.tsx` does
     today with hand-written logic instead of retrieval + an LLM.

This retrieval-first design is what satisfies the product requirement
"Always answer using lecture content. Always cite timestamps. Never
hallucinate." — the model is never allowed to answer from unguided
general knowledge for lecture-specific questions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    transcript_segment_id: str
    chapter_id: str
    chapter_title: str
    timestamp_sec: float
    text: str
    similarity: float


def retrieve(lecture_id: str, query: str, top_k: int = 5) -> list[RetrievedChunk]:
    raise NotImplementedError(
        "Reference stub — embed `query`, run a vector similarity search "
        "scoped to `lecture_id`, and return the top_k chunks. See module docstring."
    )


def answer_with_citations(lecture_id: str, query: str) -> tuple[str, list[RetrievedChunk]]:
    chunks = retrieve(lecture_id, query)
    raise NotImplementedError(
        "Reference stub — build the grounded prompt from `chunks` and call "
        "the LLM, then return (answer_text, chunks_actually_cited). See module docstring."
    )
