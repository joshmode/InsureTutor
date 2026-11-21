from __future__ import annotations

import logging

from ..chat.llm import OpenAICompatibleClient
from ..chat.orchestrator import ChatOrchestrator
from ..config import Settings
from ..ingestion.store import KnowledgeBase
from ..retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


class AppRuntime:
    def __init__(self, settings: Settings, consumption=None):
        self.settings = settings
        self.knowledge = KnowledgeBase(settings)
        self.retriever: HybridRetriever | None = None
        self.llm = OpenAICompatibleClient(settings, consumption=consumption)
        self.orchestrator: ChatOrchestrator | None = None
        self.ready = False

    def initialize(self) -> None:
        chunks = self.knowledge.ensure_ready()
        if not chunks:
            raise RuntimeError("Knowledge base is empty after ingestion")
        self.retriever = HybridRetriever(chunks, self.settings)
        self.orchestrator = ChatOrchestrator(self.settings, self.retriever, self.llm)
        from .brochures import BrochureStore
        self.brochures = BrochureStore(
            self.settings, self.llm, self.retriever.embedding_backend,
            self.orchestrator._retrieval_lock,
        )
        self.ready = True
        logger.info(
            "Runtime ready: %d chunks, retrieval=%s, llm_configured=%s",
            len(chunks),
            self.retriever.mode,
            self.llm.configured,
        )
