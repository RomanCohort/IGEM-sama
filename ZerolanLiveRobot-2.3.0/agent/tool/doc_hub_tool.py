"""文档中心 LangChain 工具"""
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from features.doc_hub import DocHub, DOC_CATEGORIES


class DocHubToolInput(BaseModel):
    command: str = Field(description="文档命令，如 '列表', '搜索 质粒', '扫描', '监视 C:/docs'")


class DocHubTool(BaseTool):
    """技术文档中心工具。"""
    name: str = "文档中心"
    description: str = (
        "管理iGEM团队技术文档。支持：\n"
        "  list / 列表 - 查看所有分类\n"
        "  搜索 [关键词] - 搜索文档\n"
        "  扫描 - 扫描监视文件夹\n"
        "  监视 [路径] - 添加监视文件夹\n"
        "示例: '列表', '搜索 质粒提取', '扫描'"
    )
    args_schema: Type[BaseModel] = DocHubToolInput

    def __init__(self):
        super().__init__()
        self._hub = DocHub()

    def set_llm_predict(self, llm_predict):
        """设置LLM预测函数。"""
        self._hub.set_llm_predict(llm_predict)

    def _run(self, command: str) -> str:
        mode, payload = DocHub.parse_doc_command(f"/doc {command}")
        logger.debug("DocHubTool: mode={}, payload={}", mode, payload)

        if mode == "list":
            categories = self._hub.get_all_categories_with_count()
            lines = ["文档中心分类："]
            for cat in categories:
                lines.append(f"  {cat['icon']} {cat['label']} ({cat['count']}篇)")
            total = sum(c["count"] for c in categories)
            lines.append(f"\n共 {total} 篇文档")
            return "\n".join(lines)

        elif mode == "search":
            query = payload.get("query", "")
            if not query:
                return "请提供搜索关键词"
            results = self._hub.search(query)
            if not results:
                return f"未找到与'{query}'相关的文档"
            lines = [f"找到 {len(results)} 篇相关文档："]
            for doc in results[:5]:
                lines.append(self._hub.format_doc_text(doc))
            return "\n---\n".join(lines)

        elif mode == "add":
            path = payload.get("path", "")
            category = payload.get("category", "other")
            if not path:
                return "请提供文档路径"
            doc = self._hub.add_document(path, category=category)
            if doc:
                return f"已添加文档：{doc['title']} (ID: {doc['id']})"
            return "添加失败，请检查文件路径"

        elif mode == "watch":
            path = payload.get("path", "")
            if not path:
                return "请提供文件夹路径"
            if self._hub.add_watch_folder(path):
                return f"已添加监视文件夹：{path}"
            return "该文件夹已在监视列表中"

        elif mode == "scan":
            stats = self._hub.scan_watch_folders()
            return (
                f"扫描完成：扫描 {stats['scanned']} 个文件，"
                f"新增 {stats['added']} 篇，更新 {stats['updated']} 篇"
                + (f"\n错误: {stats['errors']}" if stats["errors"] else "")
            )

        return "未知文档命令。可用: 列表, 搜索, 扫描, 监视"
