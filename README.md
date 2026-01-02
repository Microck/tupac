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

organize your game dev discord with zero effort.

- **auto channels:** creates 25+ organized channels per game from a template.
- **smart acronyms:** "Neon Drift" -> ND, "The Great Escape" -> TGE.
- **role sync:** members with @Coder auto-get @ND-Coder for every game.
- **emoji groups:** channels prefixed by category (code-nd-code-frontend).
- **channel descriptions:** each channel has a topic explaining its purpose.
- **colored roles:** each game gets a unique color for its roles.
- **live templates:** modify template, sync to all existing games instantly.
- **task management:** trello-style task tracking with threads, dashboards, and automation.

---

### how it works

1. **create:** run `/newgame "Your Game Name"` - acronym auto-generated.
2. **channels:** 25 channels created from template with emoji prefixes and descriptions.
3. **roles:** game-specific roles created with random color and auto-assigned to team members.
4. **customize:** add/remove channels per-game or modify the global template.
5. **tasks:** create tasks with `/task create`, track on dashboard with `/task board`.

---

### usage

#### 1. assign member roles

```
/assign add @user Coder     -> assign Coder role (creates if missing)
/assign add @user Artist    -> assign Artist role
/assign remove @user Coder  -> remove Coder role
/assign list                -> list all members with roles
```

available roles: `Coder`, `Artist`, `Audio`, `Writer`, `QA`

#### 2. create a game

```
/newgame "Neon Drift"
```

creates:

```
Neon Drift
-- nd-announcements    (Project updates, milestones, and important news)
-- nd-general          (Casual chat and general discussion)
-- nd-brainstorming    (Ideas, concepts, and feature proposals)
-- nd-tasks            (Task assignments, todos, and progress tracking)
-- nd-code-frontend    (UI, menus, HUD, and client-side code)
-- nd-code-backend     (Server, database, and backend systems)
-- nd-code-gamelogic   (Game mechanics, physics, and core systems)
-- nd-code-networking  (Multiplayer, netcode, and online features)
-- nd-code-bugs        (Bug reports, debugging, and issue tracking)
-- nd-design-gui       (UI/UX design, menus, and interface mockups)
-- nd-design-3d        (3D models, textures, and environments)
-- nd-design-2d        (Sprites, textures, icons, and 2D artwork)
-- nd-design-animation (Character animations, rigging, and motion)
-- nd-design-vfx       (Particles, shaders, and visual effects)
-- nd-design-concept   (Concept art, sketches, and visual ideas)
-- nd-audio-music      (Soundtrack, themes, and background music)
-- nd-audio-sfx        (Sound effects, foley, and audio design)
-- nd-writing-story    (Narrative, lore, worldbuilding, and plot)
-- nd-writing-dialogue (Character dialogue and voice lines)
-- nd-writing-copy     (Marketing copy, descriptions, and text)
-- nd-qa-playtesting   (Playtest sessions, builds, and test plans)
-- nd-qa-feedback      (Tester feedback, reviews, and suggestions)
-- nd-resources-refs   (Reference images, inspiration, and research)
-- nd-resources-tools  (Tools, tutorials, and helpful resources)
-- nd-voice            (Voice chat for team calls)
```

roles created: `@ND-Coder`, `@ND-Artist`, `@ND-Audio`, `@ND-Writer`, `@ND-QA` (all same color)

#### 3. manage template

```
/template list                          -> view current template
/template add <name> <group> [desc]     -> add channel to template
/template remove <name>                 -> remove from template
/template sync                          -> sync changes to all games
/template export                        -> download template as JSON
/template import <file> [mode]          -> import template from JSON (merge/replace)
```

#### 4. per-game customization

```
/game addchannel ND marketing general   -> add custom channel
/game removechannel ND code-networking  -> remove channel
/game list                              -> list all games
```

#### 5. task management

```
/task create <title> <desc> <channel> <assignee> [priority] [deadline] [game]
/task board <game>          -> show task dashboard (4 status columns)
/task list [user]           -> list active tasks
/task import <file>         -> bulk import from JSON/XML
/task help                  -> show detailed help
```

**task workflow:**
1. admin creates task -> thread spawned in target channel
2. assignee clicks `Start` -> status becomes "In Progress"
3. assignee clicks `Submit for Review` -> leads notified
4. lead clicks `Approve & Close` -> task done, thread archived

**header buttons (in channel, lead/admin only):**
- `View Thread` - jump to discussion thread
- `Reassign` - assign to different user
- `Change Priority` - update priority level
- `Cancel Task` - cancel and archive

**thread buttons (assignee):**
- `Start` / `Pause` - toggle work status
- `Update ETA` - set estimated completion
- `Question` - ping leads for help
- `Submit for Review` - request approval
- `Approve & Close` (lead only) - complete task

**role-based styling:**
- tasks styled by assignee role (Coder=blue/laptop, Artist=purple/palette, etc)
- priority levels: Critical, High, Medium, Low

**automation:**
- reminders for tasks due within 24 hours
- check-ins for stagnant tasks (no update 3+ days)
- thread moderation (only assignee/leads can post)

#### 6. discovery commands (for imports)

```
/debug list-channels [category_id]  -> get channel IDs
/debug list-members [role]          -> get member IDs
```

---

### commands

| command | description |
|---------|-------------|
| `/newgame <name> [acronym]` | create game with channels and roles |
| `/deletegame <acronym>` | delete game and all channels/roles |
| `/game list` | list all games |
| `/game addchannel` | add custom channel to a game |
| `/game removechannel` | remove channel from a game |
| `/assign add` | assign member role to user |
| `/assign remove` | remove member role from user |
| `/assign list` | list all users with member roles |
| `/template list` | show channel template |
| `/template add` | add channel to template |
| `/template remove` | remove from template |
| `/template sync` | sync template to all games |
| `/template export` | download template as JSON |
| `/template import` | import template from JSON |
| `/group list` | list groups and emojis |
| `/group emoji` | change a group's emoji |
| `/task create` | create task with thread |
| `/task board` | show/refresh task dashboard |
| `/task list` | list active tasks |
| `/task import` | bulk import tasks from file |
| `/task help` | show task system help |
| `/debug list-channels` | list channels with IDs |
| `/debug list-members` | list members with IDs |

---

### task import formats

**JSON:**
```json
[
  {
    "title": "Implement Inventory",
    "description": "Create grid-based inventory UI",
    "assignee_id": "123456789012345678",
    "target_channel_id": "987654321098765432",
    "deadline": "2026-05-20",
    "priority": "High"
  }
]
```

**XML:**
```xml
<tasks>
  <task>
    <title>Compose Main Theme</title>
    <description>Orchestral track for main menu</description>
    <assignee_id>123456789012345678</assignee_id>
    <target_channel_id>555444333222111000</target_channel_id>
    <deadline>2026-04-15</deadline>
  </task>
</tasks>
```

use `/debug list-channels` and `/debug list-members` to get IDs.

---

### template import/export format

```json
{
  "groups": [
    {"name": "general", "emoji": "..."},
    {"name": "code", "emoji": "..."}
  ],
  "channels": [
    {
      "name": "announcements",
      "group": "general",
      "is_voice": false,
      "description": "Project updates"
    },
    {
      "name": "voice",
      "group": "voice",
      "is_voice": true,
      "description": null
    }
  ]
}
```

import modes:
- `merge` (default): add new entries, update existing
- `replace`: clear template, import fresh

---

### channel groups

| group | emoji | channels |
|-------|-------|----------|
| general | chat | announcements, general, brainstorming, tasks |
| code | laptop | frontend, backend, gamelogic, networking, bugs |
| design | art | gui, 3d, 2d, animation, vfx, concept |
| audio | speaker | music, sfx |
| writing | pen | story, dialogue, copy |
| qa | test | playtesting, feedback |
| resources | books | refs, tools |
| voice | mic | voice channel |

---

### project structure

```
gamedev-discord-bot/
-- bot/
|   -- main.py          # bot entry, role sync
|   -- config.py        # groups, template, env
|   -- database.py      # sqlite crud
|   -- models.py        # dataclasses
|   -- utils.py         # acronym generation
|   -- cogs/
|       -- games.py     # /newgame, /deletegame, /game, /assign
|       -- templates.py # /template, /group
|       -- tasks.py     # /task, /debug, task management
-- assets/              # static files (gifs, etc)
-- data/                # sqlite database
```

---

### troubleshooting

**commands not showing**
wait a few minutes for discord to sync, or set `GUILD_ID` in .env for instant sync.

**role sync not working**
enable **Server Members Intent** in discord developer portal. bot role must be above game roles in hierarchy.

**permission errors**
move bot role higher in server role list. administrator permission recommended.

**acronym conflicts**
if "ND" exists, new game auto-becomes "ND2". or specify custom: `/newgame "Name" acronym:XYZ`

**task threads not working**
bot needs "Create Public Threads" and "Send Messages in Threads" permissions.

---

### license

mit
