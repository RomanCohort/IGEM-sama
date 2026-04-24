"""Personality state model and evolution logic.

Personality traits drift based on emotional experiences:
  1. Emotion influence: current dominant emotions push traits
  2. Decay: traits slowly return to default values
  3. Interaction density: more interactions = faster evolution

State is persisted to JSON for cross-session continuity.
"""

import json
import os
import time
from typing import Dict

from loguru import logger
from pydantic import BaseModel, Field

from personality.config import PersonalityEvolutionConfig, TraitConfig


class TraitState(BaseModel):
    """Current state of a single personality trait."""
    name: str
    value: float = 0.5
    default_value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    decay_rate: float = 0.005
    emotion_influence: Dict[str, float] = {}


class PersonalityState(BaseModel):
    """Full personality state, persisted across sessions."""
    traits: Dict[str, TraitState] = {}
    interaction_count: int = 0
    last_evolution_time: float = Field(default_factory=time.time)


class PersonalityEvolution:
    """Manages personality evolution over time.

    Usage:
        evolution = PersonalityEvolution(config)
        evolution.evolve(emotion_tracker.state.intensities, dt=1.0)
        prompt = evolution.build_system_prompt(base_prompt)
    """

    def __init__(self, config: PersonalityEvolutionConfig):
        self._config = config
        self._prompt_builder = None  # Lazy import to avoid circular dependency
        self._state = self._load()
        self._save_counter = 0
        self._save_interval = 60  # Save every 60 evolve calls

    def evolve(self, emotion_intensities: Dict[str, float], dt: float = 1.0):
        """Evolve personality based on current emotion state.

        Called periodically (e.g. every second from SecondEvent handler).
        Traits drift based on:
          1. Emotion influence: current dominant emotions push traits
          2. Decay: traits slowly return to default values

        Args:
            emotion_intensities: Dict of emotion_name → intensity (0-1).
            dt: Time delta in seconds since last evolve call.
        """
        if not self._config.enable:
            return

        rate = self._config.evolution_rate

        for name, trait in self._state.traits.items():
            # 1. Emotion influence
            emotion_shift = 0.0
            for emotion, influence in trait.emotion_influence.items():
                intensity = emotion_intensities.get(emotion, 0.0)
                emotion_shift += influence * intensity * rate * dt

            # 2. Decay toward default
            decay = (trait.default_value - trait.value) * trait.decay_rate * dt

            # Apply shift
            trait.value += emotion_shift + decay

            # Clamp to bounds
            trait.value = max(trait.min_value, min(trait.max_value, trait.value))

        self._state.interaction_count += 1
        self._state.last_evolution_time = time.time()

        # Periodic save
        self._save_counter += 1
        if self._save_counter >= self._save_interval:
            self._save_counter = 0
            self._save()

    def build_system_prompt(self, base_prompt: str) -> str:
        """Assemble a dynamic system prompt from current personality state.

        Appends trait-based personality modifiers to the base prompt.

        Args:
            base_prompt: The original static system prompt.

        Returns:
            Enhanced system prompt with personality context.
        """
        if not self._config.enable:
            return base_prompt

        # Lazy import to avoid circular dependency
        if self._prompt_builder is None:
            from personality.prompt_builder import PersonalityPromptBuilder
            self._prompt_builder = PersonalityPromptBuilder()

        extension = self._prompt_builder.build_prompt_extension(self._state)
        if not extension:
            return base_prompt

        return f"{base_prompt}\n\n{extension}"

    def get_state(self) -> PersonalityState:
        """Return current personality state."""
        return self._state

    def get_trait(self, name: str) -> float:
        """Get current value of a specific trait."""
        trait = self._state.traits.get(name)
        return trait.value if trait else 0.5

    def _load(self) -> PersonalityState:
        """Load personality state from persistence file."""
        state = PersonalityState()

        # Initialize traits from config
        for tc in self._config.traits:
            state.traits[tc.name] = TraitState(
                name=tc.name,
                value=tc.default_value,
                default_value=tc.default_value,
                min_value=tc.min_value,
                max_value=tc.max_value,
                decay_rate=tc.decay_rate,
                emotion_influence=tc.emotion_influence,
            )

        # Load persisted values if available
        if os.path.exists(self._config.persist_path):
            try:
                with open(self._config.persist_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                persisted = PersonalityState.model_validate(data)
                # Merge persisted values into initialized traits
                for name, trait in persisted.traits.items():
                    if name in state.traits:
                        state.traits[name].value = trait.value
                state.interaction_count = persisted.interaction_count
                logger.info(f"Personality state loaded from {self._config.persist_path}")
            except Exception as e:
                logger.warning(f"Failed to load personality state: {e}")

        return state

    def _save(self):
        """Save personality state to persistence file."""
        try:
            os.makedirs(os.path.dirname(self._config.persist_path), exist_ok=True)
            with open(self._config.persist_path, 'w', encoding='utf-8') as f:
                f.write(self._state.model_dump_json(indent=2))
        except Exception as e:
            logger.warning(f"Failed to save personality state: {e}")
