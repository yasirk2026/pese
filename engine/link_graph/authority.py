"""
PESE Link Graph: Authority Scoring
Computes bounded internal link authority using power-iteration PageRank and in-degree.
Strictly bounded so link authority never overwhelms query relevance.
"""

import math
from typing import Dict
from .graph import LinkGraph

# Maximum authority score boost achievable (bounded to prevent irrelevant hub domination)
MAX_LINK_AUTHORITY_BOOST: float = 1.5
DAMPING_FACTOR: float = 0.85
MAX_ITERATIONS: int = 25
EPSILON: float = 1e-6


class LinkAuthorityCalculator:
    """Computes bounded authority scores across the document link graph."""

    def __init__(self, graph: LinkGraph):
        self.graph = graph
        self.pagerank_scores: Dict[str, float] = {}
        self.authority_scores: Dict[str, float] = {}

    def compute_scores(self) -> None:
        """Compute PageRank and bounded authority scores."""
        nodes = list(self.graph.nodes)
        num_nodes = len(nodes)
        if num_nodes == 0:
            self.pagerank_scores = {}
            self.authority_scores = {}
            return

        # 1. Initialize PageRank uniformly: 1 / N
        initial_val = 1.0 / num_nodes
        pr: Dict[str, float] = {node: initial_val for node in nodes}

        # 2. Power iteration
        for _ in range(MAX_ITERATIONS):
            new_pr: Dict[str, float] = {}
            # Account for dangling nodes (nodes with 0 out-degree)
            dangling_sum = sum(pr[node] for node in nodes if self.graph.out_degree(node) == 0)
            dangling_contrib = (DAMPING_FACTOR * dangling_sum) / num_nodes

            diff = 0.0
            for node in nodes:
                # Sum PR(u) / out_deg(u) for all u that link to node
                incoming_sum = 0.0
                for source in self.graph.rev_adj_list.get(node, set()):
                    out_deg = self.graph.out_degree(source)
                    if out_deg > 0:
                        incoming_sum += pr[source] / out_deg

                val = ((1.0 - DAMPING_FACTOR) / num_nodes) + (DAMPING_FACTOR * incoming_sum) + dangling_contrib
                new_pr[node] = val
                diff += abs(val - pr[node])

            pr = new_pr
            if diff < EPSILON:
                break

        self.pagerank_scores = pr

        # 3. Bounded authority score computation
        # Normalize into [0.0, MAX_LINK_AUTHORITY_BOOST] using log-scaled in-degree + PageRank
        max_in_degree = max([self.graph.in_degree(n) for n in nodes] or [1])
        max_pr = max(self.pagerank_scores.values() or [1.0])

        for node in nodes:
            in_deg = self.graph.in_degree(node)
            deg_norm = math.log(1 + in_deg) / math.log(1 + max(1, max_in_degree))
            pr_norm = self.pagerank_scores[node] / max(1e-9, max_pr)

            # Blended authority signal in [0.0, 1.0]
            blended = 0.6 * deg_norm + 0.4 * pr_norm
            # Scaled to maximum allowed boost
            self.authority_scores[node] = round(blended * MAX_LINK_AUTHORITY_BOOST, 4)

    def get_authority_score(self, slug: str) -> float:
        """Return the bounded link authority bonus for a document slug."""
        return self.authority_scores.get(slug, 0.0)

    def get_doc_link_details(self, slug: str) -> dict:
        """Return full link audit details for a document slug."""
        return {
            "in_degree": self.graph.in_degree(slug),
            "out_degree": self.graph.out_degree(slug),
            "in_links": self.graph.get_in_links(slug),
            "out_links": self.graph.get_out_links(slug),
            "pagerank": round(self.pagerank_scores.get(slug, 0.0), 6),
            "authority_score": self.authority_scores.get(slug, 0.0),
        }
