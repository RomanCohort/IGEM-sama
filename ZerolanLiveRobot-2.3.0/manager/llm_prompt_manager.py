from copy import deepcopy
from typing import Optional

from zerolan.data.pipeline.llm import Conversation, RoleEnum

from character.config import ChatConfig
from memory.short_term import ShortTermMemory, ShortTermMemoryConfig


class LLMPromptManager:
    def __init__(self, config: ChatConfig):
        self.system_prompt: str = config.system_prompt
        self.injected_history: list[Conversation] = self._parse_history_list(config.injected_history,
                                                                             self.system_prompt)
        self.current_history: list[Conversation] = deepcopy(self.injected_history)
        self.max_history = config.max_history

        # Short-term memory with summarization compression
        stm_config = config.short_term_memory if hasattr(config, 'short_term_memory') and config.short_term_memory else ShortTermMemoryConfig(
            summary_threshold=config.max_history,
            max_recent_messages=config.max_history // 2,
        )
        self.short_term_memory = ShortTermMemory(stm_config)

    def reset_history(self, history: list[Conversation]) -> None:
        """
        Resets `current_history` with deepcopy.
        If the length of `current_history` is greater than the `max_history`,
        uses short-term memory compression instead of hard truncation.
        :param history: List of instances of class Conversation
        :return: None
        """
        if history is None:
            self.current_history = deepcopy(self.injected_history)
        else:
            if len(history) <= self.max_history:
                self.current_history = deepcopy(history)
            else:
                # Use summarization-based compression instead of hard truncation
                self.current_history = self.short_term_memory.reconstruct_history(
                    self.injected_history, history
                )

    def update_system_prompt(self, new_prompt: str) -> None:
        """Update the system prompt dynamically (e.g. for personality evolution).

        Replaces the first system message in injected_history and
        updates the system_prompt field.

        Args:
            new_prompt: The new system prompt text.
        """
        self.system_prompt = new_prompt
        # Update the first message (system prompt) in injected_history
        if self.injected_history and self.injected_history[0].role == RoleEnum.system:
            self.injected_history[0] = Conversation(role=RoleEnum.system, content=new_prompt)
        # Also update in current_history if it starts with a system message
        if self.current_history and self.current_history[0].role == RoleEnum.system:
            self.current_history[0] = Conversation(role=RoleEnum.system, content=new_prompt)

    @staticmethod
    def _parse_history_list(history: list[str], system_prompt: str | None = None) -> list[Conversation]:
        result = []

        if system_prompt is not None:
            result.append(Conversation(role=RoleEnum.system, content=system_prompt))

        for idx, content in enumerate(history):
            role = RoleEnum.user if idx % 2 == 0 else RoleEnum.assistant
            conversation = Conversation(role=role, content=content)
            result.append(conversation)

        return result
