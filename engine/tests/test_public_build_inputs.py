"""Public source must contain the laboratory fixture imported during API startup."""
from engine.evaluation.synthetic_history import SYNTHETIC_EVENTS
from engine.discovery.models import QuerySessionEvent


def test_synthetic_history_fixture_is_valid_and_explicitly_synthetic():
    assert SYNTHETIC_EVENTS
    events = [QuerySessionEvent.model_validate(event) for event in SYNTHETIC_EVENTS]
    assert all(event.session_id.startswith("synth-sess-") for event in events)
