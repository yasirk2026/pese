"""Safety boundaries for the production V2 proposition path."""
import pytest
from engine.passages.answer_pipeline import AnswerPipeline, QueryFrame


def answer(query,text,title=''):
    pipeline=AnswerPipeline()
    value,_=pipeline.run(query,[dict(text=text,id='source',score=20)],title)
    return value,pipeline.audit


@pytest.mark.parametrize('query,text',[
    ('Who repaired the station clock?','The station clock stopped during the storm.'),
    ('Who repaired the clock?','Nora Hale did not repair the clock.'),
    ('When did the tower open?','The tower did not open in 2001.'),
    ('How many participants does the workshop accept?','The workshop does not accept nine participants.'),
    ('Who repaired the clock?','Nora Hale inspected the clock and Leo Moss repaired the bell.'),
    ('Who repaired the clock?','Ali met Hamza. He repaired the clock.'),
    ('Does Pearl Clinic split payments?','Pearl Clinic offers flexible appointment scheduling.'),
    ('Does Pearl Clinic offer flexible payments?','The Pearl Clinic guide discusses installment payments and consultation fees.'),
    ('How many boats does the station own?','Each boat carries its own name.'),
    ('Why was the pump repaired?','The pump stopped because ice blocked the intake. The pump was repaired.'),
    ('When was the clock repaired?','The clock stopped in 1997. The station opened in 1982.'),
    ('What motor does the bicycle use?','The bicycle uses hydraulic disc brakes.'),
    ('In what year did the tower open?','The tower opened on Friday.'),
    ('How much does the workshop cost?','The workshop cost nine volunteers their free afternoon.'),
    ('Does Reed Clinic offer installment payments?','Reed Clinic offers installment payments. Reed Clinic does not offer installment payments.'),
])
def test_unsupported_relations_abstain(query,text):
    assert answer(query,text)[0] is None


@pytest.mark.parametrize('query,text,expected',[
    ('Who repaired the clock?','Nora Hale repaired the clock.','Nora Hale'),
    ('Who repaired the clock?','The clock was repaired by Leo Moss.','Leo Moss'),
    ('Who founded Alpha Labs?','Ali founded Alpha Labs.','Ali'),
    ('How much does the bicycle weigh?','The bicycle weighs 12kg.','12kg'),
    ('What is hydration?','Hydration attaches event listeners to server-rendered HTML.','attaches event listeners'),
    ('Is an audition required to join the choir?','No audition is required for the choir.','No audition'),
    ('When did Dr. Lena Hart become medical director?','Dr. Lena Hart joined the clinic in 2019. She became medical director in 2023.','2023'),
    ('Can Opal Clinic customers split the consultation fee?','Opal Clinic customers may divide the consultation fee into three installments.','three installments'),
    ('What temperature is the greenhouse thermostat set to?','The greenhouse thermostat is set to 8 °C.','8 °C'),
    ('In which century was the tower completed?','The tower was completed in the 14th century.','14th century'),
    ('Where is the cedar chest kept?','The club bought a cedar chest for costumes. It is kept beneath the stairs.','beneath the stairs'),
])
def test_supported_propositions_remain_grounded(query,text,expected):
    value,audit=answer(query,text)
    assert value and expected in value
    assert audit['support_sentence'] in text
    assert value in text


def test_validator_exception_is_visible_and_fails_closed(monkeypatch):
    def broken(*args,**kwargs):raise RuntimeError('injected validator failure')
    monkeypatch.setattr(AnswerPipeline,'validate',broken)
    value,audit=answer('When did the tower open?','The tower opened in 2001.')
    assert value is None
    assert any('ANSWER_GATE_EXCEPTION' in c['reason'] for c in audit['candidates'])


def test_query_frame_distinguishes_requested_person_from_known_object():
    frame=QueryFrame.parse('Who repaired the station clock?')
    assert frame.expected_answer_type=='PERSON'
    assert frame.subject==['station','clock']
    assert frame.relation==['repaired']


def test_one_validator_error_cannot_hide_a_possible_conflict(monkeypatch):
    original=AnswerPipeline.validate
    def fail_one(self,candidate,*args):
        if candidate['answer_span']=='2002':raise RuntimeError('candidate unavailable')
        return original(self,candidate,*args)
    monkeypatch.setattr(AnswerPipeline,'validate',fail_one)
    value,audit=answer('When did the tower open?','The tower opened in 2001. The tower opened in 2002.')
    assert value is None
    assert 'ANSWER_GATE_EXCEPTION' in audit['arbitration']


def test_current_policy_resolves_archived_policy_only_by_structure():
    pipeline=AnswerPipeline()
    value,_=pipeline.run('Does Reed Clinic offer installment payments?',[
        dict(text='Reed Clinic offers installment payments.',heading='Old policy',id='old'),
        dict(text='Reed Clinic does not offer installment payments.',heading='Current policy',id='current')])
    assert value and 'not offer' in value
