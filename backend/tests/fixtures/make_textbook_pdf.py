"""Build a real multi-page PDF using raw PDF syntax (no third-party deps)."""
import zlib, sys
from pathlib import Path

def esc(s):
    return s.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')

def make_pdf(pages, out):
    objs = {}
    n_pages = len(pages)
    font_id = 3 + n_pages*2
    kids = " ".join(f"{3+i*2} 0 R" for i in range(n_pages))
    objs[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>"
    for i, lines in enumerate(pages):
        pid, cid = 3+i*2, 4+i*2
        objs[pid] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {cid} 0 R >>")
        parts = ["BT", "/F1 11 Tf", "56 730 Td", "14 TL"]
        for ln in lines:
            parts.append(f"({esc(ln)}) Tj")
            parts.append("T*")
        parts.append("ET")
        objs[cid] = ("stream", "\n".join(parts))
    objs[font_id] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    buf = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objs):
        offsets[num] = len(buf)
        val = objs[num]
        if isinstance(val, tuple):
            body = val[1].encode("latin-1")
            buf += f"{num} 0 obj\n<< /Length {len(body)} >>\nstream\n".encode()
            buf += body + b"\nendstream\nendobj\n"
        else:
            buf += f"{num} 0 obj\n{val}\nendobj\n".encode()
    xref = len(buf)
    mx = max(objs)+1
    buf += f"xref\n0 {mx}\n".encode()
    buf += b"0000000000 65535 f \n"
    for num in range(1, mx):
        buf += (f"{offsets[num]:010d} 00000 n \n".encode() if num in offsets
                else b"0000000000 65535 f \n")
    buf += f"trailer\n<< /Size {mx} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(out).write_bytes(bytes(buf))
    return out

# A realistic textbook chapter: title page, TOC, then substantive content.
pages = []
pages.append(["Introduction to Cell Biology", "", "Chapter 3", "",
              "Prepared for first-year undergraduate students", "", "University Press, 2024"])
pages.append(["Contents", "", "3.1 The Cell Membrane .................. 3",
              "3.2 Organelles ......................... 5",
              "3.3 The Cell Cycle ..................... 8",
              "3.4 Protein Synthesis .................. 11",
              "3.5 Cellular Respiration ............... 14"])
body = [
 ("3.1 The Cell Membrane",
  ["The plasma membrane is defined as a selectively permeable barrier that surrounds the cell.",
   "It is composed of a phospholipid bilayer in which proteins are embedded.",
   "Because the bilayer is hydrophobic at its core, small nonpolar molecules cross it freely,",
   "while ions and large polar molecules require transport proteins to pass through."]),
 ("Membrane Transport",
  ["Passive transport is defined as movement of a substance across a membrane without energy input.",
   "Diffusion is the net movement of particles from a region of higher concentration to lower concentration.",
   "Osmosis is defined as the diffusion of water across a selectively permeable membrane.",
   "Active transport, in contrast, requires ATP because it moves substances against their gradient."]),
 ("3.2 Organelles",
  ["The nucleus is defined as the membrane-bound organelle that stores the cell's genetic material.",
   "The nucleolus is a dense region inside the nucleus where ribosomes are assembled.",
   "Mitochondria are organelles that generate most of the cell's ATP through cellular respiration.",
   "Because mitochondria contain their own DNA, they are thought to have originated as bacteria."]),
 ("Endomembrane System",
  ["The rough endoplasmic reticulum is studded with ribosomes and folds newly made proteins.",
   "The smooth endoplasmic reticulum synthesises lipids and detoxifies harmful compounds.",
   "The Golgi apparatus modifies, sorts and packages proteins before they are shipped onward.",
   "Lysosomes contain digestive enzymes that break down worn-out organelles and debris."]),
 ("3.3 The Cell Cycle",
  ["The cell cycle is defined as the ordered sequence of events that produces two daughter cells.",
   "Interphase is the growth stage, divided into the G1, S and G2 phases.",
   "DNA replication occurs during the S phase, so that each chromosome is duplicated before division.",
   "Checkpoints halt the cycle when damage is detected, which prevents faulty cells from dividing."]),
 ("Mitosis",
  ["Mitosis is defined as nuclear division that produces two genetically identical daughter cells.",
   "Prophase begins when chromosomes condense and the nuclear envelope breaks down.",
   "During metaphase the chromosomes align along the equator of the cell.",
   "Anaphase follows, in which sister chromatids are pulled toward opposite poles."]),
 ("Meiosis",
  ["Meiosis is a specialised division that produces four genetically distinct gametes.",
   "Unlike mitosis, meiosis includes two consecutive divisions and one round of DNA replication.",
   "Crossing over during prophase I exchanges segments between homologous chromosomes.",
   "Because of crossing over and independent assortment, meiosis generates genetic variation."]),
 ("3.4 Protein Synthesis",
  ["Transcription is defined as the process in which messenger RNA is copied from a DNA template.",
   "RNA polymerase binds the promoter region and reads the template strand in one direction.",
   "Translation is the process by which ribosomes decode messenger RNA into a chain of amino acids.",
   "Transfer RNA molecules deliver the amino acids that correspond to each codon."]),
 ("Gene Regulation",
  ["A gene is defined as a segment of DNA that encodes a functional product.",
   "An operon is a cluster of genes transcribed together under a single promoter.",
   "Repressor proteins bind the operator and block transcription, which switches the genes off.",
   "Because regulation conserves energy, cells express enzymes only when the substrate is present."]),
 ("3.5 Cellular Respiration",
  ["Cellular respiration is defined as the process that converts glucose into usable ATP.",
   "Glycolysis splits glucose into two molecules of pyruvate in the cytoplasm.",
   "The citric acid cycle oxidises pyruvate derivatives and releases carbon dioxide.",
   "Oxidative phosphorylation uses the electron transport chain to produce most of the ATP."]),
 ("Fermentation",
  ["Fermentation is defined as ATP production that proceeds without oxygen.",
   "Lactic acid fermentation regenerates NAD+ in muscle cells during intense exercise.",
   "Alcoholic fermentation instead produces ethanol and carbon dioxide in yeast.",
   "Because fermentation yields far less ATP than respiration, it is used only when oxygen is scarce."]),
 ("Enzymes",
  ["An enzyme is defined as a protein catalyst that lowers the activation energy of a reaction.",
   "The active site is the region of the enzyme where the substrate binds.",
   "Denaturation occurs when heat or extreme pH destroys the enzyme's three-dimensional shape.",
   "Because shape determines function, a denatured enzyme can no longer bind its substrate."]),
 ("Cell Communication",
  ["A receptor is defined as a protein that binds a signalling molecule and triggers a response.",
   "Signal transduction is the relay of a message from the receptor into the cell interior.",
   "Second messengers such as cyclic AMP amplify the signal inside the cytoplasm.",
   "Because amplification occurs at each step, a few molecules can produce a large response."]),
 ("Transport in Tissues",
  ["Tight junctions are defined as seals that prevent leakage between neighbouring cells.",
   "Desmosomes fasten cells together so that tissues resist mechanical stress.",
   "Gap junctions are channels that allow small molecules to pass directly between cells.",
   "Because gap junctions couple cells electrically, cardiac muscle contracts as a unit."]),
 ("Homeostasis",
  ["Homeostasis is defined as the maintenance of a stable internal environment.",
   "Negative feedback reverses a change and returns the system toward its set point.",
   "Positive feedback amplifies a change, as occurs during blood clotting.",
   "Because most systems must stay stable, negative feedback is far more common."]),
 ("Chapter Summary",
  ["The membrane controls what enters and leaves the cell.",
   "Organelles divide the cell's chemistry into separate compartments.",
   "The cell cycle and mitosis ensure that genetic material is copied accurately.",
   "Respiration and fermentation supply the ATP that all of these processes require."]),
 ("Review Questions",
  ["1. Explain why active transport requires ATP but diffusion does not.",
   "2. Compare mitosis and meiosis in terms of their products.",
   "3. Describe the role of the Golgi apparatus in protein trafficking.",
   "4. Explain how negative feedback maintains homeostasis."]),
 ("Glossary",
  ["Anabolism: the set of reactions that build larger molecules from smaller ones.",
   "Catabolism: the set of reactions that break larger molecules into smaller ones.",
   "Substrate: the reactant upon which an enzyme acts.",
   "Gradient: a difference in concentration across a distance."]),
]
for title, lines in body:
    pages.append([title, ""] + lines)
while len(pages) < 20:
    pages.append(["References", "", "Alberts B. Molecular Biology of the Cell.",
                  "Campbell N. Biology: A Global Approach."])
make_pdf(pages[:20], str(Path(__file__).with_name("textbook_20_pages.pdf")))
print("pages written:", len(pages[:20]))
