"""会议管理 LangChain 工具"""
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from features.meeting_tracker import MeetingTracker


class MeetingToolInput(BaseModel):
    command: str = Field(description="会议命令，如 'list', '记录 今天讨论了载体构建', '查询 安全', '总结 abc123', '进展 蛋白表达'")


class MeetingTool(BaseTool):
    """iGEM组会记录管理工具。"""
    name: str = "会议管理"
    description: str = (
        "管理iGEM团队组会记录。支持以下命令：\n"
        "  list / 列表 - 列出最近会议\n"
        "  记录 [内容] - 记录新会议\n"
        "  查询 [关键词] - 搜索会议\n"
        "  总结 [会议ID] - AI生成摘要\n"
        "  进展 [关键词] - 追踪任务进展\n"
        "示例: 'list', '记录 今天讨论了载体构建的进展', '查询 安全', '进展 蛋白表达'"
    )
    args_schema: Type[BaseModel] = MeetingToolInput

    def __init__(self):
        super().__init__()
        self._tracker = MeetingTracker()

    def set_llm_predict(self, llm_predict):
        """设置LLM预测函数。"""
        self._tracker.set_llm_predict(llm_predict)

    def _run(self, command: str) -> str:
        mode, payload = MeetingTracker.parse_meeting_command(f"/meeting {command}")
        logger.debug("MeetingTool: mode={}, payload={}", mode, payload)

        if mode == "list":
            meetings = self._tracker.get_recent_meetings(5)
            if not meetings:
                return "暂无会议记录"
            return "\n---\n".join([
                self._tracker.format_meeting_text(m) for m in meetings
            ])

        elif mode == "record":
            raw_notes = payload.get("raw_notes", "")
            if not raw_notes:
                return "请提供会议内容，例如：记录 今天讨论了蛋白表达的问题"
            meeting = self._tracker.add_meeting(
                date="", title="弹幕记录", attendees=[],
                raw_notes=raw_notes,
            )
            return f"已记录会议，ID: {meeting['id']}。可以说 '总结 {meeting['id']}' 生成AI摘要。"

        elif mode == "summarize":
            meeting_id = payload.get("meeting_id", "")
            if not meeting_id:
                meetings = self._tracker.get_recent_meetings(1)
                if not meetings:
                    return "暂无会议可总结"
                meeting_id = meetings[0].get("id", "")
            summary = self._tracker.summarize_meeting(meeting_id)
            if summary and not summary.get("error"):
                return f"会议摘要生成成功：\n" + "\n".join([
                    f"- {k}: {'；'.join(v) if isinstance(v, list) else v}"
                    for k, v in summary.items() if v
                ])
            return f"摘要生成失败：{summary.get('error', '未知错误') if summary else '会议未找到'}"

        elif mode == "progress":
            keyword = payload.get("keyword", "")
            if not keyword:
                return "请提供关键词，例如：进展 蛋白表达"
            results = self._tracker.find_task_progress(keyword)
            if not results:
                return f"未找到与'{keyword}'相关的会议进展"
            lines = []
            for r in results:
                lines.append(f"[{r['date']}] {r['title']}:")
                for item in r["matched"]:
                    lines.append(f"  [{item['category']}] {item['content'][:100]}")
            return "\n".join(lines)

        elif mode == "query":
            query = payload.get("query", "")
            results = self._tracker.query_meetings(query)
            if not results:
                return f"未找到与'{query}'相关的会议"
            return "\n---\n".join([
                self._tracker.format_meeting_text(m) for m in results[:3]
            ])

        return "未知会议命令，可用: list, 记录, 查询, 总结, 进展"
