"""Shared fake AI provider for understanding-first quiz pipeline tests.

The fake mirrors what a real structured provider does, in two stages:

1. **Understanding** — it reads the cleaned source it was handed and proposes a
   document understanding (subject, summary, topics, concepts, relationships,
   objectives) using verbatim quotes from that source.  It never invents
   content, so the backend's grounding checks operate exactly as in production.
2. **Writing** — it turns the blueprints the backend planned into candidate
   prose.  Tests may instead supply an explicit pool of candidates when they
   want to exercise a specific prose shape.

Nothing here weakens a production gate: everything the fake emits is validated
by the same normalizer, deduplicator, and scorer as a live provider response.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Callable

from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_deterministic import deterministic_candidates
from app.services.quiz_pipeline import _RawCandidate, _RawQuizPool
from app.services.quiz_understanding import (
    DocumentUnderstanding,
    _RawUnderstanding,
    deterministic_understanding,
)
from app.services.quiz_concepts import split_source_units
from app.services.quiz_boilerplate import clean_source_units


class FakeCompletion:
    def __init__(self, value, provider="gemini", model="gemini-test", fallback_used=False):
        self.value = value
        self.provider = provider
        self.model = model
        self.fallback_used = fallback_used


_BLUEPRINT_RE = re.compile(
    r"^- \[(?P<id>[^]]+)] Q\d+ [^:]+: concept=(?P<concept>.*?) \((?P<concept_id>[^)]+)\); "
    r"knowledge_target=(?P<target>.*?) \((?P<target_id>[^)]+)\); skill=(?P<skill>[^;]+); "
    r"type=(?P<type>[^;]+); difficulty=(?P<difficulty>[^;]+); pages=(?P<pages>\[[^]]*]); "
    r"VERBATIM EVIDENCE=(?P<evidence>.*)$"
)


def parse_blueprints(prompt: str) -> list[dict[str, Any]]:
    """Recover the blueprint plan the backend rendered into the writer prompt."""
    blueprints: list[dict[str, Any]] = []
    for line in prompt.splitlines():
        match = _BLUEPRINT_RE.match(line)
        if not match:
            continue
        values = match.groupdict()
        try:
            values["concept"] = ast.literal_eval(values["concept"])
            values["target"] = ast.literal_eval(values["target"])
            values["pages"] = ast.literal_eval(values["pages"])
            values["evidence"] = ast.literal_eval(values["evidence"])
        except (SyntaxError, ValueError):
            continue
        blueprints.append(values)
    return blueprints


def understanding_from_source(text: str, *, title: str = "Source") -> DocumentUnderstanding:
    """Deterministic study map for the source a prompt carried."""
    return deterministic_understanding(
        clean_source_units(split_source_units(text)), title=title
    )


def _raw_understanding(understanding: DocumentUnderstanding) -> _RawUnderstanding:
    """Render a study map back into the shape a provider would return."""
    return _RawUnderstanding.model_validate(
        {
            "subject": understanding.subject,
            "summary": understanding.summary,
            "main_topics": [
                {
                    "name": topic.name,
                    "subtopics": list(topic.subtopics),
                    "concept_ids": list(topic.concept_ids),
                    "source_pages": list(topic.pages),
                }
                for topic in understanding.main_topics
            ],
            "concepts": [
                {
                    "id": concept.concept_id,
                    "name": concept.name,
                    "description": concept.description,
                    "topic": concept.topic,
                    "knowledge_type": concept.knowledge_type,
                    "teaching_emphasis": "high" if concept.importance >= 0.7 else "medium",
                    "evidence_quotes": [item.text for item in concept.evidence],
                    "source_pages": list(concept.source_pages),
                    "prerequisites": list(concept.prerequisites),
                    "related_concepts": list(concept.related_concepts),
                    "why_important": concept.rationale,
                }
                for concept in understanding.concepts
            ],
            "relationships": [
                {
                    "source": relationship.source_id,
                    "target": relationship.target_id,
                    "kind": relationship.kind,
                    "evidence": relationship.evidence,
                    "source_pages": list(relationship.pages),
                }
                for relationship in understanding.relationships
            ],
            "learning_objectives": [
                {
                    "text": objective.text,
                    "concept_ids": list(objective.concept_ids),
                    "source_pages": list(objective.pages),
                }
                for objective in understanding.learning_objectives
            ],
        }
    )


class FakeQuizService:
    """A provider that understands the document, then writes to the blueprint.

    ``pool`` optionally supplies explicit candidate prose; each entry is matched
    onto the blueprint whose evidence it best fits, exactly as a cooperative
    provider would. When no pool is given, the fake writes candidates from the
    blueprints it was handed.
    """

    def __init__(
        self,
        pool: _RawQuizPool | None = None,
        *,
        title: str = "Source",
        understanding_hook: Callable[[DocumentUnderstanding], DocumentUnderstanding] | None = None,
    ):
        self.pool = pool
        self.title = title
        self.understanding_hook = understanding_hook
        self.calls: list[dict] = []
        self.understanding: DocumentUnderstanding | None = None

    # -- stage 1 ---------------------------------------------------------- #
    def _understanding_for(self, prompt: str) -> _RawUnderstanding:
        source = prompt.split("CLEANED SOURCE:\n", 1)[-1]
        understanding = understanding_from_source(source, title=self.title)
        if self.understanding_hook is not None:
            understanding = self.understanding_hook(understanding)
        self.understanding = understanding
        return _raw_understanding(understanding)

    # -- stage 2 ---------------------------------------------------------- #
    def _write(self, prompt: str) -> _RawQuizPool:
        plan = parse_blueprints(prompt)
        if self.pool is None:
            return self._write_from_blueprints(plan)
        return _RawQuizPool(questions=self._attach_pool(plan))

    def _write_from_blueprints(self, plan: list[dict[str, Any]]) -> _RawQuizPool:
        blueprints = [
            QuestionBlueprint(
                id=item["id"],
                concept_id=item["concept_id"],
                concept=item["concept"],
                knowledge_target_id=item["target_id"],
                knowledge_target=item["target"],
                knowledge_type="definition",
                cognitive_skill=item["skill"],
                question_type=item["type"],
                difficulty=item["difficulty"],
                importance=0.9,
                evidence=item["evidence"],
                pages=tuple(item["pages"]),
            )
            for item in plan
        ]
        assert self.understanding is not None
        written = deterministic_candidates(
            blueprints, language="en", understanding=self.understanding
        )
        return _RawQuizPool(
            questions=[_RawCandidate.model_validate(item) for item in written]
        )

    def _attach_pool(self, plan: list[dict[str, Any]]) -> list[_RawCandidate]:
        from app.services.quiz_scoring import classify_cognitive_skill, content_tokens

        questions: list[_RawCandidate] = []
        assert self.pool is not None
        for candidate in self.pool.questions:
            qtype = candidate.type.strip().lower().replace("_", "-")
            if qtype in {"multiple-choice", "multiple choice"}:
                qtype = "mcq"
            if qtype in {"true/false", "tf"}:
                qtype = "true-false"
            candidate_pages = {int(page) for page in candidate.source_pages if str(page).isdigit()}
            candidate_tokens = content_tokens(
                f"{candidate.prompt} {candidate.correct_answer} {candidate.explanation}"
            )
            classified = classify_cognitive_skill(candidate.prompt)

            compatible = [
                item
                for item in plan
                if item["type"] == qtype and candidate_pages.intersection(item["pages"])
            ]
            if not compatible:
                compatible = [item for item in plan if item["type"] == qtype]
            if not compatible:
                questions.append(candidate)
                continue

            def fit(item: dict[str, Any]) -> tuple[float, float, float]:
                evidence_tokens = content_tokens(item["evidence"])
                overlap = len(candidate_tokens & evidence_tokens) / max(
                    1, len(candidate_tokens | evidence_tokens)
                )
                skill_match = float(item["skill"] == classified)
                shape_bound = {
                    "application",
                    "analysis",
                    "comparison",
                    "cause_effect",
                    "process_order",
                }
                shape_compatible = float(
                    item["skill"] not in shape_bound or item["skill"] == classified
                )
                return shape_compatible, skill_match, overlap

            item = max(compatible, key=fit)
            update: dict[str, Any] = {
                "blueprint_id": item["id"],
                "source_pages": [page for page in candidate.source_pages if page in item["pages"]]
                or list(item["pages"][:1]),
                "source_quote": item["evidence"],
            }
            if qtype == "mcq":
                update["distractor_rationales"] = [
                    "Same-domain misconception contradicted by the exact source evidence."
                    for _ in range(3)
                ]
            if qtype == "true-false" and candidate.correct_answer.strip().casefold() == "false":
                update["false_statement_basis"] = item["evidence"]
            questions.append(candidate.model_copy(update=update))
        return questions

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["response_model"] is _RawUnderstanding:
            return FakeCompletion(self._understanding_for(kwargs["user_prompt"]))
        return FakeCompletion(self._write(kwargs["user_prompt"]))


def raw(**kwargs) -> _RawCandidate:
    """A fully source-grounded default candidate; override only what matters."""
    defaults = dict(
        id="q",
        type="mcq",
        prompt="What is photosynthesis?",
        options=["Photosynthesis", "Glucose", "Oxygen", "Water"],
        correct_answer="Photosynthesis",
        explanation="The source defines photosynthesis as the conversion of light energy into chemical energy.",
        difficulty="medium",
        source_pages=[1],
    )
    defaults.update(kwargs)
    return _RawCandidate(**defaults)


def make_pool(candidates: list[dict]) -> _RawQuizPool:
    return _RawQuizPool(questions=[raw(**c) for c in candidates])


def default_kwargs(**overrides) -> dict:
    base = dict(
        count=4,
        question_types=["mcq"],
        difficulty="mixed",
        kind="practice",
        language="en",
        seed=1,
        previous_questions=[],
        system_prompt="You are LearnX.",
        # These fixtures are intentionally tiny -- a few sentences chosen to
        # probe one gate each. The production contract (exactly `count`
        # questions or an explicit QuizMaterialError) is asserted separately in
        # test_quiz_exact_count.py against real documents; enforcing it here
        # would just mean every unit test failed for lack of material.
        require_exact_count=False,
    )
    base.update(overrides)
    return base
