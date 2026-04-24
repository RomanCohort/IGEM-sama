"""任务看板 LangChain 工具"""
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from features.task_board import TaskBoard


class TaskBoardToolInput(BaseModel):
    command: str = Field(description="任务命令，如 '看板', '添加 完成载体构建', '完成 abc123', '搜索 载体'")


class TaskBoardTool(BaseTool):
    """iGEM团队任务看板工具。"""
    name: str = "任务看板"
    description: str = (
        "管理iGEM团队任务。支持以下命令：\n"
        "  看板 / board - 查看看板\n"
        "  添加 [任务名] - 创建新任务\n"
        "  完成 [任务ID] - 标记完成\n"
        "  [关键词] - 搜索任务\n"
        "示例: '看板', '添加 完成载体构建', '完成 abc123'"
    )
    args_schema: Type[BaseModel] = TaskBoardToolInput

    def __init__(self):
        super().__init__()
        self._board = TaskBoard()

    def _run(self, command: str) -> str:
        # 尝试解析为task命令
        mode, payload = TaskBoard.parse_task_command(f"/task {command}")

        # 如果不是task命令，尝试team命令
        if mode is None:
            mode, payload = TaskBoard.parse_team_command(f"/team {command}")

        logger.debug("TaskBoardTool: mode={}, payload={}", mode, payload)

        if mode == "board":
            board = self._board.get_board_view()
            lines = []
            status_icons = {
                "todo": "📋 待办", "in_progress": "🔨 进行中",
                "done": "✅ 已完成", "blocked": "🚧 卡住",
                "cancelled": "❌ 已取消",
            }
            for status, tasks in board.items():
                if tasks:
                    icon = status_icons.get(status, status)
                    lines.append(f"{icon} ({len(tasks)})")
                    for t in tasks[:5]:
                        lines.append(f"  · {t['title']} (ID: {t['id']})")
                        if t.get("deadline"):
                            lines.append(f"    截止: {t['deadline']}")
            return "\n".join(lines) if lines else "看板为空，还没有任务"

        elif mode == "add":
            title = payload.get("title", "")
            if not title:
                return "请提供任务名称"
            task = self._board.add_task(title=title)
            return f"已创建任务：{task['title']}（ID: {task['id']}）"

        elif mode == "update":
            task_id = payload.get("task_id", "")
            if not task_id:
                return "请提供任务ID"
            result = self._board.update_task(task_id, payload.get("updates", {}))
            if result:
                return f"任务已更新：{result['title']} → 状态: {result['status']}"
            return f"任务 {task_id} 未找到"

        elif mode == "find":
            keyword = payload.get("keyword", "")
            tasks = self._board.find_by_task(keyword)
            members = self._board.find_by_role(keyword)
            members += self._board.find_by_skill(keyword)

            lines = []
            if tasks:
                lines.append(f"找到 {len(tasks)} 个任务:")
                for t in tasks[:5]:
                    lines.append(f"  {self._board.format_task_text(t)}")
            if members:
                lines.append(f"找到 {len(members)} 位成员:")
                for m in members:
                    lines.append(f"  {self._board.format_member_text(m)}")
            return "\n".join(lines) if lines else f"未找到与'{keyword}'相关的内容"

        elif mode == "list":
            members = self._board.get_all_members()
            if not members:
                return "暂无团队成员"
            return "\n".join([self._board.format_member_text(m) for m in members])

        elif mode == "add_team":
            name = payload.get("name", "")
            if not name:
                return "请提供成员姓名"
            member = self._board.add_member(
                name=name,
                role=payload.get("role", ""),
                skills=payload.get("skills", []),
            )
            if member:
                return f"已添加成员：{member['name']}"
            return f"成员 {name} 已存在"

        return "未知命令，可用: 看板, 添加, 完成, 搜索"
