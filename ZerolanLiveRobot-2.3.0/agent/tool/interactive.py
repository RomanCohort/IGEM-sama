"""Interactive Tool Pack for IGEM-sama.

LangChain tools that the LLM can invoke to engage viewers during livestreams:
  - IGEMQuizTool: Launch a biology/IGEM quiz for viewers
  - LotteryTool: Run a viewer lottery/raffle
  - VoteTool: Start a simple poll for viewers
  - CountdownTool: Set a countdown timer with announcement

These tools produce structured output that the LLM can format for chat display.
"""

import random
import time
from typing import ClassVar, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


# =====================================================================
# IGEM Quiz Tool
# =====================================================================

class IGEMQuizInput(BaseModel):
    topic: str = Field(default="biology",
                       description="Quiz topic: 'biology', 'igem', 'synbio', 'safety', or 'team'.")


# Pre-built quiz questions organized by topic
QUIZ_BANK: Dict[str, List[dict]] = {
    "biology": [
        {"q": "DNA的双螺旋结构是由谁发现的？", "a": "沃森和克里克", "options": ["沃森和克里克", "孟德尔", "达尔文", "巴斯德"]},
        {"q": "PCR技术的全称是什么？", "a": "聚合酶链式反应", "options": ["聚合酶链式反应", "蛋白质链式反应", "基因链式反应", "酶链式反应"]},
        {"q": "中心法则描述的是遗传信息的什么过程？", "a": "DNA→RNA→蛋白质", "options": ["DNA→RNA→蛋白质", "RNA→DNA→蛋白质", "蛋白质→RNA→DNA", "DNA→蛋白质→RNA"]},
        {"q": "大肠杆菌的英文学名是什么？", "a": "Escherichia coli", "options": ["Escherichia coli", "Bacillus subtilis", "Saccharomyces cerevisiae", "Pseudomonas aeruginosa"]},
        {"q": "限制性内切酶的作用是什么？", "a": "切割DNA特定序列", "options": ["切割DNA特定序列", "连接DNA片段", "复制DNA", "翻译蛋白质"]},
        {"q": "启动子(Promoter)的功能是什么？", "a": "启动基因转录", "options": ["启动基因转录", "终止基因转录", "翻译蛋白质", "修饰DNA"]},
    ],
    "igem": [
        {"q": "iGEM的全称是什么？", "a": "International Genetically Engineered Machine", "options": ["International Genetically Engineered Machine", "International Gene Experiment Meeting", "Integrated Genetic Engineering Method", "International Genetic Evaluation Metric"]},
        {"q": "iGEM竞赛每年在哪里举办总决赛？", "a": "巴黎", "options": ["巴黎", "波士顿", "伦敦", "东京"]},
        {"q": "BioBrick是什么？", "a": "标准化的生物元件", "options": ["标准化的生物元件", "一种实验技术", "一种蛋白质", "一种培养基"]},
        {"q": "iGEM的Wiki是什么？", "a": "团队项目展示网页", "options": ["团队项目展示网页", "维基百科词条", "内部文档", "评审系统"]},
    ],
    "synbio": [
        {"q": "合成生物学的核心理念是什么？", "a": "工程化设计生物系统", "options": ["工程化设计生物系统", "发现新物种", "克隆动物", "基因测序"]},
        {"q": "质粒(Plasmid)是什么？", "a": "细菌中的环状DNA分子", "options": ["细菌中的环状DNA分子", "细胞核中的DNA", "一种蛋白质", "一种酶"]},
        {"q": "什么是基因回路(Gene Circuit)？", "a": "由基因元件组成的逻辑控制系统", "options": ["由基因元件组成的逻辑控制系统", "电路板上的基因芯片", "DNA测序技术", "蛋白质折叠路径"]},
    ],
}


class IGEMQuizTool(BaseTool):
    """Tool to generate and run an IGEM/biology quiz for viewers."""
    name: str = "IGEM知识问答"
    description: str = (
        "当你想和观众互动、出题考考观众时，使用此工具。"
        "可以出关于生物学、iGEM竞赛、合成生物学或队伍的问题。"
        "topic可选: 'biology'(生物学), 'igem'(iGEM竞赛), 'synbio'(合成生物学), 'safety'(安全), 'team'(队伍)。"
    )
    args_schema: Type[BaseModel] = IGEMQuizInput
    return_direct: bool = False
    obs_controller: ClassVar[Optional[object]] = None  # Set externally

    def _run(self, topic: str = "biology", run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        bank = QUIZ_BANK.get(topic, QUIZ_BANK["biology"])
        if not bank:
            bank = QUIZ_BANK["biology"]
        quiz = random.choice(bank)
        options_str = " ".join([f"{chr(65+i)}.{o}" for i, o in enumerate(quiz["options"])])
        # Show quiz on OBS overlay if available
        if self.obs_controller:
            try:
                self.obs_controller.show_quiz(quiz["q"], quiz["options"], answer_hidden=True)
            except Exception:
                pass
        return f"题目：{quiz['q']}\n选项：{options_str}\n（答案是：{quiz['a']}，先让观众猜，稍后公布答案哦！）"


# =====================================================================
# Lottery Tool
# =====================================================================

class LotteryInput(BaseModel):
    keyword: str = Field(default="IGEM",
                         description="The keyword viewers need to type to enter the lottery.")
    prize: str = Field(default="神秘礼物",
                       description="Description of the prize.")


class LotteryTool(BaseTool):
    """Tool to run a viewer lottery/raffle."""
    name: str = "观众抽奖"
    description: str = (
        "当你想进行抽奖活动时，使用此工具。"
        "设置关键词，让观众发送关键词参与抽奖。"
    )
    args_schema: Type[BaseModel] = LotteryInput
    return_direct: bool = False
    obs_controller: ClassVar[Optional[object]] = None  # Set externally

    # In-memory participant tracking
    _participants: Dict[str, List[str]] = {}
    _active_lotteries: Dict[str, dict] = {}

    def _run(self, keyword: str = "IGEM", prize: str = "神秘礼物",
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        lottery_id = f"lottery_{int(time.time())}"
        self._active_lotteries[lottery_id] = {
            "keyword": keyword,
            "prize": prize,
            "started_at": time.time(),
        }
        self._participants[lottery_id] = []
        # Show lottery on OBS overlay if available
        if self.obs_controller:
            try:
                self.obs_controller.show_lottery(keyword, prize)
            except Exception:
                pass
        return (
            f"抽奖开始啦！观众们请发送「{keyword}」参与抽奖！\n"
            f"奖品是：{prize}\n"
            f"请让观众参与后，再用我公布结果！"
        )

    def draw_winner(self, lottery_id: str) -> Optional[str]:
        """Draw a winner from the participants."""
        participants = self._participants.get(lottery_id, [])
        if not participants:
            return None
        winner = random.choice(participants)
        return winner


# =====================================================================
# Vote Tool
# =====================================================================

class VoteInput(BaseModel):
    question: str = Field(description="The question to ask viewers to vote on.")
    options: str = Field(description="Comma-separated vote options, e.g. 'A,B,C'")


class VoteTool(BaseTool):
    """Tool to start a viewer poll/vote."""
    name: str = "观众投票"
    description: str = (
        "当你想让观众投票选择时，使用此工具。"
        "设置问题和选项，让观众在弹幕中回复选项参与投票。"
    )
    args_schema: Type[BaseModel] = VoteInput
    return_direct: bool = False
    obs_controller: ClassVar[Optional[object]] = None  # Set externally

    # In-memory vote tracking
    _active_votes: Dict[str, dict] = {}

    def _run(self, question: str, options: str,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        opts = [o.strip() for o in options.split(",") if o.strip()]
        if len(opts) < 2:
            return "至少需要2个选项才能投票！"

        vote_id = f"vote_{int(time.time())}"
        self._active_votes[vote_id] = {
            "question": question,
            "options": opts,
            "votes": {o: 0 for o in opts},
            "started_at": time.time(),
        }

        options_str = " ".join([f"{chr(65+i)}.{o}" for i, o in enumerate(opts)])
        # Show vote on OBS overlay if available
        if self.obs_controller:
            try:
                self.obs_controller.show_vote(question, opts)
            except Exception:
                pass
        return (
            f"投票开始！{question}\n"
            f"选项：{options_str}\n"
            f"请在弹幕中回复选项字母参与投票！"
        )


# =====================================================================
# Countdown Tool
# =====================================================================

class CountdownInput(BaseModel):
    seconds: int = Field(default=60, description="Countdown duration in seconds.")
    event_name: str = Field(default="活动开始", description="What happens when countdown ends.")


class CountdownTool(BaseTool):
    """Tool to start a countdown timer with announcement."""
    name: str = "倒计时"
    description: str = (
        "当你想开始倒计时时，使用此工具。"
        "例如活动开始前倒计时、答题限时等。"
    )
    args_schema: Type[BaseModel] = CountdownInput
    return_direct: bool = False
    obs_controller: ClassVar[Optional[object]] = None  # Set externally

    def _run(self, seconds: int = 60, event_name: str = "活动开始",
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        mins = seconds // 60
        secs = seconds % 60
        if mins > 0:
            time_str = f"{mins}分{secs}秒" if secs else f"{mins}分钟"
        else:
            time_str = f"{secs}秒"
        # Show countdown on OBS overlay if available
        if self.obs_controller:
            try:
                self.obs_controller.show_countdown(seconds, event_name)
            except Exception:
                pass
        return f"倒计时开始！{time_str}后{event_name}！大家一起倒数吧！"


# =====================================================================
# Tool Registry
# =====================================================================

def get_interactive_tools() -> List[BaseTool]:
    """Return all interactive tools for registration with the agent."""
    return [
        IGEMQuizTool(),
        LotteryTool(),
        VoteTool(),
        CountdownTool(),
    ]
