import aiosqlite
from typing import List, Optional, Set

from .config import DATABASE_PATH, DEFAULT_GROUPS, DEFAULT_TEMPLATE
from .models import Game, Group, TemplateChannel, GameChannel, GameRole


async def init_db():
    """Initialize database schema and seed default data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create tables
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                acronym TEXT UNIQUE NOT NULL,
                category_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                emoji TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS template_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                is_voice BOOLEAN DEFAULT 0,
                UNIQUE(name)
            );

            CREATE TABLE IF NOT EXISTS game_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                is_custom BOOLEAN DEFAULT 0,
                is_voice BOOLEAN DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS game_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                suffix TEXT NOT NULL,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
            );
        """)
        
        # Seed default groups if empty
        cursor = await db.execute("SELECT COUNT(*) FROM groups")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for name, emoji in DEFAULT_GROUPS.items():
                await db.execute(
                    "INSERT INTO groups (name, emoji) VALUES (?, ?)",
                    (name, emoji)
                )
        
        # Seed default template channels if empty
        cursor = await db.execute("SELECT COUNT(*) FROM template_channels")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for name, group_name, is_voice in DEFAULT_TEMPLATE:
                await db.execute(
                    "INSERT INTO template_channels (name, group_name, is_voice) VALUES (?, ?, ?)",
                    (name, group_name, is_voice)
                )
        
        await db.commit()


# ============== GROUPS ==============

async def get_all_groups() -> List[Group]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM groups")
        rows = await cursor.fetchall()
        return [Group(id=r["id"], name=r["name"], emoji=r["emoji"]) for r in rows]


async def get_group(name: str) -> Optional[Group]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM groups WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if row:
            return Group(id=row["id"], name=row["name"], emoji=row["emoji"])
        return None


async def update_group_emoji(name: str, emoji: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE groups SET emoji = ? WHERE name = ?",
            (emoji, name)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_groups_dict() -> dict:
    """Return dict of group_name -> emoji."""
    groups = await get_all_groups()
    return {g.name: g.emoji for g in groups}


# ============== TEMPLATE CHANNELS ==============

async def get_all_template_channels() -> List[TemplateChannel]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM template_channels ORDER BY id")
        rows = await cursor.fetchall()
        return [
            TemplateChannel(
                id=r["id"],
                name=r["name"],
                group_name=r["group_name"],
                is_voice=bool(r["is_voice"])
            )
            for r in rows
        ]


async def add_template_channel(name: str, group_name: str, is_voice: bool = False) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO template_channels (name, group_name, is_voice) VALUES (?, ?, ?)",
                (name, group_name, is_voice)
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False


async def remove_template_channel(name: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM template_channels WHERE name = ?",
            (name,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_template_channel(name: str) -> Optional[TemplateChannel]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM template_channels WHERE name = ?",
            (name,)
        )
        row = await cursor.fetchone()
        if row:
            return TemplateChannel(
                id=row["id"],
                name=row["name"],
                group_name=row["group_name"],
                is_voice=bool(row["is_voice"])
            )
        return None


# ============== GAMES ==============

async def get_all_games() -> List[Game]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM games ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [
            Game(
                id=r["id"],
                name=r["name"],
                acronym=r["acronym"],
                category_id=r["category_id"],
                created_at=r["created_at"]
            )
            for r in rows
        ]


async def get_game_by_acronym(acronym: str) -> Optional[Game]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM games WHERE LOWER(acronym) = LOWER(?)",
            (acronym,)
        )
        row = await cursor.fetchone()
        if row:
            return Game(
                id=row["id"],
                name=row["name"],
                acronym=row["acronym"],
                category_id=row["category_id"],
                created_at=row["created_at"]
            )
        return None


async def get_all_acronyms() -> Set[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT acronym FROM games")
        rows = await cursor.fetchall()
        return {r[0] for r in rows}


async def create_game(name: str, acronym: str, category_id: int) -> Game:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO games (name, acronym, category_id) VALUES (?, ?, ?)",
            (name, acronym, category_id)
        )
        await db.commit()
        return Game(
            id=cursor.lastrowid,
            name=name,
            acronym=acronym,
            category_id=category_id
        )


async def delete_game(game_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        await db.commit()
        return cursor.rowcount > 0


# ============== GAME CHANNELS ==============

async def get_game_channels(game_id: int) -> List[GameChannel]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM game_channels WHERE game_id = ?",
            (game_id,)
        )
        rows = await cursor.fetchall()
        return [
            GameChannel(
                id=r["id"],
                game_id=r["game_id"],
                channel_id=r["channel_id"],
                name=r["name"],
                group_name=r["group_name"],
                is_custom=bool(r["is_custom"]),
                is_voice=bool(r["is_voice"])
            )
            for r in rows
        ]


async def add_game_channel(
    game_id: int,
    channel_id: int,
    name: str,
    group_name: str,
    is_custom: bool = False,
    is_voice: bool = False
) -> GameChannel:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO game_channels 
               (game_id, channel_id, name, group_name, is_custom, is_voice) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (game_id, channel_id, name, group_name, is_custom, is_voice)
        )
        await db.commit()
        return GameChannel(
            id=cursor.lastrowid,
            game_id=game_id,
            channel_id=channel_id,
            name=name,
            group_name=group_name,
            is_custom=is_custom,
            is_voice=is_voice
        )


async def remove_game_channel(game_id: int, name: str) -> Optional[int]:
    """Remove game channel by name, return channel_id if found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT channel_id FROM game_channels WHERE game_id = ? AND name = ?",
            (game_id, name)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        
        channel_id = row[0]
        await db.execute(
            "DELETE FROM game_channels WHERE game_id = ? AND name = ?",
            (game_id, name)
        )
        await db.commit()
        return channel_id


async def get_game_channel_by_name(game_id: int, name: str) -> Optional[GameChannel]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM game_channels WHERE game_id = ? AND name = ?",
            (game_id, name)
        )
        row = await cursor.fetchone()
        if row:
            return GameChannel(
                id=row["id"],
                game_id=row["game_id"],
                channel_id=row["channel_id"],
                name=row["name"],
                group_name=row["group_name"],
                is_custom=bool(row["is_custom"]),
                is_voice=bool(row["is_voice"])
            )
        return None


async def get_non_custom_game_channels(game_id: int) -> List[GameChannel]:
    """Get only template-based channels for a game."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM game_channels WHERE game_id = ? AND is_custom = 0",
            (game_id,)
        )
        rows = await cursor.fetchall()
        return [
            GameChannel(
                id=r["id"],
                game_id=r["game_id"],
                channel_id=r["channel_id"],
                name=r["name"],
                group_name=r["group_name"],
                is_custom=bool(r["is_custom"]),
                is_voice=bool(r["is_voice"])
            )
            for r in rows
        ]


# ============== GAME ROLES ==============

async def get_game_roles(game_id: int) -> List[GameRole]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM game_roles WHERE game_id = ?",
            (game_id,)
        )
        rows = await cursor.fetchall()
        return [
            GameRole(
                id=r["id"],
                game_id=r["game_id"],
                role_id=r["role_id"],
                suffix=r["suffix"]
            )
            for r in rows
        ]


async def add_game_role(game_id: int, role_id: int, suffix: str) -> GameRole:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO game_roles (game_id, role_id, suffix) VALUES (?, ?, ?)",
            (game_id, role_id, suffix)
        )
        await db.commit()
        return GameRole(
            id=cursor.lastrowid,
            game_id=game_id,
            role_id=role_id,
            suffix=suffix
        )


async def get_all_game_roles() -> List[GameRole]:
    """Get all game roles across all games."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM game_roles")
        rows = await cursor.fetchall()
        return [
            GameRole(
                id=r["id"],
                game_id=r["game_id"],
                role_id=r["role_id"],
                suffix=r["suffix"]
            )
            for r in rows
        ]
