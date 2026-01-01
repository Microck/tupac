import os
from dotenv import load_dotenv

load_dotenv()

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

# Default template channels (name, group, is_voice)
DEFAULT_TEMPLATE = [
    # General
    ("announcements", "general", False),
    ("general", "general", False),
    ("brainstorming", "general", False),
    ("tasks", "general", False),
    # Code
    ("code-frontend", "code", False),
    ("code-backend", "code", False),
    ("code-gamelogic", "code", False),
    ("code-networking", "code", False),
    ("code-bugs", "code", False),
    # Design
    ("design-gui", "design", False),
    ("design-3d", "design", False),
    ("design-2d", "design", False),
    ("design-animation", "design", False),
    ("design-vfx", "design", False),
    ("design-concept", "design", False),
    # Audio
    ("audio-music", "audio", False),
    ("audio-sfx", "audio", False),
    # Writing
    ("writing-story", "writing", False),
    ("writing-dialogue", "writing", False),
    ("writing-copy", "writing", False),
    # QA
    ("qa-playtesting", "qa", False),
    ("qa-feedback", "qa", False),
    # Resources
    ("resources-refs", "resources", False),
    ("resources-tools", "resources", False),
    # Voice
    ("voice", "voice", True),
]
