"""
Features模块 - iGEM团队协作功能

包含:
- MeetingTracker: 会议进展追踪
- TaskBoard: 团队任务看板
- BioWorkflowGuide: 生信工作流引导
- DocHub: 技术文档中心
"""

from .store import Store
from .paths import DATA_DIR, MEETINGS_PATH, TASK_BOARD_PATH, BIO_WORKFLOWS_PATH, DOC_HUB_PATH
from .meeting_tracker import MeetingTracker
from .task_board import TaskBoard
from .bio_workflow import BioWorkflowGuide, WORKFLOW_TEMPLATES
from .doc_hub import DocHub, DOC_CATEGORIES

__all__ = [
    "Store",
    "DATA_DIR",
    "MEETINGS_PATH",
    "TASK_BOARD_PATH",
    "BIO_WORKFLOWS_PATH",
    "DOC_HUB_PATH",
    "MeetingTracker",
    "TaskBoard",
    "BioWorkflowGuide",
    "WORKFLOW_TEMPLATES",
    "DocHub",
    "DOC_CATEGORIES",
]
