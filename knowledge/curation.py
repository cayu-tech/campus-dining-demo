"""Explicit administrative publication of purchasing policy and source metadata."""

import json

from cayu import KnowledgeIndexer, KnowledgeIndexRequest

from domain.catalog import POLICY
from knowledge.retrieval import build_knowledge_scope


async def seed(store, settings):
    indexer = KnowledgeIndexer(store, access_scope=build_knowledge_scope(settings))
    await indexer.index_text(
        KnowledgeIndexRequest(
            entry_id="purchasing-policy",
            namespace=settings.namespace,
            title="University dining purchasing policy",
            text=json.dumps(POLICY, indent=2),
            source_type="synthetic-business-policy",
            source_id="campus-purchasing-v1",
            source_uri="fixture://campus-dining/purchasing-policy/v1",
            created_by="dining-procurement-admin",
        )
    )
