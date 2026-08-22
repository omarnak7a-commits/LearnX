"""Adversarial educational-quality scanner for generated quizzes.

The test suite checks that the pipeline *runs*. This checks whether the
questions it produces are any good, by encoding the review criteria as
machine-checkable predicates and running them over every question of every
seed of every document.

Every finding is a DEFECT (must not ship) or a WARN (judgement call, reported
for a human to weigh). Nothing here rejects a question at runtime -- this is a
diagnostic, so a rule that is too strict shows up as a false positive to be
argued with rather than as silent damage to the quiz.

Usage:
    python backend/scripts/adversarial_scan.py
    python backend/scripts/adversarial_scan.py --seeds 1 3 5 7 11
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ai_documents import AIDocumentSource, _extract_pdf  # noqa: E402
from app.services.quiz_blueprints import target_tier  # noqa: E402
from app.services.quiz_grounding import content_tokens  # noqa: E402
from app.services.quiz_pipeline import generate_quiz  # noqa: E402

DEMO_DIR = ROOT / "public" / "demo-files"


class _NoProvider:
    def complete_structured(self, **_kwargs):  # noqa: ANN003
        from app.services.ai_service import AIServiceError

        raise AIServiceError("no provider configured")


# --------------------------------------------------------------------------- #
# Defect predicates
# --------------------------------------------------------------------------- #

#: A word that cannot end a complete English clause.
_TRAILING_FUNCTION_WORD = re.compile(
    r"\b(?:the|a|an|of|to|in|on|for|with|from|by|as|at|into|and|or|but|that|"
    r"which|is|are|was|were|be|been|its|their|those|through|"
    # "it"/"this"/"these" omitted: as a pronoun object each legitimately closes
    # a clause ("...without ever reaching it"). Only a stranded function word
    # signals truncation.
    r"during|before|after|between|within|along|than|such|both|either|neither|"
    r"decides?|determines?|selects?|chooses?|produces?|causes?|requires?|"
    r"allows?|prevents?|affects?|includes?|contains?|uses?|provided)\s*$",
    re.IGNORECASE,
)

#: "The the", "a a", "the a" -- an article collision from name substitution.
_DOUBLE_ARTICLE = re.compile(r"\b(?:the|a|an)\s+(?:the|a|an)\s+", re.IGNORECASE)

#: A clause that switches subject mid-answer.
_CONTRAST_IN_ANSWER = re.compile(
    r",\s+(?:while|whereas|but|although|though|unlike)\s+", re.IGNORECASE
)

#: Metadata / meta-pedagogical subject matter (§6-H).
_META_SUBJECT = re.compile(
    r"\b(?:page|copyright|isbn|publisher|chapter\s+\d|figure\s+\d|table\s+\d|"
    r"students?\s+(?:find|often|frequently|struggle)|header|footer)\b",
    re.IGNORECASE,
)

#: Wording-game stems (§6-F).
_WORDING_GAME = re.compile(
    r"^(?:what\s+correctly\s+completes|which\s+statement\s+correctly\s+means|"
    r"which\s+statement\s+best\s+completes|what\s+is\s+the\s+meaning\s+of)\b",
    re.IGNORECASE,
)

#: Stems the user named explicitly as unacceptable defaults (§15).
_NAMED_BAD_STEMS = (
    "what is response time?",
    "what is the cell?",
    "what is the net force?",
    "explain the role of the program.",
)

#: A concept that is a law/principle cannot "carry out a function" (§15).
_AGENTIVE_STEM = re.compile(
    r"\b(?:carry\s+out\s+its\s+function|works\s+by\s+means\s+of|"
    r"by\s+what\s+mechanism\s+does)\b",
    re.IGNORECASE,
)
_PRINCIPLE_NAME = re.compile(
    r"\b(?:law|rule|principle|theorem|axiom|postulate|equation|formula)\b",
    re.IGNORECASE,
)

#: A "why/how" question answered by a bare noun-phrase list (§7).
_REASON_STEM = re.compile(r"^(?:why|how)\b", re.IGNORECASE)
_FINITE_VERB = re.compile(
    r"\b(?:is|are|was|were|has|have|had|does|do|did|can|will|must|may|"
    r"[a-z]+(?:s|ed|es))\b",
    re.IGNORECASE,
)


def _is_bare_list(text: str) -> bool:
    """True when the text is an enumeration with no verb -- not a reason."""
    if _FINITE_VERB.search(text):
        return False
    return text.count(",") >= 1


def scan_question(question, bp, trace, evidence: str) -> list[tuple[str, str]]:
    """Return [(severity, message)] for one final question."""
    out: list[tuple[str, str]] = []
    prompt = (question.prompt or "").strip()
    answer = (question.correct_answer or "").strip()
    explanation = (question.explanation or "").strip()
    skill = trace.cognitive_skill if trace else ""
    concept = trace.concept if trace else ""

    # -- Grammar / surface integrity ------------------------------------- #
    if _DOUBLE_ARTICLE.search(prompt) or _DOUBLE_ARTICLE.search(answer):
        out.append(("DEFECT", "article collision ('The the ...')"))
    for label, text in (("prompt", prompt), ("answer", answer)):
        if not text:
            continue
        # A question legitimately ends on its verb ("What does FCFS produce?").
        # Only a *declarative* fragment is truncated, so skip interrogatives.
        if label == "prompt" and text.rstrip().endswith("?"):
            continue
        if _TRAILING_FUNCTION_WORD.search(text.rstrip(" .?")):
            out.append(("DEFECT", f"{label} ends mid-phrase: ...{text[-40:]!r}"))
    if prompt and not prompt.endswith(("?", ".", ":")):
        out.append(("DEFECT", f"prompt has no terminal punctuation: {prompt[-30:]!r}"))
    if answer and question.type in {"short-answer", "mcq"} and len(answer.split()) < 2:
        out.append(("WARN", f"answer is a single token: {answer!r}"))

    # -- Answer quality (§7) --------------------------------------------- #
    if question.type != "true-false" and _CONTRAST_IN_ANSWER.search(answer):
        out.append(
            ("DEFECT", "answer carries a contrast clause about another subject")
        )
    if question.type != "true-false" and _REASON_STEM.match(prompt) and _is_bare_list(answer):
        out.append(("DEFECT", f"why/how answered by a bare list: {answer[:60]!r}"))

    # -- Meta / wording games (§6) --------------------------------------- #
    if _META_SUBJECT.search(prompt):
        out.append(("DEFECT", "prompt asks about metadata / meta-pedagogy"))
    if _WORDING_GAME.match(prompt):
        out.append(("DEFECT", "wording-game stem"))
    if prompt.strip().casefold() in _NAMED_BAD_STEMS:
        out.append(("DEFECT", f"named-unacceptable stem: {prompt!r}"))

    # -- Semantic shape (§15) -------------------------------------------- #
    if _AGENTIVE_STEM.search(prompt) and _PRINCIPLE_NAME.search(concept):
        out.append(
            ("DEFECT", f"agentive stem applied to a principle: {concept!r}")
        )

    # -- Explanations (§10) ---------------------------------------------- #
    is_false = answer.strip().casefold() == "false"
    if is_false:
        if "original relationship is correct" in explanation.casefold():
            out.append(("DEFECT", "FALSE answer explained as 'is correct'"))
        elif not re.search(r"\bfalse\b|\bnot\b|\bincorrect\b", explanation, re.I):
            out.append(
                ("DEFECT", "FALSE answer explanation does not explain the falsehood")
            )
    if explanation and not explanation.rstrip().endswith((".", "?", "!")):
        out.append(("DEFECT", "explanation is not a complete sentence"))

    # -- Grounding (§6-A) ------------------------------------------------- #
    ev_tokens = content_tokens(evidence)
    if question.type != "true-false" and answer:
        missing = content_tokens(answer) - ev_tokens
        if missing and len(missing) / max(1, len(content_tokens(answer))) > 0.5:
            out.append(
                ("DEFECT", f"answer largely absent from evidence: {sorted(missing)[:6]}")
            )

    # -- Sentence copying (§6-E) ------------------------------------------ #
    norm_ev = " ".join(evidence.split()).casefold().rstrip(".")
    norm_prompt = " ".join(prompt.split()).casefold().rstrip("?.")
    if norm_prompt and norm_prompt == norm_ev:
        out.append(("DEFECT", "prompt is a verbatim copy of the source sentence"))

    # -- MCQ distractors (§9) --------------------------------------------- #
    if question.type == "mcq":
        options = list(question.options or [])
        if len(options) != 4:
            out.append(("DEFECT", f"MCQ has {len(options)} options"))
        if options.count(answer) != 1:
            out.append(("DEFECT", "MCQ correct answer not present exactly once"))
        norm = [" ".join(o.split()).casefold() for o in options]
        if len(set(norm)) != len(norm):
            out.append(("DEFECT", "MCQ has duplicate options"))
        lengths = [len(o.split()) for o in options]
        if lengths and max(lengths) >= 3 * max(1, min(lengths)):
            out.append(
                ("WARN", f"MCQ length giveaway: option words {sorted(lengths)}")
            )
        has_eq = [bool(re.search(r"[=<>≤≥]", o)) for o in options]
        if any(has_eq) and not all(has_eq):
            if has_eq[options.index(answer)] and sum(has_eq) == 1:
                out.append(("DEFECT", "MCQ notation-vs-prose giveaway"))
        # near-identical options
        for i in range(len(options)):
            for j in range(i + 1, len(options)):
                a, b = content_tokens(options[i]), content_tokens(options[j])
                if a and b:
                    jac = len(a & b) / max(1, len(a | b))
                    if jac >= 0.8:
                        out.append(
                            ("WARN", f"MCQ options {i} and {j} overlap {jac:.2f}")
                        )

    # -- Tier (§12) -------------------------------------------------------- #
    if bp is not None and target_tier(bp) == 3:
        out.append(("DEFECT", "Tier-3 question in final quiz"))

    return out


CORPUS_DIR = ROOT / "backend" / "tests" / "fixtures" / "domain_corpus"


def load_source(doc: Path):
    """Build an AIDocumentSource from a .pdf or a plain-text fixture.

    The cross-domain corpus (history, chemistry, literature, geography) is
    stored as text so the domain-independence sweep is reproducible without a
    PDF toolchain. Both paths feed the identical pipeline.
    """
    if doc.suffix.lower() == ".pdf":
        return _extract_pdf(
            doc.read_bytes(),
            file_id=doc.stem,
            title=doc.stem,
            max_characters=200_000,
            allowed_pages=None,
        )
    # Paginate the fixture so source_pages provenance is exercised the same way
    # a real PDF exercises it, instead of collapsing onto a single page.
    paragraphs = [b.strip() for b in doc.read_text(encoding="utf-8").split("\n\n") if b.strip()]
    per_page = 2
    pages = [paragraphs[i:i + per_page] for i in range(0, len(paragraphs), per_page)]
    text = "\n\n".join(
        f"[Page {n}]\n" + "\n\n".join(block) for n, block in enumerate(pages, start=1)
    )
    return AIDocumentSource(
        file_id=doc.stem,
        title=doc.stem.replace("-", " ").title(),
        text=text,
        page_count=len(pages),
    )


def run(pdf: Path, seed: int, count: int):
    source = load_source(pdf)
    result = generate_quiz(
        _NoProvider(),
        source,
        count=count,
        question_types=["mcq", "true-false", "fill-blank", "short-answer"],
        difficulty="mixed",
        kind="practice",
        language="en",
        seed=seed,
        previous_questions=[],
        system_prompt="Use only the supplied source.",
    )
    return result, inspect_quiz(result)


def inspect_quiz(result) -> list[tuple[str, str, str]]:
    """Every quality finding for one generated quiz.

    Split out of run() so other harnesses judge their output by exactly these
    rules instead of reimplementing them, keeping a single definition of
    "defect" across the project.
    """
    blueprints = {bp.id: bp for bp in (result.blueprints or [])}
    prov = {t.question_id: t for t in (result.provenance or [])}

    findings: list[tuple[str, str, str]] = []
    for index, q in enumerate(result.questions, start=1):
        trace = prov.get(q.id)
        bp = blueprints.get(trace.blueprint_id) if trace else None
        evidence = bp.evidence if bp else ""
        for severity, message in scan_question(q, bp, trace, evidence):
            findings.append((severity, f"Q{index}", message))

    # Quiz-level checks
    tf = [q for q in result.questions if q.type == "true-false"]
    if len(tf) >= 2:
        trues = sum(1 for q in tf if q.correct_answer.strip().casefold() == "true")
        if trues == 0 or trues == len(tf):
            findings.append(
                ("DEFECT", "quiz", f"uniform T/F polarity ({trues}/{len(tf)} True)")
            )
    targets = [t.knowledge_target_id for t in (result.provenance or [])]
    if len(targets) != len(set(targets)):
        findings.append(("DEFECT", "quiz", "duplicate knowledge target"))
    concepts = [t.concept_id for t in (result.provenance or [])]
    dupes = [c for c, n in Counter(concepts).items() if n > 1]
    important = list(result.understanding.important_concepts()) if result.understanding else []
    untested = [c for c in important if c.concept_id not in set(concepts)]
    if dupes and untested:
        findings.append(
            (
                "DEFECT",
                "quiz",
                f"concept repeated {dupes} while {[c.concept_id for c in untested][:3]} untested",
            )
        )
    # Top-ranked concept must be represented (§4)
    if important and important[0].concept_id not in set(concepts):
        findings.append(
            (
                "WARN",
                "quiz",
                f"top concept {important[0].concept_id!r} "
                f"(importance {important[0].importance:.3f}) not tested",
            )
        )
    skills = Counter(t.cognitive_skill for t in (result.provenance or []))
    if skills and max(skills.values()) > max(2, len(result.questions) // 2):
        findings.append(
            ("WARN", "quiz", f"cognitive skill concentration: {dict(skills)}")
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--corpus", action="store_true",
                        help="also scan the cross-domain text corpus")
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 3, 5, 7, 11])
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()

    pdfs = args.pdfs or sorted(DEMO_DIR.glob("*.pdf"))
    if args.corpus and not args.pdfs:
        pdfs = list(pdfs) + sorted(CORPUS_DIR.glob("*.txt"))
    totals = Counter()
    by_message: dict[str, list[str]] = defaultdict(list)

    for pdf in pdfs:
        for seed in args.seeds:
            result, findings = run(pdf, seed, args.count)
            defects = [f for f in findings if f[0] == "DEFECT"]
            warns = [f for f in findings if f[0] == "WARN"]
            totals["questions"] += len(result.questions)
            totals["DEFECT"] += len(defects)
            totals["WARN"] += len(warns)
            tag = f"{pdf.stem[:26]:26s} s{seed:<3d}"
            if defects or warns:
                print(f"{tag} {len(result.questions)}Q  "
                      f"DEFECT={len(defects)} WARN={len(warns)}")
                for sev, where, msg in defects + warns:
                    print(f"      [{sev}] {where}: {msg}")
                    by_message[f"{sev}: {msg.split(':')[0]}"].append(tag)
            else:
                print(f"{tag} {len(result.questions)}Q  clean")

    print()
    print("=" * 78)
    print(f"TOTAL questions scanned : {totals['questions']}")
    print(f"TOTAL defects           : {totals['DEFECT']}")
    print(f"TOTAL warnings          : {totals['WARN']}")
    if by_message:
        print("\nGrouped:")
        for message, tags in sorted(by_message.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(tags):3d}x {message}")
    return 1 if totals["DEFECT"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
