"""数据文件路径定义"""
from pathlib import Path

# 数据目录 (IGEM-sama项目根目录下的data文件夹)
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 各功能模块数据文件路径
MEETINGS_PATH = DATA_DIR / "meetings.json"
TASK_BOARD_PATH = DATA_DIR / "task_board.json"
BIO_WORKFLOWS_PATH = DATA_DIR / "bio_workflows_state.json"
DOC_HUB_PATH = DATA_DIR / "doc_hub_index.json"
