"""Short-term memory with summarization-based context compression.

Instead of truncating conversation history when it exceeds max_history,
compresses older messages into summary paragraphs that preserve
conversation flow and key information.

The context window is structured as:
  [injected_history] + [summaries as system message] + [recent_messages]
"""

import time
from copy import deepcopy
from typing import List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field
from zerolan.data.pipeline.llm import Conversation, RoleEnum


class SummaryEntry(BaseModel):
    """A compressed summary of older conversation turns."""
    summary_text: str = Field(..., description="LLM-generated summary of conversations.")
    message_count: int = Field(..., description="How many messages were compressed.")
    timestamp_range: Tuple[float, float] = Field(..., description="(first_msg_time, last_msg_time).")
    topics: List[str] = Field(default_factory=list, description="Key topics in this segment.")


class ShortTermMemoryConfig(BaseModel):
    """Configuration for short-term memory compression."""
    enable: bool = Field(default=True, description="Enable summarization-based context compression.")
    max_recent_messages: int = Field(default=10,
                                     description="Recent messages to keep uncompressed.")
    summary_threshold: int = Field(default=16,
                                   description="Compress when history exceeds this count.")
    max_summaries: int = Field(default=3,
                               description="Max compressed summary segments to keep.")
    max_summary_chars: int = Field(default=200,
                                   description="Max characters per summary segment.")


class ShortTermMemory:
    """Summarization-based context compression for short-term memory.

    Replaces the old hard-truncation strategy with LLM-generated summaries,
    preserving conversation context across longer interactions.

    Usage:
        stm = ShortTermMemory(config)
        new_history = stm.reconstruct_history(injected_history, current_history)
    """

    def __init__(self, config: ShortTermMemoryConfig):
        self._config = config
        self._summaries: List[SummaryEntry] = []

    def should_compress(self, current_history: List[Conversation]) -> bool:
        """Check if compression is needed."""
        if not self._config.enable:
            return False
        return len(current_history) > self._config.summary_threshold

    def compress(self, history: List[Conversation], keep_recent: int = None) -> List[Conversation]:
        """Compress older messages into a summary segment.

        Args:
            history: Full conversation history (excluding injected).
            keep_recent: Number of most recent messages to keep uncompressed.

        Returns:
            List of messages that were compressed (the ones removed).
        """
        if keep_recent is None:
            keep_recent = self._config.max_recent_messages

        # Messages to compress = all except the most recent ones
        messages_to_compress = history[:-keep_recent] if len(history) > keep_recent else []

        if not messages_to_compress:
            return []

        # Generate summary using LLM
        summary_text = self._generate_summary(messages_to_compress)

        # Truncate if too long
        if len(summary_text) > self._config.max_summary_chars:
            summary_text = summary_text[:self._config.max_summary_chars] + "..."

        # Extract topics (simple keyword extraction from the summary)
        topics = self._extract_topics(messages_to_compress)

        entry = SummaryEntry(
            summary_text=summary_text,
            message_count=len(messages_to_compress),
            timestamp_range=(time.time() - 300, time.time()),  # Approximate
            topics=topics,
        )

        self._summaries.append(entry)

        # Enforce max summaries limit
        while len(self._summaries) > self._config.max_summaries:
            self._summaries.pop(0)

        logger.debug(f"Short-term memory: compressed {len(messages_to_compress)} messages into summary. "
                     f"Total summaries: {len(self._summaries)}")

        return messages_to_compress

    def reconstruct_history(
        self,
        injected_history: List[Conversation],
        current_history: List[Conversation]
    ) -> List[Conversation]:
        """Full reconstruction: injected_history + summaries + recent messages.

        This replaces the old truncation logic in LLMPromptManager.reset_history().

        Args:
            injected_history: The base injected history from config.
            current_history: The current conversation history.

        Returns:
            Reconstructed history with compressed summaries.
        """
        if not self._config.enable:
            # Fallback: use old truncation behavior
            if len(current_history) <= len(injected_history) + self._config.summary_threshold:
                return deepcopy(current_history)
            return deepcopy(injected_history)

        # Calculate non-injected messages
        injected_len = len(injected_history)
        recent_messages = current_history[injected_len:]  # Messages after injected

        # Check if we need compression
        if len(recent_messages) > self._config.summary_threshold:
            # Compress older messages
            compressed = self.compress(recent_messages, self._config.max_recent_messages)
            if compressed:
                # Remove compressed messages from recent
                recent_messages = recent_messages[len(compressed):]

        # Build reconstructed history
        result = deepcopy(injected_history)

        # Add summaries as a system message
        if self._summaries:
            summary_text = self.build_summary_context()
            result.append(Conversation(
                role=RoleEnum.system,
                content=summary_text
            ))

        # Add recent messages
        result.extend(deepcopy(recent_messages))

        return result

    def build_summary_context(self) -> str:
        """Format all summaries into a context string for LLM injection.

        Returns a string like:
            [对话摘要]
            摘要1: ...
            摘要2: ...
        """
        if not self._summaries:
            return ""

        parts = ["[对话摘要]"]
        for i, entry in enumerate(self._summaries, 1):
            topics_str = "、".join(entry.topics[:3]) if entry.topics else "综合"
            parts.append(f"摘要{i}（{topics_str}）: {entry.summary_text}")

        return "\n".join(parts)

    def semantic_retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieve relevant past conversation snippets from summary buffer.

        Simple keyword-based search through summaries.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of relevant summary texts.
        """
        query_words = set(query.lower().split())
        scored = []

        for entry in self._summaries:
            # Score based on keyword overlap
            summary_words = set(entry.summary_text.lower().split())
            topic_words = set(w for t in entry.topics for w in t.lower().split())
            all_words = summary_words | topic_words
            overlap = len(query_words & all_words)
            if overlap > 0:
                scored.append((overlap, entry.summary_text))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k]]

    def _generate_summary(self, messages: List[Conversation]) -> str:
        """Generate a summary of the given messages using LLM.

        Reuses the summary_history() API from agent/api.py.
        """
        try:
            from agent.api import summary_history
            result = summary_history(messages)
            return result.content
        except Exception as e:
            logger.warning(f"Failed to generate conversation summary: {e}")
            # Fallback: simple concatenation
            parts = []
            for msg in messages[-6:]:  # Last 6 messages
                role = "用户" if msg.role == RoleEnum.user else "AI"
                parts.append(f"{role}: {msg.content[:50]}")
            return "; ".join(parts)

    def _extract_topics(self, messages: List[Conversation]) -> List[str]:
        """Simple topic extraction from messages.

        Extracts key nouns/topics from the conversation for summary indexing.
        """
        topics = []
        # Simple heuristic: look for question-like patterns
        for msg in messages:
            if msg.role == RoleEnum.user:
                content = msg.content.strip()
                # Extract short phrases as topics
                if len(content) <= 10:
                    topics.append(content)
                elif "？" in content or "?" in content:
                    # Take the part before the question mark
                    q = content.split("？")[0].split("?")[0].strip()
                    if len(q) <= 15:
                        topics.append(q)

        return topics[:5]  # Limit to 5 topics

    def reset(self):
        """Clear all summaries."""
        self._summaries.clear()
