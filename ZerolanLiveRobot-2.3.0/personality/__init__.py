"""Personality evolution system for IGEM-sama.

Enables dynamic personality that evolves based on emotional experiences
and viewer interactions over time.
"""

from personality.config import PersonalityConfig, PersonalityEvolutionConfig, TraitConfig
from personality.personality_state import PersonalityEvolution, PersonalityState, TraitState
from personality.prompt_builder import PersonalityPromptBuilder

__all__ = [
    "PersonalityConfig",
    "PersonalityEvolutionConfig",
    "TraitConfig",
    "PersonalityEvolution",
    "PersonalityState",
    "TraitState",
    "PersonalityPromptBuilder",
]
