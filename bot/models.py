from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Game:
    id: Optional[int]
    name: str
    acronym: str
    category_id: int
    created_at: Optional[datetime] = None


@dataclass
class Group:
    id: Optional[int]
    name: str
    emoji: str


@dataclass
class TemplateChannel:
    id: Optional[int]
    name: str
    group_name: str
    is_voice: bool = False
    description: Optional[str] = None


@dataclass
class GameChannel:
    id: Optional[int]
    game_id: int
    channel_id: int
    name: str
    group_name: str
    is_custom: bool = False
    is_voice: bool = False


@dataclass
class GameRole:
    id: Optional[int]
    game_id: int
    role_id: int
    suffix: str  # e.g., "-Coder"
