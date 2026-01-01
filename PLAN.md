# GameDev Discord Bot - Implementation Plan

## Overview

Discord bot that auto-creates organized channel structures for game projects with custom acronyms and automatic role management.

## Features

- `/newgame` - Create category, channels, and roles from template
- Auto-generate acronym from game name (e.g., "Steal a Brainrot" -> "SaB")
- Auto-assign game roles based on member roles (@Coder -> @SaB-Coder)
- Modifiable channel template with sync to existing games
- Per-game custom channels
- Group-based emoji prefixes

## Channel Structure Example

```
Steal a Brainrot (Category)
├── 💬-sab-announcements
├── 💬-sab-general
├── 💬-sab-brainstorming
├── 💬-sab-tasks
├── 💻-sab-code-frontend
├── 💻-sab-code-backend
├── 💻-sab-code-gamelogic
├── 💻-sab-code-networking
├── 💻-sab-code-bugs
├── 🎨-sab-design-gui
├── 🎨-sab-design-3d
├── 🎨-sab-design-2d
├── 🎨-sab-design-animation
├── 🎨-sab-design-vfx
├── 🎨-sab-design-concept
├── 🔊-sab-audio-music
├── 🔊-sab-audio-sfx
├── ✍️-sab-writing-story
├── ✍️-sab-writing-dialogue
├── ✍️-sab-writing-copy
├── 🧪-sab-qa-playtesting
├── 🧪-sab-qa-feedback
├── 📚-sab-resources-refs
├── 📚-sab-resources-tools
└── 🎙️-sab-voice
```

## Groups & Emojis

| Group     | Emoji |
|-----------|-------|
| general   | 💬    |
| code      | 💻    |
| design    | 🎨    |
| audio     | 🔊    |
| writing   | ✍️    |
| qa        | 🧪    |
| resources | 📚    |
| voice     | 🎙️    |

## Roles

**Member Roles (server-wide, manually assigned):**
- @Coder
- @Artist
- @Audio
- @Writer
- @QA

**Game Roles (auto-created per game):**
- @{acronym}-Coder
- @{acronym}-Artist
- @{acronym}-Audio
- @{acronym}-Writer
- @{acronym}-QA

When a user has @Coder, they automatically get @SaB-Coder, @TGE-Coder, etc. for all games.

## Commands (Admin only)

| Command                | Args                          | Description                    |
|------------------------|-------------------------------|--------------------------------|
| `/newgame`             | `name`, `[acronym]`           | Create game                    |
| `/deletegame`          | `acronym`                     | Delete game + channels/roles   |
| `/game list`           | -                             | List all games                 |
| `/game addchannel`     | `acronym`, `name`, `group`    | Add custom channel             |
| `/game removechannel`  | `acronym`, `name`             | Remove channel                 |
| `/template list`       | -                             | Show template                  |
| `/template add`        | `name`, `group`, `[is_voice]` | Add to template                |
| `/template remove`     | `name`                        | Remove from template           |
| `/template sync`       | -                             | Sync all games                 |
| `/group list`          | -                             | List groups and emojis         |
| `/group emoji`         | `group`, `emoji`              | Change group emoji             |

## Project Structure

```
gamedev-discord-bot/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
├── PLAN.md
├── bot/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── utils.py
│   └── cogs/
│       ├── __init__.py
│       ├── games.py
│       └── templates.py
└── data/
    └── .gitkeep
```

## Database Schema (SQLite)

```sql
CREATE TABLE games (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    acronym TEXT UNIQUE NOT NULL,
    category_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE groups (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    emoji TEXT NOT NULL
);

CREATE TABLE template_channels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    is_voice BOOLEAN DEFAULT 0
);

CREATE TABLE game_channels (
    id INTEGER PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    is_custom BOOLEAN DEFAULT 0,
    is_voice BOOLEAN DEFAULT 0
);

CREATE TABLE game_roles (
    id INTEGER PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL,
    suffix TEXT NOT NULL
);
```

## Tech Stack

- Python 3.11
- discord.py >= 2.3.0
- aiosqlite >= 0.19.0
- python-dotenv >= 1.0.0
- Docker + docker-compose

## Implementation Tasks

| # | Task                              | Status    |
|---|-----------------------------------|-----------|
| 1 | Create folder structure           | Completed |
| 2 | Docker setup                      | Completed |
| 3 | bot/config.py                     | Completed |
| 4 | bot/models.py                     | Completed |
| 5 | bot/utils.py                      | Completed |
| 6 | bot/database.py                   | Completed |
| 7 | bot/main.py                       | Completed |
| 8 | bot/cogs/templates.py             | Completed |
| 9 | bot/cogs/games.py                 | Completed |
| 10| README.md + PLAN.md               | Completed |

## Acronym Generation Logic

1. Split game name into words
2. For each word:
   - First word: always use first letter (uppercase)
   - Skip words (a, an, the, of, etc.): use lowercase letter
   - Other words: use first letter (uppercase)
3. If acronym conflicts with existing, append number (SaB -> SaB2)

Examples:
- "Steal a Brainrot" -> "SaB"
- "The Great Escape" -> "TGE"
- "Rise of Kingdoms" -> "RoK"

## Template Sync Behavior

When `/template sync` runs:
1. For each game:
   - Add channels from template that don't exist (non-custom)
   - Remove non-custom channels that were removed from template
   - Preserve custom channels (is_custom=true)

## Role Sync Behavior

On bot startup and member role changes:
1. Get all member roles user has (Coder, Artist, etc.)
2. For each game:
   - Add game roles that match member roles
   - Remove game roles for member roles user no longer has
