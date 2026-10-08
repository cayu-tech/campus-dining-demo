"""Construct the application's durable stores from the configured database.

CAYU_DATABASE_URL selects PostgreSQL for deployments. Without it the stores use
local SQLite at data/cayu.db under the project root, whatever the working
directory. The Cayu CLI reads CAYU_DATABASE_URL first too, then
[tool.cayu.session_store], so the app, `cayu session`, `cayu serve`, and Evals
use the same database. A maintained product service also keeps its product
operation records there.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cayu import (
    ApplicationStores,
    KnowledgeAccessScope,
    KnowledgeStore,
    SessionStore,
    TaskStore,
    configured_database_url,
    open_application_stores,
)

from configuration.settings import configured_public_authority_alias_codec
from cayu.model_policy import model_policy_enabled

if TYPE_CHECKING:
    from cayu.server import ProductOperationStore

LOCAL_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "cayu.db"


@dataclass(frozen=True, slots=True)
class ProjectStores:
    session_store: SessionStore
    task_store: TaskStore | None
    knowledge_store: KnowledgeStore | None
    # Stores built here and their shared connection pool; close() releases them.
    configured: ApplicationStores | None
    product_store: ProductOperationStore | None = None


def build_stores(
    *,
    session_store: SessionStore | None = None,
    task_store: TaskStore | None = None,
    knowledge_store: KnowledgeStore | None = None,
    knowledge_scope: KnowledgeAccessScope | None = None,
    product_store: ProductOperationStore | None = None,
    product_operations: bool = False,
) -> ProjectStores:
    """Build the configured stores unless a caller injects hermetic test stores.

    ``product_operations=True`` also builds the maintained service's product
    operation store in the same database and connection pool.
    """

    if knowledge_scope is None and knowledge_store is not None:
        raise ValueError("knowledge_store requires the knowledge capability")
    build_tasks = task_store is None
    build_knowledge = knowledge_scope is not None and knowledge_store is None
    build_product = product_operations and product_store is None
    if (
        session_store is not None
        and not build_tasks
        and not build_knowledge
        and not build_product
        and not model_policy_enabled()
    ):
        return ProjectStores(
            session_store,
            task_store,
            knowledge_store,
            configured=None,
            product_store=product_store,
        )
    configured = open_application_stores(
        configured_database_url(),
        sqlite_path=LOCAL_DATABASE_PATH,
        tasks=build_tasks,
        knowledge_scope=knowledge_scope if build_knowledge else None,
        product_operations=build_product,
        model_policy=model_policy_enabled(),
        public_authority_alias_codec=configured_public_authority_alias_codec(),
    )
    return ProjectStores(
        session_store=(
            session_store if session_store is not None else configured.session_store
        ),
        task_store=configured.task_store if build_tasks else task_store,
        knowledge_store=(
            configured.knowledge_store if build_knowledge else knowledge_store
        ),
        configured=configured,
        product_store=configured.product_store if build_product else product_store,
    )
