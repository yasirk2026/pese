"""Phase 2E development regression corpus. Public, inspected, NEVER a blind set.

Synthetic facts intentionally disagree with familiar historical/seed examples.
Cases test relationships rather than mere topic co-occurrence.
"""
from engine.indexing.document import Document


def documents():
    rows = [
        ("clinic", "Cedar Clinic", "Cedar Clinic provides therapy online. It operates across Nepal. Mina joined Cedar Clinic in April 2019. Appointments can be booked online.",
         [{"id": "staff", "question": "When did Mina join Cedar Clinic?", "answer": "Mina joined Cedar Clinic in April 2019."}]),
        ("timeline", "Orion Republic chronology", "Orion adopted a constitution in 1821. Orion annexed Delta in 1843. Orion annexed Kappa in 1862. Orion invaded Lumen in 1874. Orion entered the Northern War in 1896. Orion surrendered in 1907. Occupation of Orion ended in 1918.", []),
        ("people", "Alpha Labs leadership", "Ali founded Alpha Labs in 2020. Sara became CEO in 2022. Hamza joined Alpha Labs as CTO in 2023.", []),
        ("payments", "Marble Shop payment methods", "Marble Shop accepts credit cards. Marble Shop does not accept cryptocurrency. Installment payments are currently unavailable at Marble Shop. Bank transfer is supported by Marble Shop.", []),
        ("attributes", "Atlas bicycle specifications", "The Atlas bicycle weighs 12kg. The Atlas bicycle uses hydraulic disc brakes. Its frame is aluminum. The Atlas bicycle cost Rs 85,000.", []),
        ("split", "Juniper Studio fees", "Clients of Juniper Studio may divide the fee into two equal installments.", []),
        ("prices", "Museum tickets", "Adult admission at Slate Museum costs 700 rupees. Child admission costs 250 rupees. Student admission costs 400 rupees.", []),
        ("locations", "Research offices", "Aster Research is located in Quito. Boreal Research is located in Lima. Cygnus Research is located in Suva.", []),
        ("negated", "Vela launch status", "Vela did not launch in 2011. Vela launched in 2014.", []),
        ("conflict", "Nacre opening records", "Nacre opened in 1999. Nacre opened in 2003. The archive does not resolve the discrepancy.", []),
        ("cross", "Meridian archive", "Meridian hired a curator.\n\nHer name is Tala.\n\nShe started in 2008.", []),
        ("short", "Quartz launch", "Quartz launched in 2016.", []),
        ("long", "River engineering handbook", ("Water flow is measured with instruments and checked against seasonal records. " * 30) + "\n\nThe Sable dam opened in 1983. It generates electricity for nearby villages.\n\n" + ("Engineers inspect the structure and maintain careful records of repairs. " * 20), []),
        ("spam", "Quartz launched date bargain", "Quartz launched date " * 70 + "Quartz launched in 2099.", []),
        ("tech", "Firebase hydration notes", "Firebase stores application records. Hydration attaches interactive behavior to server-rendered markup. Psychology studies cognition. Bicycle maintenance includes checking brakes.", []),
        ("acronym", "Central processing unit", "A CPU is a central processing unit. The central processing unit executes instructions.", []),
        ("synonym", "Transport guide", "A bicycle is a pedal-powered vehicle. A bike can be used for commuting. A cycle has two wheels.", []),
        ("topic", "Velvet company news", "Velvet sells notebooks. Velvet hired Anika in 2017. Velvet does not publish its revenue or pricing.", []),
        ("other-entity", "Cobalt founding", "Tara founded Cobalt Labs in 2015. Tara joined Alpha Labs as an adviser in 2024.", []),
        ("technical", "Semaphore reference", "A semaphore coordinates concurrent access. A semaphore counter records available permits. Threads acquire semaphore permits before entering the protected region. Semaphore release returns a permit to the counter.", []),
        ("faq", "Pine Library", "Pine Library provides books to local readers.", [{"id":"hours", "question":"When does Pine Library open?", "answer":"Pine Library opens at 9am."}, {"id":"cards", "question":"Does Pine Library offer membership cards?", "answer":"Pine Library offers membership cards for readers."}]),
        ("markdown", "Delta lab tools", "## Tools\n\nDelta lab uses **microscopes** and [spectrometers](/doc/technical) for analysis.", []),
        ("dates", "Aquila observatory", "Aquila construction began in 1961, and Aquila opened in 1968. Aquila closed in 1994 and reopened in 2001.", []),
    ]
    result = [Document(id=s, slug=s, title=t, content=c, faqs=f, created_at="2020-01-01T00:00:00Z", updated_at="2020-01-01T00:00:00Z") for s,t,c,f in rows]
    # Authority cannot make a page about the wrong predicate correct.
    for n in range(5):
        result.append(Document(id=f"hub-{n}", slug=f"hub-{n}", title=f"Archive directory {n}", content="This directory connects readers with the Quartz bargain archive and transport notes.", internal_links=["spam", "synonym"]))
    return result


# query, source, answer substring (None means abstain), category, evidence substring
CASES = [
    ("Does Cedar Clinic offer installment payments?", "clinic", None, "topic_not_answer", None),
    ("When did Mina join Cedar Clinic?", "clinic", "April 2019", "faq", "April 2019"),
    ("Where does Cedar Clinic operate?", "clinic", "Nepal", "location", "Nepal"),
    ("Can appointments be booked online?", "clinic", "booked online", "yesno", "booked online"),
    ("Does Cedar Clinic offer flexible payments?", "clinic", None, "faq_wrong_predicate", None),
    ("When did Orion adopt a constitution?", "timeline", "1821", "multiple_dates", "1821"),
    ("When did Orion annex Delta?", "timeline", "1843", "multiple_dates", "1843"),
    ("When did Orion annex Kappa?", "timeline", "1862", "multiple_dates", "1862"),
    ("When did Orion invade Lumen?", "timeline", "1874", "multiple_dates", "1874"),
    ("When did Orion enter the Northern War?", "timeline", "1896", "multiple_dates", "1896"),
    ("When did Orion surrender?", "timeline", "1907", "multiple_dates", "1907"),
    ("When did occupation of Orion end?", "timeline", "1918", "multiple_dates", "1918"),
    ("Who founded Alpha Labs?", "people", "Ali", "multiple_people", "Ali founded"),
    ("When did Sara become CEO?", "people", "2022", "multiple_people", "Sara became"),
    ("Who joined Alpha Labs as CTO?", "people", "Hamza", "multiple_people", "Hamza joined"),
    ("When did Hamza join Alpha Labs?", "people", "2023", "multiple_people", "Hamza joined"),
    ("Who founded Cobalt Labs?", "other-entity", "Tara", "wrong_entity", "Tara founded"),
    ("When did Tara join Alpha Labs?", "other-entity", "2024", "wrong_entity", "Tara joined"),
    ("Does Marble Shop accept cryptocurrency?", "payments", "does not accept cryptocurrency", "negation", "does not accept cryptocurrency"),
    ("Does Marble Shop accept credit cards?", "payments", "accepts credit cards", "negation", "accepts credit cards"),
    ("Are installment payments available at Marble Shop?", "payments", "unavailable", "negation", "unavailable"),
    ("Can I pay Marble Shop by bank transfer?", "payments", "Bank transfer is supported", "negation", "Bank transfer is supported"),
    ("How much does the Atlas bicycle weigh?", "attributes", "12kg", "attribute", "weighs 12kg"),
    ("What brakes does the Atlas bicycle use?", "attributes", "hydraulic disc brakes", "attribute", "hydraulic disc brakes"),
    ("What is the Atlas bicycle frame made from?", "attributes", "aluminum", "attribute", "aluminum"),
    ("How much did the Atlas bicycle cost?", "attributes", "85,000", "attribute", "85,000"),
    ("What is the Atlas bicycle battery capacity?", "attributes", None, "answer_absent", None),
    ("Can Juniper Studio clients split the payment?", "split", "two equal installments", "paraphrase", "two equal installments"),
    ("Are flexible payments available at Juniper Studio?", "split", "two equal installments", "paraphrase", "two equal installments"),
    ("Can I pay Juniper Studio in installments?", "split", "two equal installments", "paraphrase", "two equal installments"),
    ("Do Juniper Studio clients need to pay everything at once?", "split", "two equal installments", "paraphrase_negation", "two equal installments"),
    ("How much does adult admission at Slate Museum cost?", "prices", "700", "multiple_prices", "700"),
    ("How much does child admission cost?", "prices", "250", "multiple_prices", "250"),
    ("How much does student admission cost?", "prices", "400", "multiple_prices", "400"),
    ("Where is Aster Research located?", "locations", "Quito", "multiple_locations", "Quito"),
    ("Where is Boreal Research located?", "locations", "Lima", "multiple_locations", "Lima"),
    ("Where is Cygnus Research located?", "locations", "Suva", "multiple_locations", "Suva"),
    ("When did Vela launch?", "negated", "2014", "negated_date", "2014"),
    ("When did Nacre open?", "conflict", None, "contradiction", None),
    ("When did Meridian hire Tala?", "cross", "2008", "cross_paragraph", "2008"),
    ("When did Quartz launch?", "short", "2016", "short_vs_spam", "2016"),
    ("When did the Sable dam open?", "long", "1983", "long_document", "1983"),
    ("What is hydrtion?", "tech", "Hydration attaches", "typo", "Hydration attaches"),
    ("What does firbase store?", "tech", "application records", "typo", "application records"),
    ("What is pyskology?", "tech", "cognition", "typo", "cognition"),
    ("Atlas bicycel brakes", "attributes", None, "typo_keyword", None),
    ("What does a CPU execute?", "acronym", "instructions", "acronym", "executes instructions"),
    ("bike commuting", "synonym", None, "synonym_keyword", None),
    ("cycle wheels", "synonym", None, "synonym_keyword", None),
    ("Does Velvet offer refunds?", "topic", None, "answer_absent", None),
    ("When did Velvet hire Anika?", "topic", "2017", "same_entity_wrong_predicate", "2017"),
    ("How much is Velvet revenue?", "topic", None, "answer_absent", None),
    ("Who founded Velvet?", "topic", None, "same_predicate_wrong_entity", None),
    ("What does a semaphore coordinate?", "technical", "concurrent access", "legitimate_repetition", "concurrent access"),
    ("Does Pine Library offer membership cards?", "faq", "membership cards", "faq", "membership cards for readers"),
    ("Does Pine Library offer installment payments?", "faq", None, "faq_wrong_attribute", None),
    ("When was Pine Library founded?", "faq", None, "faq_wrong_predicate", None),
    ("What tools does Delta lab use?", "markdown", "microscopes", "markdown", "microscopes"),
    ("When did Aquila construction begin?", "dates", "1961", "same_sentence_dates", "1961"),
    ("When did Aquila open?", "dates", "1968", "same_sentence_dates", "1968"),
    ("When did Aquila close?", "dates", "1994", "same_sentence_dates", "1994"),
    ("When did Aquila reopen?", "dates", "2001", "same_sentence_dates", "2001"),
    ("Does Aster Research accept cryptocurrency?", "locations", None, "high_lexical_wrong_attribute", None),
    ("Does Juniper Studio provide a refund?", "split", None, "same_topic_wrong_attribute", None),
]
