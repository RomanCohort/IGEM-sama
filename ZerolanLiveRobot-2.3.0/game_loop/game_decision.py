"""LLM-based game decision making.

Takes the current game state and decides on actions to execute.
For Minecraft: delegates to KonekoMinecraftAIAgent via WebSocket.
For screen-based games: uses LLM to decide keyboard/mouse actions.
"""

from collections import deque
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

from game_loop.config import GameLoopConfig
from game_loop.game_perception import GameState


class GameAction(BaseModel):
    """A single game action to execute."""
    action_type: str  # "key_press", "mouse_click", "mouse_move", "minecraft_command"
    params: Dict[str, Any] = {}
    description: str = ""


class GameDecision:
    """LLM-based game decision making.

    Usage:
        decision = GameDecision(llm_pipeline, game_agent, config)
        actions = decision.decide(game_state)
    """

    # System prompt for game decision making
    _DECISION_SYSTEM_PROMPT = (
        "你是一个游戏AI助手。根据当前游戏画面的描述，决定下一步应该做什么操作。\n"
        "请以JSON格式返回操作列表，每个操作包含:\n"
        "  - action_type: 'key_press'(按键), 'mouse_click'(点击), 'minecraft_command'(MC指令)\n"
        "  - params: 操作参数，如 {'key': 'w'} 或 {'x': 100, 'y': 200}\n"
        "  - description: 操作描述\n"
        "最多返回3个操作。如果不确定该做什么，返回空列表。"
    )

    def __init__(self, llm_pipeline, game_agent=None, config: GameLoopConfig = None):
        self._llm = llm_pipeline
        self._game_agent = game_agent
        self._config = config
        self._action_history: deque = deque(maxlen=20)

    def decide(self, game_state: GameState) -> List[GameAction]:
        """Given the current game state, decide on next actions.

        Args:
            game_state: Current game state from GamePerception.

        Returns:
            List of GameAction to execute.
        """
        if not game_state or not game_state.game_context:
            return []

        if self._config and self._config.platform.value == "minecraft" and self._game_agent:
            return self._decide_minecraft(game_state)
        else:
            return self._decide_screen_based(game_state)

    def _decide_minecraft(self, game_state: GameState) -> List[GameAction]:
        """Minecraft-specific decision using Koneko protocol."""
        # For Minecraft, delegate to the game agent with context
        try:
            if game_state.game_context:
                self._game_agent.exec_instruction(game_state.game_context)
            return [GameAction(
                action_type="minecraft_command",
                params={"command": game_state.game_context},
                description="Delegate to Minecraft agent",
            )]
        except Exception as e:
            logger.warning(f"Minecraft decision failed: {e}")
            return []

    def _decide_screen_based(self, game_state: GameState) -> List[GameAction]:
        """Generic screen-based game decision using LLM."""
        try:
            from zerolan.data.pipeline.llm import LLMQuery, Conversation, RoleEnum

            history = [
                Conversation(role=RoleEnum.system, content=self._DECISION_SYSTEM_PROMPT),
                Conversation(role=RoleEnum.user, content=game_state.game_context),
            ]
            query = LLMQuery(text="请决定下一步操作。", history=history)
            prediction = self._llm.predict(query)

            if not prediction or not prediction.response:
                return []

            # Parse LLM response into actions (best-effort JSON parsing)
            actions = self._parse_actions(prediction.response)
            self._action_history.extend(actions)
            return actions

        except Exception as e:
            logger.warning(f"Screen-based decision failed: {e}")
            return []

    def _parse_actions(self, response: str) -> List[GameAction]:
        """Parse LLM response into GameAction list (best-effort)."""
        import json
        actions = []

        # Try to extract JSON from response
        try:
            # Look for JSON array in the response
            start = response.find('[')
            end = response.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                action_dicts = json.loads(json_str)
                for d in action_dicts[:3]:  # Limit to 3 actions
                    actions.append(GameAction(
                        action_type=d.get("action_type", "key_press"),
                        params=d.get("params", {}),
                        description=d.get("description", ""),
                    ))
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback: treat the whole response as a description
            if len(response.strip()) > 0:
                actions.append(GameAction(
                    action_type="key_press",
                    params={"key": "space"},
                    description=f"LLM suggested: {response[:100]}",
                ))

        return actions
