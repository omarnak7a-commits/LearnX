"""Adversarial regressions for backend candidate hard gates."""

from app.services.quiz_blueprints import QuestionBlueprint
from app.services.quiz_pipeline import _RawCandidate, normalize_blueprinted_candidate
from app.services.quiz_scoring import content_tokens


# The old content-map categories map onto study-map knowledge types.
_KNOWLEDGE_TYPE_ALIASES = {
    "core_concept": "definition",
    "important_definition": "definition",
    "process_mechanism": "process",
    "formula_rule": "principle",
}


def _blueprint(
    *,
    question_type: str,
    evidence: str,
    category: str = "core_concept",
    skill: str = "understanding",
    concept: str = "Recursion",
) -> QuestionBlueprint:
    knowledge_type = _KNOWLEDGE_TYPE_ALIASES.get(category, category)
    concept_id = concept.lower().replace(" ", "-")
    return QuestionBlueprint(
        id="bp-1",
        concept_id=concept_id,
        concept=concept,
        knowledge_target_id=f"{concept_id}--{skill}",
        knowledge_target=evidence,
        knowledge_type=knowledge_type,
        cognitive_skill=skill,
        question_type=question_type,
        difficulty="medium",
        importance=0.92,
        evidence=evidence,
        pages=(1,),
    )


def _normalize(raw: _RawCandidate, blueprint: QuestionBlueprint, page: str):
    return normalize_blueprinted_candidate(
        raw,
        index=0,
        blueprints={blueprint.id: blueprint},
        page_count=1,
        included_pages={1},
        page_text={1: page},
        vocab=content_tokens(page),
    )


def test_mcq_accepts_parallel_source_domain_distractors() -> None:
    evidence = "A base case stops recursive calls before another smaller problem is created."
    page = (
        evidence
        + " A recursive case reduces the problem. A loop repeats an operation. "
        + "A stack frame records an active call."
    )
    blueprint = _blueprint(question_type="mcq", evidence=evidence)
    raw = _RawCandidate.model_validate(
        {
            "id": "q1",
            "blueprint_id": "bp-1",
            "type": "mcq",
            "prompt": "Which recursion component stops recursive calls?",
            "options": ["A base case", "A recursive case", "A loop", "A stack frame"],
            "correct_answer": "A base case",
            "explanation": evidence,
            "difficulty": "hard",
            "source_pages": [1],
            "source_quote": evidence,
            "distractor_rationales": [
                "A recursive case instead reduces the current problem.",
                "A loop repeats work but is not the recursion stopping condition.",
                "A stack frame records a call rather than stopping recursion.",
            ],
        }
    )

    record = _normalize(raw, blueprint, page)
    assert record is not None
    # Provider difficulty is not trusted; the planned level wins.
    assert record.question.difficulty == "medium"


def test_mcq_rejects_absurd_or_out_of_domain_distractors() -> None:
    evidence = "A base case stops recursive calls before another smaller problem is created."
    page = evidence + " A recursive case reduces the problem."
    blueprint = _blueprint(question_type="mcq", evidence=evidence)
    raw = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "mcq",
            "prompt": "Which recursion component stops recursive calls?",
            "options": ["A base case", "A purple bicycle", "Ocean weather", "A musical sandwich"],
            "correct_answer": "A base case",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
            "distractor_rationales": ["Not a recursion component."] * 3,
        }
    )
    assert _normalize(raw, blueprint, page) is None


def test_answer_cannot_append_an_unsupported_number_or_claim() -> None:
    evidence = "Increasing light intensity increases the photosynthesis rate until saturation."
    blueprint = _blueprint(
        question_type="short-answer",
        evidence=evidence,
        category="cause_effect",
        skill="cause_effect",
        concept="Light intensity",
    )
    raw = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "Why does light intensity affect the photosynthesis rate?",
            "correct_answer": "The photosynthesis rate increases by exactly 50 percent.",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
        }
    )
    assert _normalize(raw, blueprint, evidence) is None


def test_explanation_needs_more_than_one_shared_topic_word() -> None:
    evidence = "Increasing light intensity increases the photosynthesis rate until saturation."
    blueprint = _blueprint(
        question_type="short-answer",
        evidence=evidence,
        category="cause_effect",
        skill="cause_effect",
        concept="Light intensity",
    )
    raw = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "Why does light intensity affect the photosynthesis rate?",
            "correct_answer": "The photosynthesis rate increases until saturation.",
            "explanation": "Light intensity proves that fertilizer always doubles desert crops overnight.",
            "source_pages": [1],
            "source_quote": evidence,
        }
    )
    assert _normalize(raw, blueprint, evidence) is None


def test_fill_blank_accepts_a_key_term_but_rejects_a_generic_blank() -> None:
    evidence = "A base case stops recursion by returning without another recursive call."
    blueprint = _blueprint(
        question_type="fill-blank",
        evidence=evidence,
        category="important_definition",
        skill="understanding",
        concept="Base case",
    )
    valid = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "fill-blank",
            "prompt": "A _____ stops recursion by returning without another recursive call.",
            "correct_answer": "base case",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
        }
    )
    assert _normalize(valid, blueprint, evidence) is not None

    generic = valid.model_copy(
        update={
            "prompt": "A base case stops recursion by using a _____.",
            "correct_answer": "process",
        }
    )
    assert _normalize(generic, blueprint, evidence) is None


def test_false_statement_requires_a_grounded_correction_basis() -> None:
    evidence = "Increasing light intensity increases photosynthesis until a saturation point."
    blueprint = _blueprint(
        question_type="true-false",
        evidence=evidence,
        category="cause_effect",
        skill="cause_effect",
        concept="Light intensity",
    )
    valid = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "true-false",
            "prompt": "Because light intensity increases, photosynthesis decreases until a saturation point.",
            "options": ["True", "False"],
            "correct_answer": "False",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
            "false_statement_basis": evidence,
        }
    )
    assert _normalize(valid, blueprint, evidence) is not None

    invented_basis = valid.model_copy(
        update={"false_statement_basis": "Astronauts discovered photosynthesis on Mars."}
    )
    assert _normalize(invented_basis, blueprint, evidence) is None


def test_true_false_rejects_unrelated_assertion_with_one_shared_term() -> None:
    evidence = "Increasing light intensity increases photosynthesis until a saturation point."
    blueprint = _blueprint(
        question_type="true-false",
        evidence=evidence,
        category="cause_effect",
        skill="cause_effect",
        concept="Light intensity",
    )
    raw = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "true-false",
            "prompt": "Because astronauts visited Mars, photosynthesis was invented there in 1969.",
            "options": ["True", "False"],
            "correct_answer": "False",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
            "false_statement_basis": evidence,
        }
    )
    assert _normalize(raw, blueprint, evidence) is None


def test_application_scenario_is_meaningful_and_evidence_bound() -> None:
    evidence = "If light intensity increases, the photosynthesis rate increases until a saturation point."
    blueprint = _blueprint(
        question_type="short-answer",
        evidence=evidence,
        category="cause_effect",
        skill="application",
        concept="Light intensity",
    )
    valid = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "Suppose light intensity increases before saturation. Predict what happens to the photosynthesis rate.",
            "correct_answer": "The photosynthesis rate increases.",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
        }
    )
    assert _normalize(valid, blueprint, evidence) is not None

    invented = valid.model_copy(
        update={
            "prompt": "Suppose fertilizer vanishes from a desert greenhouse overnight. Predict the photosynthesis rate."
        }
    )
    assert _normalize(invented, blueprint, evidence) is None

    recall_evidence = "A base case stops recursion by returning without another recursive call."
    recall_blueprint = _blueprint(
        question_type="short-answer",
        evidence=recall_evidence,
        category="important_definition",
        skill="application",
        concept="Base case",
    )
    disguised_recall = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "Suppose a base case stops recursion. What is a base case?",
            "correct_answer": "A base case stops recursion",
            "explanation": recall_evidence,
            "source_pages": [1],
            "source_quote": recall_evidence,
        }
    )
    assert _normalize(disguised_recall, recall_blueprint, recall_evidence) is None


def test_source_quote_and_pages_must_match_the_planned_evidence() -> None:
    evidence = "A base case stops recursion by returning without another recursive call."
    blueprint = _blueprint(question_type="short-answer", evidence=evidence, concept="Base case")
    raw = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "How does a base case stop recursion?",
            "correct_answer": "By returning without another recursive call.",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": "A base case sometimes makes the program faster.",
        }
    )
    assert _normalize(raw, blueprint, evidence) is None


def test_analysis_blueprint_rejects_recall_disguised_as_higher_order() -> None:
    evidence = "A base case stops recursion by returning without another recursive call."
    blueprint = _blueprint(
        question_type="short-answer",
        evidence=evidence,
        category="core_concept",
        skill="analysis",
        concept="Base case",
    )
    valid = _RawCandidate.model_validate(
        {
            "blueprint_id": "bp-1",
            "type": "short-answer",
            "prompt": "Which conclusion about a base case is best supported?",
            "correct_answer": "A base case stops recursion by returning without another recursive call.",
            "explanation": evidence,
            "source_pages": [1],
            "source_quote": evidence,
        }
    )
    assert _normalize(valid, blueprint, evidence) is not None

    disguised_recall = valid.model_copy(update={"prompt": "What is a base case?"})
    assert _normalize(disguised_recall, blueprint, evidence) is None
