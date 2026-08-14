"""Tests for deterministic concept extraction and importance scoring."""

from __future__ import annotations

from app.services.quiz_concepts import (
    SourceUnit,
    build_concept_map,
    concept_map_block,
    extract_concepts,
    has_educational_content,
    is_metadata_line,
    is_trivial_concept,
    score_importance,
    split_source_units,
)

BIOLOGY_SOURCE = """[Page 1]
1.1 Introduction to Photosynthesis
Photosynthesis is defined as the process by which green plants convert light energy into chemical energy. This process takes place in the chloroplasts of plant cells. Cellular Respiration is the complementary process that releases energy from glucose.

[Page 2]
2.1 The Light Reactions
The light reactions occur in the thylakoid membranes. Chlorophyll absorbs light energy and splits water molecules, producing oxygen as a byproduct. The light reactions produce ATP and NADPH.

[Page 3]
3.1 The Calvin Cycle
The Calvin cycle is the set of reactions that fix carbon dioxide into glucose. Unlike the light reactions, the Calvin cycle does not require light directly. The relationship between the light reactions and the Calvin cycle is that the products of one fuel the other. The light reactions and the Calvin cycle together convert light energy into chemical energy.

[Page 4]
4.1 Factors Affecting Photosynthesis
Light intensity, carbon dioxide concentration, and temperature all affect the rate of photosynthesis. If light intensity increases, the rate of photosynthesis increases up to a saturation point. Students should compare Metabolic Pathways in plants and animals.
"""

ARABIC_SOURCE = """[Page 1]
الفصل الأول: البناء الضوئي
البناء الضوئي هو العملية التي تحول بها النباتات الطاقة الضوئية إلى طاقة كيميائية. يتم تخزين هذه الطاقة في جزيئات الجلوكوز.

[Page 2]
القسم الثاني: التنفس الخلوي
التنفس الخلوي هو العملية التي تطلق الطاقة من الجلوكوز.
"""


def units(text: str) -> list[SourceUnit]:
    return split_source_units(text)


def test_split_source_units_parses_page_markers() -> None:
    parsed = split_source_units(BIOLOGY_SOURCE)
    assert [u.page for u in parsed] == [1, 2, 3, 4]
    assert all(u.text for u in parsed)
    assert "Photosynthesis" in parsed[0].text


def test_split_source_units_without_markers_falls_back_to_page_one() -> None:
    parsed = split_source_units("Plain text without page markers.")
    assert len(parsed) == 1
    assert parsed[0].page == 1


def test_split_source_units_empty() -> None:
    assert split_source_units("") == []
    assert split_source_units("   \n  ") == []


def test_definition_detection_english() -> None:
    concepts = extract_concepts(units(BIOLOGY_SOURCE))
    definitions = [c for c in concepts if c.kind == "definition"]
    names = [c.name.lower() for c in definitions]
    assert any("photosynthesis" in n for n in names)
    photosynthesis = next(c for c in definitions if "photosynthesis" in c.name.lower())
    assert "light energy" in photosynthesis.evidence or "chemical energy" in photosynthesis.evidence


def test_definition_detection_arabic() -> None:
    concepts = extract_concepts(units(ARABIC_SOURCE))
    definitions = [c for c in concepts if c.kind == "definition"]
    assert definitions
    assert any("البناء الضوئي" in c.name or "التنفس الخلوي" in c.name for c in definitions)


def test_heading_detection_numbered_english() -> None:
    concepts = extract_concepts(units(BIOLOGY_SOURCE))
    headings = [c for c in concepts if c.kind in {"numbered_heading", "heading"}]
    names = [c.name.lower() for c in headings]
    assert any("calvin cycle" in n for n in names)
    assert any("light reactions" in n for n in names)


def test_heading_detection_named_arabic() -> None:
    concepts = extract_concepts(units(ARABIC_SOURCE))
    headings = [c for c in concepts if c.kind in {"numbered_heading", "heading"}]
    assert any("البناء الضوئي" in c.name or "التنفس الخلوي" in c.name for c in headings)


def test_multiword_term_detection() -> None:
    concepts = extract_concepts(units(BIOLOGY_SOURCE))
    multiword = [c for c in concepts if c.kind == "multiword_term"]
    names = [c.name.lower() for c in multiword]
    assert any("metabolic pathway" in n for n in names)
    # "Cellular Respiration is the complementary process..." is also a
    # multi-word term, even though it is classified as a definition.
    all_names = [c.name.lower() for c in concepts]
    assert any("cellular respiration" in n for n in all_names)


def test_repeated_concept_detection() -> None:
    concepts = extract_concepts(units(BIOLOGY_SOURCE))
    repeated = [c for c in concepts if c.kind == "repeated_term"]
    assert repeated
    names = [c.name.lower() for c in repeated]
    assert any("light reaction" in n for n in names)


def test_metadata_lines_rejected() -> None:
    assert is_metadata_line("ISBN 978-0-12-345678-9")
    assert is_metadata_line("Word count: 1234")
    assert is_metadata_line("Page 4")
    assert is_metadata_line("42")
    assert is_metadata_line("Copyright 2026 All rights reserved")
    assert is_metadata_line("https://example.com/doc.pdf")
    assert not is_metadata_line("Photosynthesis is defined as a process.")


def test_trivial_concepts_rejected() -> None:
    assert is_trivial_concept("42")
    assert is_trivial_concept("ISBN 978-0-12-345678-9")
    assert is_trivial_concept("Page 3")
    assert is_trivial_concept("Introduction")
    assert is_trivial_concept("Conclusion")
    assert is_trivial_concept("the")
    assert not is_trivial_concept("Photosynthesis")
    assert not is_trivial_concept("Cellular Respiration")


def test_extraction_ignores_page_numbers_and_metadata() -> None:
    noisy = "[Page 1]\n42\nISBN 978-0-12-345678-9\nWord count: 500\nPhotosynthesis is defined as the conversion of light into chemical energy.\n"
    concepts = extract_concepts(units(noisy))
    for c in concepts:
        assert not c.name.strip().isdigit()
        assert "isbn" not in c.name.lower()
        assert "word count" not in c.name.lower()


def test_importance_scoring_prefers_definitions_over_repeated_terms() -> None:
    concepts = score_importance(extract_concepts(units(BIOLOGY_SOURCE)))
    definitions = [c for c in concepts if c.kind == "definition"]
    repeated = [c for c in concepts if c.kind == "repeated_term"]
    assert definitions and repeated
    best_definition = max(c.importance for c in definitions)
    best_repeated = max(c.importance for c in repeated)
    assert best_definition >= best_repeated


def test_importance_scoring_rewards_repetition_and_spread() -> None:
    concepts = score_importance(extract_concepts(units(BIOLOGY_SOURCE)))
    light = next(
        (c for c in concepts if c.kind == "repeated_term" and "light reaction" in c.name.lower()),
        None,
    )
    assert light is not None
    assert light.frequency >= 2
    assert len(set(light.pages)) >= 2
    assert light.importance >= 0.15
    assert any("repeated" in reason for reason in light.reasons)
    assert any("spans" in reason for reason in light.reasons)


def test_importance_is_transparent_and_bounded() -> None:
    concepts = score_importance(extract_concepts(units(BIOLOGY_SOURCE)))
    for concept in concepts:
        assert 0.0 <= concept.importance <= 1.0
    assert concepts == sorted(concepts, key=lambda c: c.importance, reverse=True)


def test_concept_map_block_renders_top_concepts() -> None:
    concepts = build_concept_map(units(BIOLOGY_SOURCE))
    block = concept_map_block(concepts, limit=5)
    assert "Photosynthesis" in block or "photosynthesis" in block
    assert "importance=" in block
    assert "why important" in block


def test_sparse_educational_source_produces_section_fallback() -> None:
    units = [SourceUnit(page=1, text="Mitosis produces two genetically identical daughter cells.")]
    assert has_educational_content(units)
    concepts = build_concept_map(units)
    assert concepts
    assert any(concept.kind == "source_section" for concept in concepts)
    assert "Mitosis produces" in concepts[0].evidence


def test_metadata_or_trivial_text_is_not_educational_content() -> None:
    assert not has_educational_content([SourceUnit(page=1, text="Oxford University Press Third Edition")])
    assert not has_educational_content([SourceUnit(page=1, text="Very short text.")])


def test_empty_source_produces_no_concepts() -> None:
    assert build_concept_map([]) == []
