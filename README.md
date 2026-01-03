<p align="center">
  <img src="https://kagi.com/proxy/tupac_shakur_photo_by_steve_eichner_archive_photos_getty_83928439.jpg?c=CO4LUKZbRFWAMar9Ouxd47EwU47WPl3o3nzqn97mCtVTrK_dM-bW2xJeWDX7J9obDzYE8LRsBLJ_zgE6S3ksG8H-ZMnDuNoYFnZm7tmVT6YDpYOhRzduw_5kxe1iqmWP-EVNRXTwmDUFPr7olXA9ZUtgwR4Z9KC_h4qsNddNw8I%3D" alt="logo" width="96"/>
</p>

<h1 align="center">tupac</h1>

<p align="center">
  discord bot for organizing game dev projects with auto-generated channels, roles, acronyms, and task management.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license"/>
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="python"/>
  <img src="https://img.shields.io/badge/discord.py-2.3-5865F2.svg" alt="discord"/>
</p>

---

### quickstart

**1. create discord bot**

1. go to [discord developer portal](https://discord.com/developers/applications)
2. create new application -> bot tab -> create bot -> copy token
3. enable **Server Members Intent** under Privileged Gateway Intents
4. oauth2 -> url generator -> scopes: `bot`, `applications.commands` -> permissions: `Administrator`
5. use generated url to invite bot

**2. run with docker (recommended)**

```bash
git clone https://github.com/microck/tupac.git
cd tupac
cp .env.example .env
# edit .env with your DISCORD_TOKEN and GUILD_ID
docker compose up -d
```

**3. run manually**

```bash
pip install -r requirements.txt
python -m bot.main
```

---

### features

- **auto channels:** creates 25+ organized channels per game from a template
- **smart acronyms:** "Neon Drift" -> ND, "The Great Escape" -> TGE
- **role sync:** members with @Coder auto-get @ND-Coder for every game
- **task management:** trello-style task tracking with threads, dashboards, automation
- **multi-assignee:** assign multiple people to tasks with configurable approval rules
- **setup wizard:** interactive `/admin setup` to configure task system

---

### commands

all commands organized into 4 groups:

| group | command | description |
|-------|---------|-------------|
| **game** | `/game new <name>` | create game with channels and roles |
| | `/game delete <acronym>` | delete game and all channels/roles |
| | `/game list` | list all games |
| | `/game addchannel` | add custom channel to a game |
| | `/game removechannel` | remove channel from a game |
| | `/game member add/remove` | assign/remove member roles |
| | `/game members` | list all users with roles |
| **template** | `/template list` | show channel template |
| | `/template add` | add channel to template |
| | `/template remove` | remove from template |
| | `/template sync` | sync template to all games |
| | `/template export/import` | backup/restore template |
| | `/template groups` | list groups and emojis |
| | `/template emoji` | change a group's emoji |
| **task** | `/task new` | create task with thread |
| | `/task close [id]` | close task (run in thread or specify ID) |
| | `/task list [user]` | list active tasks |
| | `/task board <game>` | show/refresh task dashboard |
| | `/task help` | show detailed help |
| **admin** | `/admin setup` | configure task system (wizard) |
| | `/admin status` | show current config |
| | `/admin migrate` | migrate tasks to multi-assignee |
| | `/admin channels` | list channels with IDs |
| | `/admin members` | list members with IDs |

---

### usage

#### 1. create a game

```
/game new "Neon Drift"
```

creates category with 25 channels and game-specific roles.

#### 2. manage members

```
/game member add @user Coder   -> assign role
/game member remove @user Coder -> remove role
/game members                   -> list all
```

available roles: `Coder`, `Artist`, `Audio`, `Writer`, `QA`

#### 3. create tasks

```
/task new <title> <description> <channel> <assignee> [priority] [deadline]
```

- creates thread in target channel
- supports multiple assignees (comma-separated IDs)
- first assignee becomes primary owner

#### 4. task workflow

1. admin creates task -> thread spawned
2. assignee clicks `Start` -> "In Progress"
3. click `Submit for Review` -> leads notified
4. click `Approve & Close` or `/task close` -> done, thread archived

**buttons:**
- `Manage Team` - add/remove members, set primary
- `Start/Pause` - toggle work status
- `Update ETA` - set completion estimate
- `Question` - ping leads for help

#### 5. server setup

```
/admin setup    -> interactive wizard
/admin status   -> view current config
/admin migrate  -> sync existing tasks
```

---

### task import format

```json
[
  {
    "title": "Implement Inventory",
    "description": "Create grid-based inventory UI",
    "assignee_id": "123456789012345678",
    "target_channel_id": "987654321098765432",
    "deadline": "2026-05-20",
    "priority": "High",
    "additional_assignees": "111222333,444555666"
  }
]
```

use `/admin channels` and `/admin members` to get IDs.

---

### project structure

```
gamedev-discord-bot/
├── bot/
│   ├── main.py          # bot entry, role sync
│   ├── config.py        # env vars
│   ├── database.py      # sqlite crud
│   ├── models.py        # dataclasses
│   ├── utils.py         # acronym generation
│   └── cogs/
│       ├── games.py     # /game commands
│       ├── templates.py # /template commands
│       ├── tasks.py     # /task commands
│       └── setup.py     # /admin commands
├── assets/              # static files
└── data/                # sqlite database
```

---

### troubleshooting

**commands not showing** - wait for discord sync, or set `GUILD_ID` in .env

**role sync not working** - enable Server Members Intent in developer portal

**permission errors** - move bot role higher in server role list

**task threads not working** - bot needs "Create Public Threads" permission

---

### license

mit
