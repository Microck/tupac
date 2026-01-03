# BOT CORE KNOWLEDGE BASE

**Context:** Core infrastructure (Database, Models, Configuration, Entry Point)

## OVERVIEW
Handles bot lifecycle, data persistence (SQLite), and domain models. No business logic here (see `cogs/`).

## STRUCTURE
```
bot/
├── config.py       # Constants, Env vars (DISCORD_TOKEN, GUILD_ID)
├── database.py     # Raw SQL queries, Schema init, aiosqlite wrapper
├── main.py         # GameDevBot class, Role Sync on startup
├── models.py       # Dataclasses (Game, Task, TaskAssignee, ServerConfig)
└── utils.py        # Acronym generator, string formatters
```

## KEY TABLES
| Table | Purpose |
|-------|---------|
| `task_assignees` | Multi-assignee (task_id, user_id, is_primary, has_approved) |
| `server_config` | Per-server setup (guild_id, config_json, setup_completed) |

## CONVENTIONS
- Raw SQL strings. No ORM.
- Context manager: `async with aiosqlite.connect(DATABASE_PATH) as db`
- Role sync on `on_ready` and `on_member_update`
