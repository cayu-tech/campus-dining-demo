"""Knowledge review, curation, and publication behavior."""

import json

from cayu import KnowledgeIndexer, KnowledgeIndexRequest, KnowledgeStatus

from domain.catalog import POLICY
from knowledge.retrieval import KNOWLEDGE_NAMESPACE, build_knowledge_scope

POLICY_ENTRY_ID = "purchasing-policy"


async def publish_purchasing_policy(store) -> None:
    """Publish the reviewed purchasing policy the agent reads. An administrative step."""

    indexer = KnowledgeIndexer(store, access_scope=build_knowledge_scope())
    await indexer.index_text(
        KnowledgeIndexRequest(
            entry_id=POLICY_ENTRY_ID,
            namespace=KNOWLEDGE_NAMESPACE,
            status=KnowledgeStatus.ACTIVE,
            title="University dining purchasing policy",
            text=json.dumps(POLICY, indent=2),
            source_type="synthetic-business-policy",
            source_id="campus-purchasing-v1",
            source_uri="fixture://campus-dining/purchasing-policy/v1",
            created_by="dining-procurement-admin",
            skip_unchanged=True,
        )
    )
