# Quiz quality audit — what is actually wrong

Real output, `cell-biology-ch3.pdf`, seed 3, before this round of fixes:

| # | Question | Verdict |
| --- | --- | --- |
| Q1 | Which statement best describes the role of the nucleus? | template |
| Q2 | `_____` refers to the two-stage process of transcription, … | sentence copy |
| Q3 | Into which categories is the endoplasmic reticulum divided? → "exists in two forms" | answer names no categories |
| Q4 | Which statement best describes the role of Translation? | template (2nd) |
| Q5 | Which statement correctly completes the meaning of the Golgi apparatus? | template (3rd) |
| Q6 | Explain the role of the equation. | "equation" is not a concept |
| Q7 | `_____` is defined as a specialized type of cell division … | sentence copy |
| Q8 | Explain the role of the plasma membrane. | template (4th) |

## Diagnosis

1. **Template monoculture.** Four of eight questions are "role of X". The quiz
   tests recognition of a definition, never understanding.
2. **Fill-blank is sentence copying.** Blanking the subject of its own defining
   sentence leaves the whole definition on screen as a give-away.
3. **Higher-order blueprints never survive.** The planner asked for
   application / comparison / cause_effect / analysis slots; the deterministic
   writer cannot express them, so every slot silently collapsed to
   `understanding`. The blueprint's cognitive plan is decorative.
4. **Junk concepts.** "equation" is a generic noun that the term extractor
   promoted to a concept.
5. **Classification answers do not answer.** "exists in two forms" never names
   rough and smooth ER.

## Root cause

The document genuinely supports good questions — it states contrasts
(eukaryotic vs prokaryotic, mitosis vs meiosis), causes ("because it directs
protein synthesis"), and purposes ("used for growth and tissue repair"). The
understanding layer finds the concepts but **discards the relational sentences
that make reasoning questions possible**, and the writer only knows definition
templates.

So the fix is not more filtering. It is:

- extract *relational* evidence (cause, contrast, purpose, mechanism) as
  first-class material, not just definition sentences;
- write questions from that relational material;
- refuse to ship a quiz that is mostly recognition, rather than padding it.
