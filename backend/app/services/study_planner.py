"""
AI Study Plan Generator service.

Real approach
-------------
The planner is best modeled as a constrained scheduling problem, not a
single LLM call:

1. **Collect signals** for the student: upcoming exams (date + subject),
   per-topic mastery scores (derived from quiz/flashcard history), lecture
   completion state, assignment due dates, available study hours/day
   (either user-configured or inferred from historical session lengths),
   focus-score time-of-day curve, and learning speed (derived from how
   quickly quiz accuracy improves per unit of study time on a topic).

2. **Score every candidate task** (watch lecture X, revise topic Y,
   practice topic Z, take quiz W, review flashcard deck V) using a
   weighted priority function, e.g.:

       priority = (
           w1 * days_until_related_exam_inverse
           + w2 * (1 - topic_mastery)
           + w3 * spaced_repetition_due_urgency
           + w4 * assignment_deadline_proximity
       )

   This is the same signal set `src/data/plannerMock.ts::plannerInputs`
   models, just scripted by hand there instead of computed.

3. **Pack scored tasks into the available time windows** for the
   requested horizon (day/week/month), respecting:
     - `available_hours_per_day`
     - a max continuous focus block (e.g. 45–60 min) before inserting a
       `break` task
     - the focus-score curve, so `exam-prep`/`practice` tasks (which need
       the most focus) are scheduled during the user's historically
       highest-focus windows, and `revision`/`flashcards` (lower-focus
       tasks) fill the rest.

4. **Persist the resulting `StudyTask` rows**, tagged with the
   `PlanRegenerationTrigger` that produced them.

5. **Re-run step 2–4** whenever `regenerate()` is called — see the
   trigger enum in `app/models/planner.py` and the API surface in
   `app/api/planner.py`. This "no manual intervention required"
   regeneration is simulated client-side today by
   `src/hooks/useStudyPlan.ts::regenerate()`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.planner import PlanRegenerationTrigger


@dataclass
class PlannerInputs:
    upcoming_exams: list[dict]
    topic_mastery: dict[str, float]  # topic -> 0..1
    available_hours_per_day: float
    focus_curve: dict[int, float]  # hour-of-day (0-23) -> relative focus 0..1
    learning_speed: float  # topic-mastery gain per study hour, historical average


def regenerate_plan(inputs: PlannerInputs, trigger: PlanRegenerationTrigger) -> list[dict]:
    """
    Recomputes the rolling task window for a student. This is the server
    counterpart to `useStudyPlan.regenerate()` on the frontend — see the
    module docstring for the scoring/packing algorithm this would run.
    """

    raise NotImplementedError(
        "Reference stub — implement the scoring + time-window packing "
        "algorithm described in this module's docstring. See "
        "src/hooks/useStudyPlan.ts for the client-side behavior this "
        "endpoint should match."
    )
