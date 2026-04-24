"""Knowledge Base RAG Pipeline.

Wraps the Milvus vector database to provide RAG (Retrieval-Augmented
Generation) functionality for IGEM-sama.

Two retrieval modes:
  1. **Automatic** - build_context() is called inside emit_llm_prediction()
     so every user message is enriched with relevant KB context.
  2. **Tool-based** - IGEMKnowledgeTool lets the LLM agent explicitly query
     the KB when it decides the question is project-related.
"""

from typing import List, Optional

from loguru import logger
from zerolan.data.pipeline.milvus import MilvusInsert, MilvusQuery, InsertRow, MilvusQueryResult

from knowledge_base.config import KnowledgeBaseConfig
from knowledge_base.models import KnowledgeBaseEntry, KnowledgeBaseResult, KnowledgeBaseResultItem
from pipeline.db.milvus.milvus_sync import MilvusSyncPipeline


class KnowledgeBasePipeline:
    """RAG pipeline backed by Milvus."""

    def __init__(self, vec_db: MilvusSyncPipeline, config: KnowledgeBaseConfig):
        self._vec_db = vec_db
        self._config = config
        self._collection = config.collection_name
        logger.info(f"KnowledgeBasePipeline initialized (collection={self._collection})")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, entries: List[KnowledgeBaseEntry]) -> int:
        """Insert knowledge base entries into the Milvus collection.

        Returns the number of entries successfully inserted.
        """
        rows = [
            InsertRow(id=e.id, text=e.text, subject=e.category)
            for e in entries
        ]
        insert = MilvusInsert(
            collection_name=self._collection,
            drop_if_exists=False,
            texts=rows,
        )
        try:
            result = self._vec_db.insert(insert)
            logger.info(f"Ingested {result.insert_count} entries into '{self._collection}'")
            return result.insert_count
        except Exception as e:
            logger.error(f"Failed to ingest entries: {e}")
            return 0

    def ingest_with_reset(self, entries: List[KnowledgeBaseEntry]) -> int:
        """Drop the existing collection and re-insert all entries.

        Useful for full refreshes when documents are updated.
        """
        rows = [
            InsertRow(id=e.id, text=e.text, subject=e.category)
            for e in entries
        ]
        insert = MilvusInsert(
            collection_name=self._collection,
            drop_if_exists=True,
            texts=rows,
        )
        try:
            result = self._vec_db.insert(insert)
            logger.info(f"Ingested (reset) {result.insert_count} entries into '{self._collection}'")
            return result.insert_count
        except Exception as e:
            logger.error(f"Failed to ingest entries (reset): {e}")
            return 0

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        category: Optional[str] = None,
    ) -> KnowledgeBaseResult:
        """Search the knowledge base and return matching entries.

        Args:
            query: The search query text.
            top_k: Maximum number of results.
            category: If set, filter results to this category.

        Returns:
            A KnowledgeBaseResult containing matched items.
        """
        mq = MilvusQuery(
            collection_name=self._collection,
            limit=top_k,
            output_fields=["text", "subject"],
            query=query,
        )
        try:
            raw: MilvusQueryResult = self._vec_db.search(mq)
        except Exception as e:
            logger.warning(f"KB search failed: {e}")
            return KnowledgeBaseResult(query=query)

        items: List[KnowledgeBaseResultItem] = []
        for group in raw.result:
            for row in group:
                text = row.entity.get("text", "")
                cat = row.entity.get("subject", "general")
                # Apply category filter on the client side
                if category and cat != category:
                    continue
                items.append(KnowledgeBaseResultItem(
                    text=text,
                    source="",
                    category=cat,
                    distance=row.distance,
                ))

        return KnowledgeBaseResult(items=items, query=query)

    def build_context(self, query: str, top_k: int = 3) -> str:
        """Search the KB and format results as a context string for LLM injection.

        Returns an empty string if no results are found or the KB is unavailable,
        so the caller can safely prepend without checking.
        """
        result = self.retrieve(query, top_k=top_k)
        if not result.items:
            return ""

        lines = ["[知识库检索结果]"]
        for i, item in enumerate(result.items, 1):
            source_tag = f"(分类: {item.category})" if item.category else ""
            lines.append(f"{i}. {source_tag} {item.text}")
        return "\n".join(lines)
