from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseEntry(BaseModel):
    """A single chunk of document stored in the knowledge base."""
    id: int = Field(..., description="Unique identifier for this entry.")
    text: str = Field(..., description="The text content of this chunk.")
    source: str = Field(default="", description="Origin file name or URL.")
    category: str = Field(default="general", description="Category tag, e.g. 'project', 'parts', 'safety'.")
    metadata: Optional[str] = Field(default=None, description="Optional metadata string.")


class KnowledgeBaseQuery(BaseModel):
    """A search query against the knowledge base."""
    query: str = Field(..., description="The search query text.")
    top_k: int = Field(default=3, description="Maximum number of results to return.")
    category: Optional[str] = Field(default=None, description="Filter by category if set.")


class KnowledgeBaseResultItem(BaseModel):
    """A single result from a knowledge base search."""
    text: str = Field(..., description="Matched text content.")
    source: str = Field(default="", description="Origin of this text.")
    category: str = Field(default="general", description="Category of this entry.")
    distance: float = Field(default=0.0, description="Similarity distance (lower = more relevant).")


class KnowledgeBaseResult(BaseModel):
    """The full result of a knowledge base search."""
    items: List[KnowledgeBaseResultItem] = Field(default_factory=list)
    query: str = Field(default="")


class DocumentIngestRequest(BaseModel):
    """Request to ingest a document into the knowledge base."""
    file_path: Optional[str] = Field(default=None, description="Path to the document file.")
    raw_text: Optional[str] = Field(default=None, description="Raw text content (alternative to file_path).")
    category: str = Field(default="general", description="Category tag for all chunks from this document.")
    source: str = Field(default="", description="Source identifier (file name, URL, etc.).")
