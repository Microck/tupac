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


@dataclass
class Task:
    id: Optional[int]
    game_acronym: str
    title: str
    description: Optional[str]
    assignee_id: int
    target_channel_id: int
    thread_id: Optional[int]
    control_message_id: Optional[int]  # The embed message ID in the thread
    header_message_id: Optional[int]  # The embed message ID in the channel (before thread)
    status: str  # todo, progress, review, done, cancelled
    deadline: Optional[datetime]
    eta: Optional[str]
    priority: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class TaskHistory:
    id: Optional[int]
    task_id: int
    user_id: int
    action: str  # status_change, eta_update, etc.
    old_value: Optional[str]
    new_value: Optional[str]
    timestamp: Optional[datetime] = None


@dataclass
class TaskBoard:
    id: Optional[int]
    game_acronym: str
    channel_id: int
    message_ids: str  # JSON array of message IDs for the embeds
