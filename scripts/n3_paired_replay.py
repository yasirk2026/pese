"""Run exposed replay against a chosen local source tree with frozen timestamps.

The original replay creates directory-hub timestamps at wall time, which can
change tied tail ranks. Freeze every document timestamp for exact paired checks.
Environment PESE_BRAIN_PATH must already identify an isolated synthetic Brain.
"""
import argparse
import os
from pathlib import Path
import sys


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if not os.environ.get("PESE_BRAIN_PATH"):
        parser.error("Explicit synthetic Brain path required")
    os.environ["PESE_REL_SHADOW_ENABLED"]="false"
    os.environ["HF_HUB_OFFLINE"]="1"
    sys.path.insert(0,str(Path(args.source_root).resolve()))
    from engine.evaluation import independent_runner
    original=independent_runner.documents
    def frozen_documents():
        docs=original()
        for doc in docs:
            doc.created_at=doc.updated_at="2020-01-01T00:00:00Z"
        return docs
    independent_runner.documents=frozen_documents
    from engine.ranking import scorer
    from engine.search_sync.feedback_store import SearchSyncFeedbackStore
    from engine.search_sync.preference_signal import SearchSyncPreferenceSignal
    scorer.default_preference_signal=SearchSyncPreferenceSignal(SearchSyncFeedbackStore(":memory:"))
    independent_runner.run(args.output)
