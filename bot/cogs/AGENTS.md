# BOT COGS KNOWLEDGE BASE

**Context:** Feature implementations, Slash Commands, UI Views

## STRUCTURE
```
bot/cogs/
├── games.py     # /game (new, delete, list, addchannel, removechannel, member, members)
├── templates.py # /template (list, add, remove, sync, export, import, groups, emoji)
├── tasks.py     # /task (new, close, list, board, help)
└── setup.py     # /admin (setup, status, migrate, channels, members)
```

## PATTERNS
- UI classes (`discord.ui.View`, `Modal`) defined in same file as Cog
- `custom_id` format: `action:id` (e.g., `task_start:123`)
- Views re-registered in `setup()` hook for persistence
- Heavy use of `ephemeral=True` for user actions

## COG DETAILS

### Games (`games.py`)
- `/game new` creates category + channels + roles
- `/game member` manages Coder/Artist/Audio/Writer/QA roles
- Acronyms auto-generated, roles get random color

### Templates (`templates.py`)
- `/template sync` applies changes to ALL active games
- `/template groups` + `/template emoji` manage channel prefixes

### Tasks (`tasks.py`)
- Trello-like state machine: Todo -> Progress -> Review -> Done
- Multi-assignee with approval rules (auto/all/majority/any)
- `reminder_loop` checks deadlines (24h) and stagnation (3d)
- Thread moderation via `on_message` listener

### Setup (`setup.py`)
- `/admin setup` - interactive wizard for task config
- `/admin migrate` - syncs existing tasks to multi-assignee
- `/admin channels` + `/admin members` - ID discovery for imports
