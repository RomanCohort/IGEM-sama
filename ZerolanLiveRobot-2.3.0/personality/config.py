"""Personality evolution configuration models."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TraitConfig(BaseModel):
    """Configuration for a single personality trait dimension."""
    name: str = Field(..., description="Trait name, e.g. 'lively', 'tsundere'.")
    default_value: float = Field(default=0.5, description="Starting value 0-1.")
    min_value: float = Field(default=0.0)
    max_value: float = Field(default=1.0)
    decay_rate: float = Field(default=0.005, description="How fast the trait decays toward default per second.")
    emotion_influence: Dict[str, float] = Field(default_factory=dict,
                                                description="How each emotion shifts this trait. e.g. {'happy': 0.02}")


class PersonalityEvolutionConfig(BaseModel):
    """Configuration for personality evolution behavior."""
    enable: bool = Field(default=True)
    persist_path: str = Field(default="data/personality_state.json")
    evolution_rate: float = Field(default=0.1, description="Overall speed of personality drift.")
    traits: List[TraitConfig] = Field(default_factory=lambda: [
        TraitConfig(name="lively", default_value=0.7, emotion_influence={
            "happy": 0.02, "excited": 0.03, "sad": -0.02, "calm": -0.01}),
        TraitConfig(name="tsundere", default_value=0.3, decay_rate=0.003, emotion_influence={
            "shy": 0.03, "angry": 0.02, "happy": -0.01}),
        TraitConfig(name="knowledgeable", default_value=0.6, decay_rate=0.004, emotion_influence={
            "curious": 0.02, "proud": 0.01}),
        TraitConfig(name="playful", default_value=0.5, emotion_influence={
            "excited": 0.03, "happy": 0.02, "calm": -0.01}),
        TraitConfig(name="warm", default_value=0.6, decay_rate=0.004, emotion_influence={
            "happy": 0.02, "shy": 0.01, "angry": -0.02}),
        TraitConfig(name="scientific", default_value=0.7, decay_rate=0.003, emotion_influence={
            "curious": 0.02, "proud": 0.01}),
    ])


class PersonalityConfig(BaseModel):
    """Top-level personality module configuration."""
    evolution: PersonalityEvolutionConfig = Field(default=PersonalityEvolutionConfig())
