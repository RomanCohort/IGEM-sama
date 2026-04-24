from pydantic import BaseModel, Field


class KnowledgeBaseConfig(BaseModel):
    enable: bool = Field(default=True, description="Whether the knowledge base is enabled.")
    collection_name: str = Field(default="igem_kb",
                                 description="Milvus collection name for the knowledge base.")
    top_k: int = Field(default=3,
                       description="Number of relevant chunks to retrieve per query.")
    max_chunk_chars: int = Field(default=500,
                                 description="Maximum characters per text chunk during ingestion.")
    chunk_overlap: int = Field(default=50,
                               description="Overlap characters between consecutive chunks.")
    docs_dir: str = Field(default="knowledge_base/docs",
                          description="Directory containing documents for auto-ingestion.")
    auto_ingest_on_start: bool = Field(default=False,
                                       description="Automatically ingest docs_dir on startup.")
