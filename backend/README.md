# LearnX AI Video Intelligence & Study Planner — Backend Reference Architecture

## What this is

This `backend/` folder is a **reference architecture**, not a deployed or
tested service. It shows exactly how the LearnX AI Video Intelligence and
AI Study Planner features described in the product spec would be
implemented as a real backend, and how the existing frontend
(`src/data/videoIntelligenceMock.ts`, `src/data/plannerMock.ts`,
`src/hooks/useStudyPlan.ts`) maps onto real services.

**Nothing in this folder has been run.** There is no GPU, no Redis, no
Postgres, and no model weights available in the environment this was
written in. Treat every module as a well-typed interface + implementation
sketch that a backend team can pick up, install real dependencies for, and
run.

## Why a skeleton instead of a "working" service

Whisper/WhisperX transcription, Silero VAD / pyannote diarization, and
FFmpeg-based trimming all require:

- A GPU (or a very long CPU inference time) for anything beyond a few
  minutes of audio.
- Multi-gigabyte model weight downloads.
- A real object store for uploaded video files.
- A message broker (Redis) + worker pool (Celery) for background
  processing that can run for many minutes per lecture.

None of that exists in this sandbox, and shipping code that has never
executed against a real model, broker, or database while calling it
"production-ready" would be actively misleading. Instead, every module
below is:

- Fully typed and documented.
- Structured exactly the way it would be structured in production
  (routers → services → pipeline stages → workers).
- Explicit about which calls are "real" (I/O, DB, queueing) vs. which
  are `# TODO: call real model here` stubs.

## Architecture overview

```
Client (React/Vite frontend)
        │  REST + WebSocket
        ▼
FastAPI app  (app/main.py, app/api/*)
        │
        ├── PostgreSQL (app/models — SQLAlchemy) via app/core/db.py
        │
        ├── Redis (broker + result backend for Celery, + pub/sub for
        │   WebSocket progress updates)
        │
        ├── Object storage (S3-compatible) via app/services/storage.py
        │
        └── Celery workers (app/workers/*) run the pipeline:
                app/pipeline/stages/*.py, orchestrated by
                app/pipeline/orchestrator.py, each stage persisting
                incremental state so a crashed worker can resume.
```

## Pipeline stage → module mapping

Each stage in the product spec's pipeline diagram maps 1:1 to a module in
`app/pipeline/stages/`:

| Spec stage | Module | Real dependency |
|---|---|---|
| Virus Scan | `stages/virus_scan.py` | ClamAV daemon |
| Metadata Extraction | `stages/metadata.py` | `ffprobe` |
| Audio Extraction | `stages/audio_extraction.py` | `ffmpeg` |
| Speech / Voice Activity Detection | `stages/vad.py` | Silero VAD |
| Speaker Diarization | `stages/diarization.py` | `pyannote.audio` |
| Silence Detection | `stages/silence_detection.py` | VAD output + heuristics (see docstring) |
| Scene Detection | `stages/scene_detection.py` | `PySceneDetect` / `ffmpeg` |
| OCR / Subtitle Detection | `stages/ocr.py` | Tesseract / PaddleOCR |
| Speech Recognition | `stages/transcription.py` | WhisperX |
| Topic & Chapter Detection | `stages/chaptering.py` | embeddings + clustering |
| Concept / Formula Extraction | `stages/concept_extraction.py` | LLM (RAG-grounded) |
| Summary / Flashcards / Quiz / Mind Map / Notes | `stages/generation.py` | LLM (RAG-grounded, same corpus) |
| Smart Trimming (optimized video) | `stages/trimming.py` | `ffmpeg` concat/cut using silence_detection output |

`app/pipeline/orchestrator.py` runs these in order, matching the sequence
in `src/data/videoIntelligenceMock.ts`'s `PIPELINE_STAGE_DEFS`, and emits
progress over the same shape the frontend's `PipelineStage` type expects —
so swapping the mock data source for real API calls requires no frontend
changes beyond the data-fetching layer.

## Study Planner service

`app/services/study_planner.py` describes the planning algorithm inputs
(exam dates, quiz scores, lecture completion, available hours, focus
score) and the "regenerate on any signal change" behavior that
`src/hooks/useStudyPlan.ts` simulates client-side. `app/api/planner.py`
exposes the endpoints the frontend would call instead of using mock data.

## Running this for real (future work)

1. `docker compose up -d postgres redis minio clamav`
2. Download WhisperX + pyannote + Silero VAD model weights (see comments
   in `app/services/ai_models.py`).
3. `pip install -r requirements.txt` (contains version pins for FastAPI,
   Celery, SQLAlchemy, WhisperX, pyannote.audio, etc. — see the file for
   which packages are heavy/GPU-only).
4. `uvicorn app.main:app --reload` for the API.
5. `celery -A app.workers.celery_app worker --loglevel=info` for the
   pipeline workers.
6. Point `VITE_API_BASE_URL` in the frontend at this API instead of the
   mock data modules.

## Security & compliance notes (see spec § Security)

- All video/document storage keys are namespaced per-user
  (`app/services/storage.py::user_scoped_key`) and served via
  short-lived signed URLs, never public buckets.
- Every table with user content has a `user_id` foreign key with
  row-level access checks in `app/api/deps.py::require_owner`.
- File validation (`app/services/validation.py`) checks MIME type,
  extension, and magic bytes before a file is queued — not just the
  extension the client claims.
