"""Dynamic system prompt assembly from personality traits.

Maps trait values (0-1) to Chinese personality descriptions that
are appended to the base system prompt for runtime personality control.
"""

from typing import Dict, List, Tuple

from personality.personality_state import PersonalityState


class PersonalityPromptBuilder:
    """Builds dynamic system prompt additions from personality traits.

    Maps trait values to descriptive Chinese text that guides the LLM's
    personality expression. Each trait has value ranges that map to
    different personality descriptions.
    """

    # Maps trait values to Chinese personality descriptions
    # Format: {trait_name: [(low_bound, high_bound, description), ...]}
    TRAIT_DESCRIPTIONS: Dict[str, List[Tuple[float, float, str]]] = {
        "lively": [
            (0.0, 0.3, "你现在比较安静，说话简洁"),
            (0.3, 0.6, "你说话正常，偶尔活跃"),
            (0.6, 0.8, "你现在比较活泼，喜欢用感叹号和语气词"),
            (0.8, 1.0, "你现在非常活跃，说话充满热情和活力！"),
        ],
        "tsundere": [
            (0.0, 0.3, ""),
            (0.3, 0.6, "偶尔会有点嘴硬"),
            (0.6, 0.8, "你有点傲娇，嘴上说着不在意但其实很在意"),
            (0.8, 1.0, "你非常傲娇，总是嘴硬但内心很柔软"),
        ],
        "knowledgeable": [
            (0.0, 0.3, "简单回答问题"),
            (0.3, 0.6, "正常回答，偶尔展开解释"),
            (0.6, 0.8, "你喜欢详细解释原理，善于类比"),
            (0.8, 1.0, "你非常博学，喜欢深入讲解，会引用数据和文献"),
        ],
        "playful": [
            (0.0, 0.3, "你的语气比较正经"),
            (0.3, 0.6, "你偶尔会开个小玩笑"),
            (0.6, 0.8, "你比较调皮，喜欢逗观众开心"),
            (0.8, 1.0, "你非常调皮搞怪，总是想整点活儿"),
        ],
        "warm": [
            (0.0, 0.3, "你保持礼貌但有些冷淡"),
            (0.3, 0.6, "你态度友好温和"),
            (0.6, 0.8, "你非常关心观众，语气温暖体贴"),
            (0.8, 1.0, "你像大姐姐一样关心每个人，总是温柔鼓励"),
        ],
        "scientific": [
            (0.0, 0.3, ""),
            (0.3, 0.6, "科普时用简单易懂的语言"),
            (0.6, 0.8, "你乐于科普，会用通俗的方式解释科学概念"),
            (0.8, 1.0, "你热衷于科普，总是想找机会分享有趣的科学知识"),
        ],
    }

    def build_prompt_extension(self, state: PersonalityState) -> str:
        """Generate personality prompt text from current trait values.

        Args:
            state: Current personality state.

        Returns:
            Formatted personality context string, or empty string if
            no significant traits are active.
        """
        descriptions = []

        for trait_name, trait_state in state.traits.items():
            desc = self._get_trait_description(trait_name, trait_state.value)
            if desc:
                # Format with percentage for clarity
                pct = int(trait_state.value * 100)
                descriptions.append(f"{self._trait_display_name(trait_name)}{pct}%({desc})")

        if not descriptions:
            return ""

        return "【当前性格倾向】" + "，".join(descriptions)

    def _get_trait_description(self, trait_name: str, value: float) -> str:
        """Get the description for a trait at its current value."""
        ranges = self.TRAIT_DESCRIPTIONS.get(trait_name, [])
        for low, high, desc in ranges:
            if low <= value < high:
                return desc
        # Handle value == 1.0 (falls through upper bound)
        if ranges and value >= 1.0:
            return ranges[-1][2]
        return ""

    @staticmethod
    def _trait_display_name(trait_name: str) -> str:
        """Map internal trait names to display names."""
        names = {
            "lively": "活泼度",
            "tsundere": "傲娇度",
            "knowledgeable": "博学度",
            "playful": "调皮度",
            "warm": "温柔度",
            "scientific": "科普度",
        }
        return names.get(trait_name, trait_name)
