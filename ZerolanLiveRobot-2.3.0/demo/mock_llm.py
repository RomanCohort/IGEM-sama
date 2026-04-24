"""Mock LLM for demo mode — keyword-matched preset responses.

No real LLM API needed. Returns contextual responses about the
IGEM-FBH project based on keyword matching, with emotion-aware
tone adjustments.
"""

import random
import re
import time
from typing import Optional


# Keyword → response rules. First match wins; order matters.
RULES: list[tuple[str, list[str]]] = [
    # Greetings
    (r"你好|hello|嗨|hi|哈喽|嘿", [
        "你好呀！我是IGEM-sama，很高兴见到你！",
        "嗨嗨！欢迎来到IGEM-FBH的直播间！",
        "你好～今天想来了解什么生物学知识呢？",
    ]),
    # Self-introduction
    (r"你是谁|自我介绍|叫什么|什么名字", [
        "我是IGEM-sama！IGEM-FBH队伍的AI形象大使，负责向全世界安利合成生物学！",
        "我叫IGEM-sama，是一支iGEM竞赛队伍的AI吉祥物，可以回答关于我们项目的各种问题哦！",
    ]),
    # Project overview
    (r"项目|project|做什么|研究方向", [
        "我们IGEM-FBH团队的项目聚焦合成生物学创新！我们设计新型生物元件来解决实际问题，让生物学为人类服务！",
        "我们的项目致力于用合成生物学的方法，设计创新的生物系统。具体来说，我们在构建新的基因回路和功能元件！",
        "IGEM-FBH的项目是从生物元件设计出发，通过工程化思路构建有用的生物系统。听起来很酷吧！",
    ]),
    # iGEM competition
    (r"iGEM|igem|竞赛|比赛|大赛", [
        "iGEM是国际基因工程机器大赛，是全球最大的合成生物学竞赛！每年有来自世界各地的队伍参加！",
        "iGEM大赛从2003年开始，现在每年有超过300支队伍参赛！我们IGEM-FBH就是其中之一！",
        "iGEM不仅是比赛，更是一个全球合成生物学社区！大家在这里分享、合作、创新！",
    ]),
    # Synthetic biology
    (r"合成生物|synthetic|基因工程|bioengineering", [
        "合成生物学就像是生物界的乐高！我们把标准化的生物元件组合起来，构建新的生物系统！",
        "合成生物学的核心思想是工程化：把生物系统分解成标准元件，再像搭积木一样组装！",
        "合成生物学让我们能够设计全新的生物功能！从药物生产到环境治理，应用前景超广阔！",
    ]),
    # Team info
    (r"队伍|团队|team|IGEM-FBH|fbh", [
        "IGEM-FBH是一支充满热情的iGEM队伍！我们来自不同的学科背景，但都热爱合成生物学！",
        "我们的团队有湿实验组、干实验组和人文实践组，分工合作完成项目！",
        "IGEM-FBH的每个成员都很厉害！我们互相学习、共同进步，这就是团队的力量！",
    ]),
    # BioBrick / parts
    (r"元件|BioBrick|parts|生物砖|基因元件", [
        "BioBrick是标准化的生物元件，就像电子元件有电阻电容一样，生物也有标准化的功能单元！",
        "我们设计的生物元件可以在iGEM Registry注册，让全世界的研究者都能使用！",
        "生物元件包括启动子、核糖体结合位点、编码序列、终止子等，它们是合成生物学的基石！",
    ]),
    # Wet lab
    (r"湿实验|wetlab|wet lab|实验|实验操作", [
        "湿实验是iGEM项目的核心！我们在实验室里进行DNA组装、蛋白表达、功能验证等实验！",
        "湿实验组负责把我们设计的基因回路在实验室中实现，验证功能是否和预期一致！",
    ]),
    # Dry lab / modeling
    (r"干实验|drylab|dry lab|建模|模型|modeling", [
        "干实验主要是数学建模和计算机仿真！我们用模型来预测和优化生物系统的行为！",
        "通过建模，我们可以在电脑上先验证设计思路，再进入实验室，提高实验效率！",
    ]),
    # Safety
    (r"安全|safety|伦理|风险|规范", [
        "安全是合成生物学最重要的原则！我们严格遵守实验室安全规范，确保实验过程不会对环境和人体造成危害！",
        "iGEM非常重视安全与伦理，每个队伍都要提交安全表格，接受安全委员会的审核！",
    ]),
    # Human practices
    (r"人文|实践|human|HP|社会", [
        "人文实践是iGEM的重要组成部分！我们走出实验室，与社会对话，听取公众的意见！",
        "我们通过科普活动、问卷调查、专家访谈等方式，让更多人了解合成生物学！",
    ]),
    # Collaboration
    (r"合作|collaboration|交流|其他队伍", [
        "iGEM鼓励队伍间的合作！我们和其他队伍交流经验、共享资源，一起推动项目进步！",
        "合作让科学更有温度！我们和其他iGEM队伍互帮互助，共同成长！",
    ]),
    # Compliments
    (r"厉害|棒|牛|赞|666|nb|强|优秀", [
        "嘿嘿谢谢夸奖！都是团队的功劳！我们IGEM-FBH超棒的！",
        "谢谢谢谢！你们也很厉害呀，能关注到合成生物学说明很有眼光！",
        "太开心啦！被夸奖了！我会继续努力传播合成生物学知识的！",
    ]),
    # Sad/negative
    (r"难过|伤心|不开心|难受|惨", [
        "别难过呀！有什么不开心的可以说出来，IGEM-sama陪你聊天！",
        "抱抱！要开心起来哦，生活总有美好的事情等着你！",
    ]),
    # Thanks
    (r"谢谢|感谢|thank", [
        "不客气！能帮到你我也很开心！",
        "不用谢～有问题随时问我！",
    ]),
    # Goodbye
    (r"再见|拜拜|bye|晚安|下次见", [
        "拜拜～下次记得再来玩哦！IGEM-sama等你！",
        "再见啦！祝一切顺利，下次直播见！",
    ]),
    # Fun / casual
    (r"唱歌|唱歌给我们听|会唱歌吗", [
        "唱歌嘛...我还不太会，但我可以给你讲个生物学冷知识！你知道吗，人体内的DNA拉直了可以往返太阳300次！",
    ]),
    (r"有趣|好玩|有意思|酷", [
        "对吧对吧！合成生物学就是这么有趣！每天都有新发现！",
        "科学就是这样，越了解越觉得神奇！",
    ]),
    (r"吃|食物|饿|美食", [
        "说到吃的，你知道酵母菌可以做面包和啤酒吗？这也是合成生物学的应用哦！微生物小厨师！",
        "我虽然不能吃东西，但我知道合成生物学可以帮助生产更营养的食物！比如富含维生素的黄金大米！",
    ]),
]

# Fallback responses when no keyword matches
FALLBACK = [
    "嗯嗯，这个话题很有意思！你对合成生物学感兴趣吗？",
    "我想想...说到这个，我倒是可以给你讲讲我们IGEM-FBH的项目！",
    "收到！有什么想了解的可以随时问我，关于iGEM、合成生物学、我们队伍的问题都行！",
    "哦哦，了解了解～对了，你知道iGEM是什么吗？我可以给你介绍一下！",
    "好问题！让我想想...其实如果你对我们的项目感兴趣，可以问我更具体的问题哦！",
    "嗯嗯～欢迎来我的直播间！有什么想聊的尽管说！",
]

# Emotion tone modifiers (appended/prepended based on current emotion)
EMOTION_TONES: dict[str, list[str]] = {
    "happy": ["嘿嘿～ ", "好开心呀！"],
    "excited": ["哇！！", "太激动了！"],
    "sad": ["呜呜...", "唉..."],
    "angry": ["哼！", "真让人着急！"],
    "shy": ["(小声) ", "...不好意思..."],
    "curious": ["咦？", "让我想想..."],
    "proud": ["哼哼，", "我们队当然厉害！"],
    "neutral": ["", ""],
    "calm": ["", ""],
}


class MockLLM:
    """Keyword-matched mock LLM for demo mode."""

    def __init__(self):
        self._compiled_rules = [
            (re.compile(pattern, re.IGNORECASE), responses)
            for pattern, responses in RULES
        ]
        self._history: list[str] = []
        self._response_count = 0

    def predict(self, text: str, emotion: str = "neutral") -> str:
        """Generate a mock response based on keyword matching.

        Args:
            text: Input text (danmaku content).
            emotion: Current dominant emotion label.

        Returns:
            A mock response string.
        """
        # Try keyword rules
        for pattern, responses in self._compiled_rules:
            if pattern.search(text):
                response = random.choice(responses)
                break
        else:
            response = random.choice(FALLBACK)

        # Apply emotion tone
        tone_prefix, tone_suffix = EMOTION_TONES.get(emotion, ("", ""))
        if tone_prefix:
            response = tone_prefix + response
        if tone_suffix and random.random() < 0.3:
            response = response + tone_suffix

        # Track
        self._response_count += 1
        self._history.append(response)
        if len(self._history) > 20:
            self._history.pop(0)

        return response

    @property
    def response_count(self) -> int:
        return self._response_count


# Predefined simulated viewer names
SIM_VIEWERS = [
    "生物小白", "DNA猎人", "蛋白折叠大师", "基因编辑爱好者",
    "实验鼠007", "PCR之王", "酶切小能手", "细胞培养员",
    "质粒收藏家", "引物设计师", "转化达人", "电泳判读者",
    "iGEM老粉", "合成生物迷", "干实验大佬", "湿实验专家",
    "实验室常客", "生物信息学", "模型构建师", "科普爱好者",
]

# Predefined simulated danmaku
SIM_DANMAKU = [
    "你好呀！",
    "你们的项目是做什么的？",
    "什么是iGEM？",
    "合成生物学是什么？",
    "介绍一下你们的队伍吧",
    "好厉害啊！",
    "什么是BioBrick？",
    "湿实验是干嘛的？",
    "你们的建模是怎么做的？",
    "安全方面有什么考虑？",
    "人文实践做了什么？",
    "你们和其他队伍有合作吗？",
    "666",
    "太酷了吧",
    "涨知识了",
    "来支持你们！",
    "加油！",
    "你们的项目有什么创新点？",
    "iGEM比赛难不难？",
    "怎么参加iGEM？",
]
