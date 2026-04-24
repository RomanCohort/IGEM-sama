"""Long-Term Memory System for IGEM-sama.

Provides cross-session memory persistence with:
  - Episodic memory: key events and conversations worth remembering
  - Viewer memory: remembers returning viewers and their preferences
  - Memory decay: older/less important memories fade over time
  - Semantic retrieval: find relevant memories via keyword/semantic search

All memories are persisted to a local JSON file and optionally to Milvus.
"""

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """A single long-term memory."""
    id: str = Field(..., description="Unique memory ID.")
    content: str = Field(..., description="The memory text.")
    category: str = Field(default="general", description="Memory category: 'event', 'viewer', 'fact', 'general'.")
    importance: float = Field(default=0.5, description="Importance score 0-1 (affects decay rate).")
    created_at: float = Field(default_factory=time.time, description="Unix timestamp when created.")
    last_accessed: float = Field(default_factory=time.time, description="Unix timestamp when last accessed.")
    access_count: int = Field(default=0, description="How many times this memory was retrieved.")
    tags: List[str] = Field(default_factory=list, description="Searchable tags.")


class ViewerProfile(BaseModel):
    """Profile for a returning viewer."""
    uid: str = Field(..., description="Viewer's platform UID.")
    username: str = Field(default="", description="Viewer's display name.")
    platform: str = Field(default="bilibili", description="Platform name.")
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    visit_count: int = Field(default=1)
    notes: List[str] = Field(default_factory=list, description="Notable things about this viewer.")
    preferences: List[str] = Field(default_factory=list, description="Topics they're interested in.")


class LongTermMemory:
    """Manages IGEM-sama's persistent memories.

    Memories are saved to a JSON file and survive across sessions.
    Use the `retrieve` method to find relevant memories before LLM calls.
    """

    _HALF_LIFE_SECONDS = 86400 * 7  # 7 days base half-life; scaled by importance

    def __init__(self, persist_path: str = "data/long_term_memory.json"):
        self._persist_path = Path(persist_path)
        self._lock = threading.RLock()
        self.memories: Dict[str, MemoryEntry] = {}
        self.viewers: Dict[str, ViewerProfile] = {}
        self._load()

    # ------------------------------------------------------------------
    # Memory CRUD
    # ------------------------------------------------------------------

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """Store a new long-term memory. Thread-safe."""
        with self._lock:
            entry = MemoryEntry(
                id=str(uuid.uuid4())[:8],
                content=content,
                category=category,
                importance=max(0.0, min(1.0, importance)),
                tags=tags or [],
            )
            self.memories[entry.id] = entry
            self._save()
            logger.info(f"Added memory [{entry.id}]: {content[:50]}...")
            return entry

    def retrieve(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[MemoryEntry]:
        """Find relevant memories using simple keyword matching + decay scoring.

        For production use, integrate with Milvus for semantic search.
        Thread-safe.
        """
        with self._lock:
            scored: List[tuple] = []
            query_lower = query.lower()
            query_words = set(query_lower.split())

            for entry in self.memories.values():
                if category and entry.category != category:
                    continue

                # Keyword match score
                content_lower = entry.content.lower()
                tag_lower = " ".join(entry.tags).lower()
                match_score = 0.0
                for word in query_words:
                    if word in content_lower or word in tag_lower:
                        match_score += 0.3

                # Recency bonus (newer = higher)
                age = time.time() - entry.created_at
                recency = max(0, 1.0 - age / (86400 * 30))  # 30-day window

                # Access frequency bonus
                freq_bonus = min(entry.access_count * 0.1, 0.5)

                # Importance weight
                imp = entry.importance

                # Effective score (0 if no keyword match at all)
                total = (match_score + recency * 0.2 + freq_bonus * 0.1) * (0.5 + imp * 0.5)

                if match_score > 0 or recency > 0.7:
                    scored.append((total, entry))

            scored.sort(key=lambda x: x[0], reverse=True)

            # Update access stats
            results = []
            for _, entry in scored[:top_k]:
                entry.last_accessed = time.time()
                entry.access_count += 1
                results.append(entry)

            self._save()
            return results

    def remove_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID. Thread-safe."""
        with self._lock:
            if memory_id in self.memories:
                del self.memories[memory_id]
                self._save()
                return True
            return False

    # ------------------------------------------------------------------
    # Viewer Profiles
    # ------------------------------------------------------------------

    def track_viewer(self, uid: str, username: str = "", platform: str = "bilibili") -> ViewerProfile:
        """Record a viewer visit, creating or updating their profile. Thread-safe."""
        with self._lock:
            key = f"{platform}:{uid}"
            if key in self.viewers:
                profile = self.viewers[key]
                profile.last_seen = time.time()
                profile.visit_count += 1
                if username:
                    profile.username = username
            else:
                profile = ViewerProfile(uid=uid, username=username, platform=platform)
                self.viewers[key] = profile
            self._save()
            return profile

    def get_viewer(self, uid: str, platform: str = "bilibili") -> Optional[ViewerProfile]:
        """Look up a viewer by UID. Thread-safe."""
        with self._lock:
            return self.viewers.get(f"{platform}:{uid}")

    def add_viewer_note(self, uid: str, note: str, platform: str = "bilibili"):
        """Add a note about a viewer. Thread-safe."""
        with self._lock:
            key = f"{platform}:{uid}"
            if key in self.viewers:
                self.viewers[key].notes.append(note)
                self._save()

    # ------------------------------------------------------------------
    # Decay & Cleanup
    # ------------------------------------------------------------------

    def apply_decay(self):
        """Remove memories that have decayed below threshold. Thread-safe."""
        with self._lock:
            now = time.time()
            to_remove = []
            for mid, entry in self.memories.items():
                age = now - entry.created_at
                half_life = self._HALF_LIFE_SECONDS * (0.5 + entry.importance)
                # Exponential decay
                decay_factor = 0.5 ** (age / half_life)
                # Access count slows decay
                decay_factor *= min(1.0 + entry.access_count * 0.1, 3.0)
                if decay_factor < 0.05:
                    to_remove.append(mid)

            for mid in to_remove:
                logger.debug(f"Decayed memory: {self.memories[mid].content[:40]}...")
                del self.memories[mid]

            if to_remove:
                self._save()

    # ------------------------------------------------------------------
    # Context Building
    # ------------------------------------------------------------------

    def build_viewer_context(self, uid: str, username: str, platform: str = "bilibili") -> str:
        """Build a context string about a returning viewer for LLM injection. Thread-safe."""
        # track_viewer is already thread-safe with its own lock acquisition (RLock)
        profile = self.track_viewer(uid, username, platform)
        with self._lock:
            parts = []

            if profile.visit_count > 1:
                parts.append(f'这是老观众"{username}"，第{profile.visit_count}次来直播间。')
            else:
                parts.append(f'这是新观众"{username}"。')

            if profile.notes:
                parts.append(f"关于TA的备注：{'；'.join(profile.notes[-3:])}")

            if profile.preferences:
                parts.append(f"感兴趣的话题：{'、'.join(profile.preferences[:3])}")

            return " ".join(parts)

    def build_memory_context(self, query: str, top_k: int = 3) -> str:
        """Build a context string from relevant memories for LLM injection. Thread-safe."""
        # retrieve is already thread-safe with its own lock acquisition (RLock)
        entries = self.retrieve(query, top_k=top_k)
        if not entries:
            return ""

        lines = ["[长期记忆]"]
        for entry in entries:
            lines.append(f"- {entry.content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        """Persist to disk using atomic write (write-to-temp then rename)."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "memories": {k: v.model_dump() for k, v in self.memories.items()},
                "viewers": {k: v.model_dump() for k, v in self.viewers.items()},
            }
            content = json.dumps(data, ensure_ascii=False, indent=2)
            # Atomic write: write to temp file in same dir, then rename
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._persist_path.parent), suffix=".json"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, str(self._persist_path))
            except Exception:
                os.unlink(tmp_path)
                raise
        except Exception as e:
            logger.warning(f"Failed to save long-term memory: {e}")

    def _load(self):
        if not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for k, v in data.get("memories", {}).items():
                self.memories[k] = MemoryEntry.model_validate(v)
            for k, v in data.get("viewers", {}).items():
                self.viewers[k] = ViewerProfile.model_validate(v)
            logger.info(f"Loaded {len(self.memories)} memories, {len(self.viewers)} viewer profiles.")
        except Exception as e:
            logger.warning(f"Failed to load long-term memory: {e}")
