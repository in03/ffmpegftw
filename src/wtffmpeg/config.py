from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from .llm import Profile, load_profile, DEFAULT_PROFILE_DIR

@dataclass(frozen=True)
class AppConfig:
    profile: Profile
    context_turns: int
    copy: bool
    exec_: bool
    prompt_once: Optional[str]
    preload_prompt: Optional[str]
