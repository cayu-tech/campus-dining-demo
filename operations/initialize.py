"""Explicit administrative seeding. Never deletes active state."""

import secrets

from cayu import SQLiteKnowledgeStore

from configuration.settings import CUSTOMERS, Settings
from domain.store import PortalStore
from knowledge.curation import seed
from knowledge.retrieval import build_knowledge_scope


async def initialize(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    key = settings.data_dir / "memory-evidence.key"
    try:
        with key.open("x") as f:
            f.write(secrets.token_hex(32) + "\n")
        key.chmod(0o600)
    except FileExistsError:
        pass
    review_key = settings.data_dir / "human-review.key"
    try:
        import os
        fd = os.open(review_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    ownership = settings.data_dir / "docker-ownership"
    ownership.mkdir(mode=0o700, exist_ok=True)
    ownership.chmod(0o700)
    PortalStore(settings.portal_database).initialize()
    for customer in CUSTOMERS:
        scoped = Settings(data_dir=settings.data_dir, customer=customer)
        store = SQLiteKnowledgeStore(scoped.database, access_scope=build_knowledge_scope(scoped))
        try:
            await seed(store, scoped)
        finally:
            await store.close()
