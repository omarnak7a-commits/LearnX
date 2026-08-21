from pathlib import Path
import random
src = Path("/home/user/LearnX/backend/tests/fixtures/make_textbook_pdf.py").read_text()
ns = {}; exec(src.split("# A realistic textbook")[0], ns); make_pdf = ns["make_pdf"]
rnd = random.Random(7)

TOPICS = [
 ("Cell Membrane","plasma membrane","a selectively permeable barrier surrounding the cell"),
 ("Diffusion","diffusion","the net movement of particles from higher to lower concentration"),
 ("Osmosis","osmosis","the diffusion of water across a selectively permeable membrane"),
 ("Active Transport","active transport","movement of a substance against its concentration gradient"),
 ("The Nucleus","nucleus","the organelle that stores the cell's genetic material"),
 ("Mitochondria","mitochondria","organelles that generate most of the cell's ATP"),
 ("Ribosomes","ribosome","the structure that assembles amino acids into proteins"),
 ("Golgi Apparatus","Golgi apparatus","the organelle that modifies and packages proteins"),
 ("Lysosomes","lysosome","an organelle containing digestive enzymes"),
 ("Cell Cycle","cell cycle","the ordered sequence of events producing two daughter cells"),
 ("Mitosis","mitosis","nuclear division producing two genetically identical daughter cells"),
 ("Meiosis","meiosis","a division producing four genetically distinct gametes"),
 ("Transcription","transcription","the process in which messenger RNA is copied from DNA"),
 ("Translation","translation","the process by which ribosomes decode messenger RNA"),
 ("Enzymes","enzyme","a protein catalyst that lowers the activation energy of a reaction"),
 ("Denaturation","denaturation","the loss of an enzyme's shape caused by heat or extreme pH"),
 ("Glycolysis","glycolysis","the splitting of glucose into two molecules of pyruvate"),
 ("Citric Acid Cycle","citric acid cycle","the pathway that oxidises pyruvate derivatives"),
 ("Fermentation","fermentation","ATP production that proceeds without oxygen"),
 ("Photosynthesis","photosynthesis","the conversion of light energy into chemical energy"),
 ("Chlorophyll","chlorophyll","the pigment that absorbs light energy inside the chloroplast"),
 ("Homeostasis","homeostasis","the maintenance of a stable internal environment"),
 ("Negative Feedback","negative feedback","a loop that reverses a change toward a set point"),
 ("Receptors","receptor","a protein that binds a signalling molecule and triggers a response"),
 ("Signal Transduction","signal transduction","the relay of a message into the cell interior"),
 ("Tight Junctions","tight junction","a seal that prevents leakage between neighbouring cells"),
 ("Gap Junctions","gap junction","a channel that allows small molecules to pass between cells"),
 ("Chromosomes","chromosome","a condensed structure of DNA that carries genes"),
 ("Genes","gene","a segment of DNA that encodes a functional product"),
 ("Operons","operon","a cluster of genes transcribed together under a single promoter"),
]
VERBS=["regulates","stabilises","controls","limits","supports","coordinates","modulates"]
NOUNS=["the surrounding cytoplasm","adjacent tissue","the internal gradient","nearby organelles",
       "the transport pathway","the surrounding fluid","the reaction rate"]
CAUSE=["Because","Since","Given that","As a consequence of the fact that"]

pages=[["Cell Biology: A Complete Course","","Cover page"]]
for i,(title,term,definition) in enumerate(TOPICS, start=1):
    lines=[f"{i}. {title}",""]
    lines.append(f"{term.capitalize()} is defined as {definition}.")
    lines.append(f"{rnd.choice(CAUSE)} {term} {rnd.choice(VERBS)} {rnd.choice(NOUNS)}, the cell maintains its function.")
    lines.append(f"The {term} differs from {rnd.choice(NOUNS)} in both structure and role.")
    lines.append(f"During this stage the {term} {rnd.choice(VERBS)} {rnd.choice(NOUNS)}.")
    for j in range(34):
        lines.append(f"In {title.lower()}, {rnd.choice(VERBS)} {rnd.choice(NOUNS)} while the {term} "
                     f"interacts with {rnd.choice(NOUNS)} at step {i}.{j}.")
    pages.append(lines)
pages.append(["References","","Alberts B. Molecular Biology of the Cell."])
make_pdf(pages[:32], str(Path(__file__).with_name("textbook_32_pages.pdf")))
print("ok")
