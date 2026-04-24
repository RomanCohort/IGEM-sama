"""Builds and manages visual context for LLM injection.

Provides context strings that are injected into the LLM query
in emit_llm_prediction, similar to how RAG and emotion context
are currently injected.
"""

from perception.visual_loop import VisualLoop
from perception.config import PerceptionConfig


class PerceptionContext:
    """Builds visual context for LLM injection.

    Usage:
        ctx = PerceptionContext(visual_loop, config)
        context_str = ctx.build_context()  # Returns "[视觉观察] ..."
    """

    def __init__(self, visual_loop: VisualLoop, config: PerceptionConfig):
        self._visual_loop = visual_loop
        self._config = config

    def build_context(self) -> str:
        """Build the full perception context string.

        Called from emit_llm_prediction before creating the LLMQuery.
        Returns empty string if no observations are available.
        """
        if not self._config.visual.enable:
            return ""
        return self._visual_loop.get_context()
