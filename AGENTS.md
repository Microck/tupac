# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-04
**Context:** Discord bot for game dev project management

## OVERVIEW
Python Discord bot (`discord.py` + `aiosqlite`). Manages game projects via auto-generated channels, role sync, and Trello-like task boards with multi-assignee support.

## STRUCTURE
```
.
├── bot/
│   ├── cogs/           # Feature modules (4 cogs)
│   ├── config.py       # Env vars & constants
│   ├── database.py     # SQLite CRUD & Schema
│   ├── main.py         # Entry point & Role Sync
│   ├── models.py       # Data Classes
│   └── utils.py        # Helpers
├── data/               # SQLite storage
└── assets/             # Static media
```

## COMMAND GROUPS (4 total)
| Group | Cog | Commands |
|-------|-----|----------|
| `/game` | games.py | new, delete, list, addchannel, removechannel, member, members |
| `/template` | templates.py | list, add, remove, sync, export, import, groups, emoji |
| `/task` | tasks.py | new, close, list, board, help |
| `/admin` | setup.py | setup, status, migrate, channels, members |

## KEY TABLES
| Table | Purpose |
|-------|---------|
| `games` | Game records (name, acronym, category_id) |
| `tasks` | Task records (title, status, deadlines) |
| `task_assignees` | Multi-assignee (user_id, is_primary, has_approved) |
| `server_config` | Per-server setup (approval rules, lead roles) |

## CONVENTIONS
- Raw SQL in `database.py`, no ORM
- UI Views (Buttons/Modals) live inside Cog files
- Acronyms auto-generated: "Neon Drift" -> "ND"
- Channels/Roles prefixed with acronym: `nd-general`, `ND-Coder`
