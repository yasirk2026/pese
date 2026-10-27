"""Fresh, unreviewed everyday English diagnostic proposals, never training data.

Fictional names/facts are authored as specifications here, without model labels.
This is an OPEN diagnostic. A human must approve a separate protected packet.
"""


def draft():
    # family, category, two natural queries, supporting fact, confusing alternative,
    # expected extract (None = an evidence-based answer cannot be established).
    rows = [
        ("keys", "everyday", ["Where did I leave my spare key?", "Where is the extra key?"],
         "The spare house key is in the blue cup beside the kitchen sink.",
         "The spare car key is in the red box in the garage.", "in the blue cup beside the kitchen sink"),
        ("appointment", "dates", ["When is my next dentist visit?", "What day do I see the dentist?"],
         "The next dentist appointment is on 6 November 2026 at 10 am.",
         "The previous dentist appointment was on 6 November 2025 at 10 am.", "6 November 2026"),
        ("bread", "cause", ["Why did Omar stop buying that bread?", "What made Omar choose different bread?"],
         "Omar stopped buying the bakery bread because it contained sesame. Omar is allergic to sesame.",
         "Omar stopped buying bakery milk because it was too expensive.", "because it contained sesame"),
        ("charger", "hard_negative", ["Which charger does my camera need?", "What cable can charge my camera?"],
         "My camera needs a USB-C charger. My phone uses a different charger.",
         "My old camera used a micro-USB charger. I no longer own that camera.", "USB-C"),
        ("bus", "negation", ["Does bus 14 run on Sunday?", "Can I take the number 14 bus on Sundays?"],
         "Bus 14 runs Monday to Saturday. Bus 14 does not run on Sunday.",
         "Bus 41 runs every Sunday. Bus 41 stops outside the library.", "does not run on Sunday"),
        ("refund", "procedure", ["How do I return the broken kettle?", "What should I do to get the kettle refunded?"],
         "To return the broken kettle, take the kettle and receipt to the shop within 30 days.",
         "To clean a kettle, unplug it and wipe the outside with a damp cloth.", "take the kettle and receipt to the shop within 30 days"),
        ("train", "conflict", ["What time does the last train leave?", "When is the final train?"],
         "The station notice says the last train leaves at 9 pm. The notice has no date.",
         "Another station notice says the last train leaves at 10 pm. This notice has no date either.", None),
        ("address", "changed_information", ["Where does Farah live now?", "What is Farah's current address?"],
         "As of 2 October 2026, Farah lives at 18 Maple Street. This replaces her old address.",
         "In 2024, Farah lived at 7 Lake Road. This address is no longer current.", "18 Maple Street"),
        ("bike", "cross_sentence", ["Why can't Nabil ride his bike today?", "What is stopping Nabil from cycling?"],
         "Nabil found a crack in his bicycle frame this morning. He will not ride it until the frame is repaired.",
         "Nabil washed his bicycle yesterday. His friend cannot ride because of rain.", "a crack in his bicycle frame"),
        ("nickname", "preference", ["Does Hana like being called Sunny?", "Is Hana happy with the nickname Sunny?"],
         "Hana said, 'Please do not call me Sunny. I prefer Hana.'",
         "Hana's brother likes the nickname Sunny. He asked his friends to use it.", "Please do not call me Sunny"),
        ("delivery", "missing_evidence", ["When will my parcel arrive?", "What day is my package due?"],
         "The parcel was sent on Tuesday. The tracking page does not give an arrival date.",
         "A different parcel arrived last Friday. That parcel belonged to a neighbour.", None),
        ("identity", "identity", ["Who is Leena?", "Tell me who Leena is."],
         "Leena is the volunteer who runs the book club at the local library.",
         "Lina is the mechanic who repairs cars near the library.", "the volunteer who runs the book club"),
    ]
    documents = []
    questions = []
    for family, category, wording, fact, negative, answer in rows:
        for suffix, content in (("a", fact), ("b", negative)):
            documents.append({"id": family + "-" + suffix, "family": family, "title": family.capitalize() + " note " + suffix,
                              "content": content})
        for i, question in enumerate(wording):
            questions.append({"id": family + str(i), "group": family, "category": category, "question": question,
                              "expected_answer": None, "answer_reviewed": False,
                              "proposed_expected_answer": answer,
                              "proposed_grades": {family + "-a": 2 if answer else 1, family + "-b": 1 if answer is None else 0},
                              "grades": None})
    ids = [d["id"] for d in documents]
    for q in questions:
        q["proposed_grades"] = {key: q["proposed_grades"].get(key, 0) for key in ids}
    return {"format": "pese-first-contact-evaluation", "version": 1,
            "role": "open_diagnostic_never_train", "provenance": "assistant_authored_fictional_specifications_not_human_review",
            "human_review": None, "documents": documents, "questions": questions}
