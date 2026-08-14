"""Regression tests for deterministic PDF-boilerplate detection and source cleaning.

The production bug this guards against: AI exams that ask questions about PDF
chrome such as ``"Copyright © 2020, _____ and/or its affiliates."`` instead of
educational content.
"""

from __future__ import annotations

from app.schemas.ai import AIQuizQuestion
from app.services.quiz_boilerplate import (
    boilerplate_hits,
    clean_source_units,
    cleaned_source_block,
    is_boilerplate_line,
    is_boilerplate_question,
    is_boilerplate_text,
    is_valid_fill_blank,
    question_boilerplate_fields,
    repeated_line_keys,
)
from app.services.quiz_concepts import SourceUnit, split_source_units

FOOTER_SOURCE = """[Page 1]
Oracle Database Documentation
1.1 Introduction to Databases
A database is defined as an organized collection of structured data. Databases store information in tables with rows and columns.

[Page 2]
Oracle Database Documentation
2.1 Tables and Rows
A table is defined as a set of rows that share the same columns.

[Page 3]
Oracle Database Documentation
3.1 Queries
A query is defined as a request for data from a database.
Copyright © 2020, Oracle and/or its affiliates. All rights reserved.
"""


def question(
    *,
    qtype: str = "mcq",
    prompt: str = "What is a database?",
    options: list[str] | None = None,
    correct: str = "An organized collection of structured data",
    explanation: str = "The source defines a database as an organized collection of structured data.",
) -> AIQuizQuestion:
    if options is None:
        options = ["An organized collection of structured data", "A text file", "A network cable", "A spreadsheet cell"]
    return AIQuizQuestion(
        id="q1",
        type=qtype,  # type: ignore[arg-type]
        prompt=prompt,
        options=options,
        correct_answer=correct,
        explanation=explanation,
        difficulty="medium",  # type: ignore[arg-type]
        source_pages=[1],
    )


# --------------------------------------------------------------------------- #
# The exact production bug
# --------------------------------------------------------------------------- #

def test_copyright_fill_blank_example_is_boilerplate() -> None:
    assert is_boilerplate_text("Copyright © 2020, _____ and/or its affiliates.")
    assert is_boilerplate_text("Copyright © 2020, Oracle and/or its affiliates. All rights reserved.")
    hits = boilerplate_hits("Copyright © 2020, _____ and/or its affiliates.")
    assert "copyright" in hits and "copyright-symbol" in hits


def test_copyright_question_is_flagged_in_prompt_field() -> None:
    q = question(qtype="fill-blank", prompt="Copyright © 2020, _____ and/or its affiliates.", correct="Oracle", options=None)
    assert question_boilerplate_fields(q) == ["prompt"]
    assert is_boilerplate_question(q)


# --------------------------------------------------------------------------- #
# Pattern coverage (English)
# --------------------------------------------------------------------------- #

def test_all_rights_reserved_is_boilerplate() -> None:
    assert is_boilerplate_text("All rights reserved.")


def test_isbn_doi_url_email_are_boilerplate() -> None:
    assert is_boilerplate_text("ISBN 978-0-12-345678-9")
    assert is_boilerplate_text("doi: 10.1038/s41586-020-2649-2")
    assert is_boilerplate_text("Visit https://example.com/docs for more information.")
    assert is_boilerplate_text("Contact support@example.com for help.")


def test_trademark_symbols_are_boilerplate() -> None:
    assert is_boilerplate_text("Oracle® and Java™ are trademarks of Oracle.")


def test_publisher_and_licensing_text_is_boilerplate() -> None:
    assert is_boilerplate_text("Published by Oxford University Press.")
    assert is_boilerplate_text("This material is licensed under a Creative Commons license.")
    assert is_boilerplate_text("Reproduced with permission of the publisher.")
    assert is_boilerplate_text("No part of this publication may be reproduced without permission.")


def test_page_folio_artifacts_are_boilerplate() -> None:
    assert is_boilerplate_text("Page 3 of 12")
    assert is_boilerplate_text("See pages 10-15 for more details.")


def test_arabic_legal_boilerplate() -> None:
    assert is_boilerplate_text("جميع الحقوق محفوظة للناشر")
    assert is_boilerplate_text("حقوق الطبع والنشر محفوظة لدار النشر")


# --------------------------------------------------------------------------- #
# Educational content must NOT be flagged
# --------------------------------------------------------------------------- #

def test_educational_text_is_not_boilerplate() -> None:
    assert not is_boilerplate_text("Photosynthesis converts light energy into chemical energy.")
    assert not is_boilerplate_text("The cell membrane is selectively permeable to small molecules.")
    assert not is_boilerplate_text("A database is defined as an organized collection of structured data.")
    assert not is_boilerplate_text("ما هي وظيفة البناء الضوئي؟")
    # "do not reproduce" is a legitimate biology statement, not a legal notice.
    assert not is_boilerplate_text("Bacteria do not reproduce by mitosis.")
    assert not is_boilerplate_line("Bacteria do not reproduce by mitosis.")


def test_clean_question_is_not_flagged() -> None:
    assert question_boilerplate_fields(question()) == []


# --------------------------------------------------------------------------- #
# Line-level source cleaning
# --------------------------------------------------------------------------- #

def test_boilerplate_lines_are_detected() -> None:
    assert is_boilerplate_line("Copyright © 2020, Oracle and/or its affiliates. All rights reserved.")
    assert is_boilerplate_line("All rights reserved.")
    assert is_boilerplate_line("ISBN 978-0-12-345678-9")
    assert is_boilerplate_line("Page 3 of 12")
    assert is_boilerplate_line("42")
    assert is_boilerplate_line("  ")
    assert is_boilerplate_line("-----")
    assert not is_boilerplate_line("A database is defined as an organized collection of structured data.")


def test_repeated_header_footer_keys_detected_across_pages() -> None:
    units = split_source_units(FOOTER_SOURCE)
    keys = repeated_line_keys(units)
    assert "oracle database documentation" in keys
    # The footer appears on only one page here, so it must be caught by the
    # boilerplate-line detector instead. A digit-varying footer is caught by
    # the repeated-line keys (digit-insensitive).
    page_folios = split_source_units("[Page 1]\ncontent one\nPage 1 of 3\n\n[Page 2]\ncontent two\nPage 2 of 3")
    keys = repeated_line_keys(page_folios)
    assert "page # of #" in keys


def test_clean_source_units_removes_boilerplate_and_repeated_headers() -> None:
    units = split_source_units(FOOTER_SOURCE)
    cleaned = clean_source_units(units)
    assert len(cleaned) == 3
    for unit in cleaned:
        assert "Oracle Database Documentation" not in unit.text  # repeated header
        assert "©" not in unit.text
        assert "all rights reserved" not in unit.text.lower()
    # Educational content survives on every page.
    assert "database is defined" in cleaned[0].text
    assert "table is defined" in cleaned[1].text
    assert "query is defined" in cleaned[2].text


def test_clean_source_units_preserves_flattened_educational_page() -> None:
    # Exact production shape: PDF extraction flattened body + footer into one
    # physical row. The old atomic line filter discarded all lesson content.
    flattened = (
        "[Page 1]\nPhotosynthesis converts light energy into chemical energy. "
        "Chlorophyll absorbs photons in the thylakoid membrane. "
        "Copyright © 2020, Example Press. All rights reserved. Page 1 of 1"
    )
    cleaned = clean_source_units(split_source_units(flattened))
    assert len(cleaned) == 1
    assert "Photosynthesis converts" in cleaned[0].text
    assert "Chlorophyll absorbs" in cleaned[0].text
    assert "Copyright" not in cleaned[0].text
    assert "©" not in cleaned[0].text


def test_clean_source_units_drops_all_boilerplate_pages() -> None:
    boilerplate_only = "[Page 1]\nCopyright © 2020, Oracle and/or its affiliates. All rights reserved.\n\n[Page 2]\nAll rights reserved.\nPrinted in the USA.\nOxford University Press\nThird Edition"
    assert clean_source_units(split_source_units(boilerplate_only)) == []


def test_cleaned_source_block_matches_prompt_block_shape() -> None:
    units = clean_source_units(split_source_units(FOOTER_SOURCE))
    block = cleaned_source_block(units, title="DB Notes", page_count=3)
    assert "<source title='DB Notes' pages=3>" in block
    assert "</source>" in block
    assert "[Page 1]" in block and "[Page 3]" in block
    assert "©" not in block
    assert "Oracle Database Documentation" not in block


# --------------------------------------------------------------------------- #
# Fill-in-the-blank validation
# --------------------------------------------------------------------------- #

def test_fill_blank_requires_a_blank_marker() -> None:
    assert not is_valid_fill_blank("What is a database?", "An organized collection of data")
    assert is_valid_fill_blank("A database is an organized collection of _____.", "structured data")


def test_fill_blank_rejects_boilerplate_answers() -> None:
    # The prompt-level copyright check lives in normalize_candidate; the
    # fill-blank validator itself rejects boilerplate ANSWERS.
    assert not is_valid_fill_blank("The notice says _____.", "All rights reserved")
    assert not is_valid_fill_blank("The publisher is _____.", "Published by Oxford")


def test_fill_blank_rejects_empty_or_symbol_only_answers() -> None:
    assert not is_valid_fill_blank("The term is _____.", "")
    assert not is_valid_fill_blank("The term is _____.", "©")
