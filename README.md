<p align="center">
  <img src="https://img.icons8.com/fluency/96/controller.png" alt="logo" width="96"/>
</p>

<h1 align="center">tupac</h1>

<p align="center">
  discord bot for organizing game dev projects with auto-generated channels, roles, and acronyms.
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
2. create new application → bot tab → create bot → copy token
3. enable **Server Members Intent** under Privileged Gateway Intents
4. oauth2 → url generator → scopes: `bot`, `applications.commands` → permissions: `Administrator`
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
- **smart acronyms:** "Steal a Brainrot" → SaB, "The Great Escape" → TGE.
- **role sync:** members with @Coder auto-get @SaB-Coder for every game.
- **emoji groups:** channels prefixed by category (💻-sab-code-frontend).
- **channel descriptions:** each channel has a topic explaining its purpose.
- **colored roles:** each game gets a unique color for its roles.
- **live templates:** modify template, sync to all existing games instantly.

---

### how it works

1. **create:** run `/newgame "Your Game Name"` - acronym auto-generated.
2. **channels:** 25 channels created from template with emoji prefixes and descriptions.
3. **roles:** game-specific roles created with random color and auto-assigned to team members.
4. **customize:** add/remove channels per-game or modify the global template.

---

### usage

#### 1. assign member roles

```
/assign add @user Coder     → assign Coder role (creates if missing)
/assign add @user Artist    → assign Artist role
/assign remove @user Coder  → remove Coder role
/assign list                → list all members with roles
```

available roles: `Coder`, `Artist`, `Audio`, `Writer`, `QA`

#### 2. create a game

```
/newgame "Steal a Brainrot"
```

creates:

```
📁 Steal a Brainrot
├── 💬-sab-announcements    (Project updates, milestones, and important news)
├── 💬-sab-general          (Casual chat and general discussion)
├── 💬-sab-brainstorming    (Ideas, concepts, and feature proposals)
├── 💬-sab-tasks            (Task assignments, todos, and progress tracking)
├── 💻-sab-code-frontend    (UI, menus, HUD, and client-side code)
├── 💻-sab-code-backend     (Server, database, and backend systems)
├── 💻-sab-code-gamelogic   (Game mechanics, physics, and core systems)
├── 💻-sab-code-networking  (Multiplayer, netcode, and online features)
├── 💻-sab-code-bugs        (Bug reports, debugging, and issue tracking)
├── 🎨-sab-design-gui       (UI/UX design, menus, and interface mockups)
├── 🎨-sab-design-3d        (3D models, textures, and environments)
├── 🎨-sab-design-2d        (Sprites, textures, icons, and 2D artwork)
├── 🎨-sab-design-animation (Character animations, rigging, and motion)
├── 🎨-sab-design-vfx       (Particles, shaders, and visual effects)
├── 🎨-sab-design-concept   (Concept art, sketches, and visual ideas)
├── 🔊-sab-audio-music      (Soundtrack, themes, and background music)
├── 🔊-sab-audio-sfx        (Sound effects, foley, and audio design)
├── ✍️-sab-writing-story    (Narrative, lore, worldbuilding, and plot)
├── ✍️-sab-writing-dialogue (Character dialogue and voice lines)
├── ✍️-sab-writing-copy     (Marketing copy, descriptions, and text)
├── 🧪-sab-qa-playtesting   (Playtest sessions, builds, and test plans)
├── 🧪-sab-qa-feedback      (Tester feedback, reviews, and suggestions)
├── 📚-sab-resources-refs   (Reference images, inspiration, and research)
├── 📚-sab-resources-tools  (Tools, tutorials, and helpful resources)
└── 🎙️-sab-voice            (Voice chat for team calls)
```

roles created: `@SaB-Coder`, `@SaB-Artist`, `@SaB-Audio`, `@SaB-Writer`, `@SaB-QA` (all same color)

#### 3. manage template

```
/template list                          → view current template
/template add <name> <group> [desc]     → add channel to template
/template remove <name>                 → remove from template
/template sync                          → sync changes to all games
```

#### 4. per-game customization

```
/game addchannel SaB marketing general  → add custom channel
/game removechannel SaB code-networking → remove channel
/game list                              → list all games
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
| `/group list` | list groups and emojis |
| `/group emoji` | change a group's emoji |

---

### channel groups

| group | emoji | channels |
|-------|-------|----------|
| general | 💬 | announcements, general, brainstorming, tasks |
| code | 💻 | frontend, backend, gamelogic, networking, bugs |
| design | 🎨 | gui, 3d, 2d, animation, vfx, concept |
| audio | 🔊 | music, sfx |
| writing | ✍️ | story, dialogue, copy |
| qa | 🧪 | playtesting, feedback |
| resources | 📚 | refs, tools |
| voice | 🎙️ | voice channel |

---

### project structure

```
gamedev-discord-bot/
├── bot/
│   ├── main.py          # bot entry, role sync
│   ├── config.py        # groups, template, env
│   ├── database.py      # sqlite crud
│   ├── models.py        # dataclasses
│   ├── utils.py         # acronym generation
│   └── cogs/
│       ├── games.py     # /newgame, /deletegame, /game, /assign
│       └── templates.py # /template, /group
├── data/                # sqlite database
└── dist/                # (if compiled)
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
if "SaB" exists, new game auto-becomes "SaB2". or specify custom: `/newgame "Name" acronym:XYZ`

---

### license

mit
