"""Public synthetic seed. No dependency on a private store or training checkpoint."""
from ..indexing.document import Document

DEMO_ROWS = [
    ("japan", "Japan", "## Geography\nJapan is an island country in East Asia. Tokyo is the capital of Japan.\n\n## History\nJapan entered World War II in 1941. The Meiji Constitution was promulgated in 1889.", ["history", "countries"]),
    ("mercury", "Mercury", "Mercury is the closest planet to the Sun. Mercury has no natural satellites.", ["science"]),
    ("cpu", "Central processing unit", "A CPU executes instructions. A central processing unit performs arithmetic and logical operations.", ["technology"]),
    ("lumen", "Lumen console", "The fictional Lumen console launched in 2017. The Lumen console uses a cartridge reader.", ["games"]),
    ("my-telescope", "My telescope specifications", "This is a synthetic personal note. My telescope weighs 7 kg and has an aperture of 90 mm. I purchased my telescope in 2021.", ["personal-style", "specifications"]),
    ("harbor-clinic", "Harbor Clinic payment policy", "Harbor Clinic accepts payment in two equal installments. Harbor Clinic opened in 2019.", ["payments", "clinic"]),
    ("chain", "Cleaning a bicycle chain", "First wipe the bicycle chain with a dry cloth. Then apply degreaser and brush the links. Finally dry the chain and apply lubricant.", ["procedure"]),
    ("aurora", "Aurora Observatory", "Aurora Observatory opened in 2006. It reopened in 2018 after restoration.", ["science", "history"]),
    ("index", "Knowledge index", "## Technology\nRead the [CPU guide](/doc/cpu).\n\n## Countries\nRead [Japan](/doc/japan).\n\n## Science\nRead [Mercury](/doc/mercury).", ["index"]),
    ("long", "Aster expedition notebook", "## Geography\nThe fictional Aster island lies in the northern sea.\n\n## Expedition\nThe Aster expedition began in 2002. The Aster expedition ended in 2005.\n\n## Equipment\nThe expedition used a cedar boat and a brass compass.\n\n## Culture\nThe crew kept a daily journal of songs and recipes.\n\n## Economics\nThe expedition budget was 800 coins.", ["long page"]),
    ("creator", "Demo project creator", "The fictional search project was created by Morgan Vale.", ["short fact"]),
]


def demo_documents():
    docs = [Document(id=s, slug=s, title=t, content=c, keywords=k, status="published") for s, t, c, k in DEMO_ROWS]
    clinic = next(d for d in docs if d.slug == "harbor-clinic")
    clinic.faqs = [{"id": "payments", "question": "Does Harbor Clinic accept installments?",
                   "answer": "Harbor Clinic accepts payment in two equal installments."}]
    return docs


def seed_demo(store):
    docs = demo_documents()
    for doc in docs:
        store.save_document(doc)
    return docs
