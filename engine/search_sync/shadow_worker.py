"""Fixed diagnostic worker. No rank authority, no DB/Brain imports or writes."""
import json
import os
from pathlib import Path
import sys


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ["PESE_REL_SHADOW_WORKER"] = "1"
    os.environ["PESE_REL_SHADOW_ENABLED"] = "true"
    payload = json.loads(sys.stdin.buffer.read(65537))
    import torch
    torch.set_num_threads(2)
    from engine.search_sync.neural_shadow import PESERelationShadowAdapter
    adapter = PESERelationShadowAdapter(_inference_worker=True)
    summaries, observations = adapter.observe_candidates(payload["query"], payload["normalized_query"],
                                                          payload["context_id"], payload["items"])
    print(json.dumps({"summaries": {k:v.model_dump() for k,v in summaries.items()},
                      "observations": [o.model_dump() for o in observations]}, allow_nan=False))


if __name__ == "__main__":
    main()
