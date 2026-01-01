import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

DATABASE_PATH = "data/bot.db"

# Member roles (server-wide, manually assigned)
MEMBER_ROLES = ["Coder", "Artist", "Audio", "Writer", "QA"]

# Default groups with emojis
DEFAULT_GROUPS = {
    "general": "\U0001f4ac",    # 💬
    "code": "\U0001f4bb",       # 💻
    "design": "\U0001f3a8",     # 🎨
    "audio": "\U0001f50a",      # 🔊
    "writing": "\u270d\ufe0f",  # ✍️
    "qa": "\U0001f9ea",         # 🧪
    "resources": "\U0001f4da",  # 📚
    "voice": "\U0001f399\ufe0f" # 🎙️
}

# Default template channels (name, group, is_voice, description)
DEFAULT_TEMPLATE = [
    # General
    ("announcements", "general", False, "Project updates, milestones, and important news"),
    ("general", "general", False, "Casual chat and general discussion"),
    ("brainstorming", "general", False, "Ideas, concepts, and feature proposals"),
    ("tasks", "general", False, "Task assignments, todos, and progress tracking"),
    # Code
    ("code-frontend", "code", False, "UI, menus, HUD, and client-side code"),
    ("code-backend", "code", False, "Server, database, and backend systems"),
    ("code-gamelogic", "code", False, "Game mechanics, physics, and core systems"),
    ("code-networking", "code", False, "Multiplayer, netcode, and online features"),
    ("code-bugs", "code", False, "Bug reports, debugging, and issue tracking"),
    # Design
    ("design-gui", "design", False, "UI/UX design, menus, and interface mockups"),
    ("design-3d", "design", False, "3D models, textures, and environments"),
    ("design-2d", "design", False, "Sprites, textures, icons, and 2D artwork"),
    ("design-animation", "design", False, "Character animations, rigging, and motion"),
    ("design-vfx", "design", False, "Particles, shaders, and visual effects"),
    ("design-concept", "design", False, "Concept art, sketches, and visual ideas"),
    # Audio
    ("audio-music", "audio", False, "Soundtrack, themes, and background music"),
    ("audio-sfx", "audio", False, "Sound effects, foley, and audio design"),
    # Writing
    ("writing-story", "writing", False, "Narrative, lore, worldbuilding, and plot"),
    ("writing-dialogue", "writing", False, "Character dialogue and voice lines"),
    ("writing-copy", "writing", False, "Marketing copy, descriptions, and text"),
    # QA
    ("qa-playtesting", "qa", False, "Playtest sessions, builds, and test plans"),
    ("qa-feedback", "qa", False, "Tester feedback, reviews, and suggestions"),
    # Resources
    ("resources-refs", "resources", False, "Reference images, inspiration, and research"),
    ("resources-tools", "resources", False, "Tools, tutorials, and helpful resources"),
    # Voice
    ("voice", "voice", True, "Voice chat for team calls"),
]
