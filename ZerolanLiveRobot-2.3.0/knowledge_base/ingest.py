"""CLI script for ingesting documents into the IGEM-sama knowledge base.

Usage:
    # Ingest all documents from the default docs directory
    python -m knowledge_base.ingest --dir knowledge_base/docs

    # Ingest a single file with a specific category
    python -m knowledge_base.ingest --file wiki/project_overview.md --category project

    # Reset (drop + re-insert) the entire collection
    python -m knowledge_base.ingest --dir knowledge_base/docs --reset

    # Override chunk size and overlap
    python -m knowledge_base.ingest --dir knowledge_base/docs --max-chars 300 --overlap 30
"""

import argparse
import sys

from loguru import logger

from knowledge_base.config import KnowledgeBaseConfig
from knowledge_base.loader import ingest_directory, ingest_document
from knowledge_base.kb_pipeline import KnowledgeBasePipeline
from pipeline.db.milvus.milvus_sync import MilvusSyncPipeline


def build_pipeline(config: KnowledgeBaseConfig | None = None) -> KnowledgeBasePipeline:
    """Construct a KnowledgeBasePipeline from config or defaults."""
    if config is None:
        config = KnowledgeBaseConfig()

    vec_db_config = _load_vec_db_config()
    vec_db = MilvusSyncPipeline(vec_db_config)
    return KnowledgeBasePipeline(vec_db, config)


def _load_vec_db_config():
    """Try to load Milvus config from the main project config, else use defaults."""
    try:
        from manager.config_manager import get_config
        _config = get_config()
        return _config.pipeline.vec_db.milvus
    except Exception:
        from pipeline.db.milvus.milvus_sync import MilvusDatabaseConfig
        logger.warning("Could not load project config, using default Milvus config.")
        return MilvusDatabaseConfig()


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into IGEM-sama knowledge base.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dir", type=str, help="Directory containing documents to ingest.")
    group.add_argument("--file", type=str, help="Single file to ingest.")

    parser.add_argument("--category", type=str, default="general",
                        help="Category tag for the documents (default: general).")
    parser.add_argument("--reset", action="store_true",
                        help="Drop the collection before ingesting (full refresh).")
    parser.add_argument("--max-chars", type=int, default=500,
                        help="Maximum characters per chunk (default: 500).")
    parser.add_argument("--overlap", type=int, default=50,
                        help="Overlap characters between chunks (default: 50).")
    parser.add_argument("--collection", type=str, default=None,
                        help="Override Milvus collection name.")

    args = parser.parse_args()

    config = KnowledgeBaseConfig(
        max_chunk_chars=args.max_chars,
        chunk_overlap=args.overlap,
    )
    if args.collection:
        config.collection_name = args.collection

    kb = build_pipeline(config)

    # Load entries
    if args.dir:
        entries = ingest_directory(
            args.dir, category=args.category,
            max_chars=args.max_chars, overlap=args.overlap,
        )
    else:
        entries = ingest_document(
            args.file, category=args.category,
            max_chars=args.max_chars, overlap=args.overlap,
        )

    if not entries:
        logger.warning("No entries to ingest.")
        sys.exit(0)

    # Insert
    if args.reset:
        count = kb.ingest_with_reset(entries)
    else:
        count = kb.ingest(entries)

    logger.info(f"Ingestion complete: {count}/{len(entries)} entries inserted.")


if __name__ == "__main__":
    main()
