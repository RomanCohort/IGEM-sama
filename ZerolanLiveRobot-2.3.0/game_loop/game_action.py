"""Game action executor via keyboard/mouse or WebSocket.

Executes game actions decided by GameDecision, using:
  - pyautogui for screen-based games (keyboard/mouse)
  - KonekoMinecraftAIAgent for Minecraft (WebSocket)
"""

from typing import List

from loguru import logger

from game_loop.game_decision import GameAction


class GameActionExecutor:
    """Executes game actions via keyboard/mouse or WebSocket.

    Usage:
        executor = GameActionExecutor(game_agent)
        executor.execute(actions)
    """

    def __init__(self, game_agent=None):
        self._game_agent = game_agent

    def execute(self, actions: List[GameAction]):
        """Execute a list of game actions."""
        for action in actions:
            self._execute_one(action)

    def _execute_one(self, action: GameAction):
        """Execute a single game action."""
        try:
            if action.action_type == "key_press":
                self._key_press(action.params)
            elif action.action_type == "mouse_click":
                self._mouse_click(action.params)
            elif action.action_type == "mouse_move":
                self._mouse_move(action.params)
            elif action.action_type == "minecraft_command":
                self._minecraft_command(action.params)
            else:
                logger.debug(f"Unknown action type: {action.action_type}")
        except Exception as e:
            logger.warning(f"Action execution failed ({action.action_type}): {e}")

    def _key_press(self, params: dict):
        """Press a keyboard key."""
        import pyautogui
        key = params.get("key", "")
        if key:
            pyautogui.press(key)
            logger.debug(f"Key press: {key}")

    def _mouse_click(self, params: dict):
        """Click at screen coordinates."""
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        if x and y:
            pyautogui.click(x, y)
            logger.debug(f"Mouse click: ({x}, {y})")

    def _mouse_move(self, params: dict):
        """Move mouse to screen coordinates."""
        import pyautogui
        x = params.get("x", 0)
        y = params.get("y", 0)
        if x and y:
            pyautogui.moveTo(x, y)
            logger.debug(f"Mouse move: ({x}, {y})")

    def _minecraft_command(self, params: dict):
        """Send command to Minecraft agent via WebSocket."""
        command = params.get("command", "")
        if command and self._game_agent:
            self._game_agent.exec_instruction(command)
            logger.debug(f"MC command: {command}")
