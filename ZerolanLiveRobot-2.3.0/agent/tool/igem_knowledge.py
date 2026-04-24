"""IGEM Knowledge Base Tool for LangChain agent.

When viewers ask about the IGEM-FBH project, bio-parts, experiment design,
or safety rules, the LLM agent can call this tool to retrieve relevant
information from the knowledge base.
"""

from typing import Type, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from knowledge_base.kb_pipeline import KnowledgeBasePipeline


class IGEMKnowledgeToolInput(BaseModel):
    query: str = Field(description="The question about the IGEM project to search in the knowledge base.")


class IGEMKnowledgeTool(BaseTool):
    """LangChain tool that queries the IGEM knowledge base via RAG."""

    name: str = "IGEM知识库"
    description: str = (
        "当观众问关于IGEM-FBH队伍的项目、生物元件、实验设计、安全规范、人文实践等问题时，"
        "使用此工具查询知识库获取相关信息。"
    )
    args_schema: Type[BaseModel] = IGEMKnowledgeToolInput
    return_direct: bool = False

    # The pipeline instance is set after construction because BaseTool
    # requires Pydantic-compatible fields.
    kb_pipeline: Optional[KnowledgeBasePipeline] = None

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        if self.kb_pipeline is None:
            return "知识库暂不可用。"
        result = self.kb_pipeline.retrieve(query)
        if not result.items:
            return "知识库中未找到相关信息。"
        lines = []
        for i, item in enumerate(result.items, 1):
            cat = f"[{item.category}]" if item.category else ""
            lines.append(f"{i}. {cat} {item.text}")
        return "\n".join(lines)
