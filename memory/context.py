"""Bounded automatic recall and durable attribution policy."""

from cayu import (
    AutomaticRecallContextPolicy,
    AutomaticRecallPolicy,
    AutomaticRecallSourceConfig,
    ContextPolicy,
    KNOWLEDGE_LEXICAL_CHANNEL,
    KNOWLEDGE_SEMANTIC_CHANNEL,
    WEIGHTED_RECIPROCAL_RANK_FUSION_VERSION,
    WeightedReciprocalRankFusionConfig,
)

from knowledge.retrieval import KNOWLEDGE_NAMESPACE

_FUSION_VERSION = "standard-local-knowledge-v1"


def build_context_policy() -> ContextPolicy | None:
    """Recall active scoped knowledge; pending and out-of-scope entries stay excluded."""

    return AutomaticRecallContextPolicy(
        admission_policy=AutomaticRecallPolicy(
            calibration_version="standard-local-recall-query-concepts-v6",
            relevance_policy="cayu.query_concepts.v5",
            fusion_strategy_version=WEIGHTED_RECIPROCAL_RANK_FUSION_VERSION,
            fusion_configuration_version=_FUSION_VERSION,
            minimum_inject_score=0.01,
            minimum_offer_score=0.005,
            max_evaluated_candidates=20,
            max_injected_items=5,
            max_offered_items=5,
        ),
        fusion_config=WeightedReciprocalRankFusionConfig(
            configuration_version=_FUSION_VERSION,
            channel_weights={
                KNOWLEDGE_LEXICAL_CHANNEL: 1.0,
                KNOWLEDGE_SEMANTIC_CHANNEL: 1.0,
            },
            max_candidates_per_channel=20,
            fused_head_limit=20,
        ),
        sources=AutomaticRecallSourceConfig(
            include_knowledge=True,
            include_transcript=False,
            knowledge_required=True,
            transcript_required=False,
            knowledge_namespace=KNOWLEDGE_NAMESPACE,
        ),
    )
