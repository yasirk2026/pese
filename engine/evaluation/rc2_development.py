"""Exposed synthetic answer development; never an independent holdout."""
import argparse
import json
import math
import time
from pathlib import Path
from collections import Counter
from ..passages.answer_pipeline import AnswerPipeline


def cases():
    rows=[]
    def add(category,text,items,title='',extra=None):
        for query,expected in items:
            rows.append(dict(category=category,query=query,expected=expected,title=title,text=text,extra=extra))
    # Eight deliberately varied event/actor sources, each with a near-topic
    # distractor event and an unsupported relation question.
    for i,name in enumerate(['Aster','Beryl','Cedar','Delta','Elm','Flint','Garnet','Hazel']):
        year=1980+i
        text=f'The {name} station opened in {year}. A storm stopped the {name} station clock in {year+1}. Engineer Nora Hale repaired the {name} station clock in {year+2}. The {name} station was renovated in {year+3}.'
        add('same_topic_different_relation',text,[(f'When did the {name} station open?',str(year)),(f'Who repaired the {name} station clock?','Nora Hale'),(f'When was the {name} station clock repaired?',str(year+2)),(f'When was the {name} station renovated?',str(year+3)),(f'Who designed the {name} station clock?',None),(f'Why did the {name} station open?',None)],name+' station')
    for name,weight,color,price in [('Juniper','12.4','blue','84,000'),('Kite','10.2','red','71,000'),('Larch','13.8','green','93,000'),('Maple','11.3','amber','88,000')]:
        text=f'The {name} bicycle weighs {weight} kg. The {name} bicycle has an aluminum frame. The {name} bicycle uses hydraulic disc brakes. The {name} bicycle cost Rs {price}. The {name} bicycle is {color}. The {name} bicycle was purchased on 18 April 2022.'
        add('multi_attribute',text,[(f'What is the weight of the {name} bicycle?',weight),(f'What brakes does the {name} bicycle use?','hydraulic disc brakes'),(f'What frame does the {name} bicycle have?','aluminum'),(f'What is the price of the {name} bicycle?',price),(f'What color is the {name} bicycle?',color),(f'When was the {name} bicycle purchased?','18 April 2022'),(f'What motor does the {name} bicycle use?',None),(f'Who repaired the {name} bicycle?',None)],name+' bicycle')
    add('paraphrase','Opal Clinic customers may divide the consultation fee into three monthly installments.',[
        ('Can Opal Clinic customers split the consultation fee?','three monthly installments'),
        ('Does Opal Clinic offer flexible payments?','three monthly installments'),
        ('Can Opal Clinic customers reserve the consultation fee?',None),
        ('What is the price of the Opal Clinic consultation?',None),
        ('Does Opal Clinic offer flexible appointments?',None),
        ('Can Opal Clinic customers split a deposit?',None),
        ('Can Opal Clinic customers split the course fee?',None)])
    add('nominal_payment_mentions','The Pearl Clinic guide discusses installment payments and consultation fees.',[
        ('Does Pearl Clinic offer flexible payments?',None)])
    add('negation','Quartz Museum accepts cards for admission. Quartz Museum does not accept crypto for admission.',[
        ('Does Quartz Museum accept cards?','accepts cards'),('Does Quartz Museum accept crypto?','not accept crypto'),('Does Quartz Museum accept checks?',None),('Who accepts cards at Quartz Museum?',None)])
    add('contradiction','Reed Clinic offers installment payments. Reed Clinic does not offer installment payments.',[
        ('Does Reed Clinic offer installment payments?',None)])
    add('definition','A dye swatch is a small cloth sample used to test a pigment. A press proof refers to a trial impression made before the main printing run.',[
        ('What is a dye swatch?','small cloth sample'),('What does press proof mean?','trial impression'),('What is a calibration ring?',None)])
    add('cause','The Sable pump stopped because ice blocked the intake. The Sable pump was repaired in 2017.',[
        ('Why did the Sable pump stop?','ice blocked the intake'),('Who repaired the Sable pump?',None),('When was the Sable pump repaired?','2017'),('Why was the Sable pump repaired?',None)])
    add('procedure','To reset the Tern router, first press the reset button, then wait for the indicator to flash. The Tern router uses a 12 volt adapter.',[
        ('How do I reset the Tern router?','press the reset button'),('What should I do to reset the Tern router?','press the reset button'),('How do I repair the Tern router?',None)])
    add('coreference_easy','Dr. Lena Hart joined the clinic in 2019. She became medical director in 2023.',[
        ('When did Dr. Lena Hart become medical director?','2023'),('When did Dr. Lena Hart join the clinic?','2019')])
    add('coreference_ambiguous','Ali met Hamza. He repaired the clock in 2014.',[
        ('Who repaired the clock?',None),('When did Ali repair the clock?',None),('When did Hamza repair the clock?',None)])
    add('heading_context','The lantern uses a brass housing. The lantern weighs 420 grams.',[
        ('What housing does the Umber lantern use?','brass'),('What is the weight of the Umber lantern?','420 grams')],title='Umber lantern')
    add('temporal_formats','The Vale tower was completed in the 14th century. The Vale tower opened on Friday morning.',[
        ('In which century was the Vale tower completed?','14th century'),('When does the Vale tower open?','Friday morning'),('When was the Vale tower demolished?',None)])
    add('quantities','The Willow workshop accepts nine participants per session. The Willow workshop costs 40 coins per session.',[
        ('How many participants does the Willow workshop accept?','nine'),('How much does the Willow workshop cost?','40 coins'),('How many teachers does the Willow workshop accept?',None)])
    add('faq_outside_passage','The Yarrow pool has changing rooms.',[
        ('What coin does the Yarrow pool locker use?','two-crown'),('What coin does the Yarrow pool vending machine use?',None)],title='Yarrow pool',extra='The Yarrow pool locker uses a two-crown coin.')
    add('actor_argument_binding','Nora Hale inspected the clock and Leo Moss repaired the bell.',[
        ('Who repaired the clock?',None),('Who repaired the bell?','Leo Moss'),('Who inspected the bell?',None)])
    add('nominal_predicate','Each boat carries its own name. The repair manual lists clock components.',[
        ('How many boats does the station own?',None),('Who repaired the clock?',None)])
    add('object_coreference','The Sequoia club bought a cedar chest for its costumes. It is kept beneath the stairs.',[
        ('Where is the Sequoia club cedar chest kept?','beneath the stairs')],title='Sequoia club chest')
    add('cross_sentence_named_object','The model boat is called Silver Dawn. The boat is built from cedar.',[
        ('What is Silver Dawn built from?','cedar')],title='Silver Dawn model boat')
    return rows


def run(output):
    records=[]
    for row in cases():
        pipeline=AnswerPipeline(); passages=[dict(text=row['text'],score=20,id='primary',heading=row['title'])]
        if row['extra']:passages.append(dict(text=row['extra'],score=1,id='faq',heading='FAQ'))
        t=time.perf_counter();answer,reason=pipeline.run(row['query'],passages,row['title']);elapsed=(time.perf_counter()-t)*1000
        expected=row['expected'];correct=bool(answer and expected and expected.casefold() in answer.casefold())
        records.append(dict(**row,answer=answer,correct=correct if expected else not answer,wrong_promotion=bool(answer and not correct),elapsed_ms=elapsed,audit=pipeline.audit))
    answerable=[r for r in records if r['expected']];negatives=[r for r in records if not r['expected']]
    timings=sorted(r['elapsed_ms'] for r in records)
    summary=dict(cases=len(records),answerable=len(answerable),correct=sum(r['correct'] for r in answerable),wrong=sum(r['wrong_promotion'] for r in records),negatives=len(negatives),negative_abstentions=sum(r['correct'] for r in negatives),categories=dict(Counter(r['category'] for r in records)),extraction_p50_ms=timings[math.ceil(len(timings)*.5)-1],extraction_p95_ms=timings[math.ceil(len(timings)*.95)-1])
    Path(output).write_text(json.dumps(dict(protocol='Exposed synthetic answer-unit development, oracle source passages; retrieval separately measured in RC1 replay.',summary=summary,records=records),indent=2),encoding='utf-8'); print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);run(parser.parse_args().output)
