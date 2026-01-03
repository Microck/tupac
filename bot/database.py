import aiosqlite
from typing import List, Optional, Set

from .config import DATABASE_PATH, DEFAULT_GROUPS, DEFAULT_TEMPLATE
from .models import Game, Group, TemplateChannel, GameChannel, GameRole, Task, TaskHistory, TaskBoard, TaskAssignee, ServerConfig


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
                description TEXT,
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

            -- Task management tables
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_acronym TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                assignee_id INTEGER NOT NULL,
                target_channel_id INTEGER NOT NULL,
                thread_id INTEGER,
                control_message_id INTEGER,
                header_message_id INTEGER,
                status TEXT DEFAULT 'todo',
                deadline DATETIME,
                eta TEXT,
                priority TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS task_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS task_boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_acronym TEXT NOT NULL UNIQUE,
                channel_id INTEGER NOT NULL,
                message_ids TEXT NOT NULL
            );

            -- Multi-assignee support
            CREATE TABLE IF NOT EXISTS task_assignees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_primary BOOLEAN DEFAULT 0,
                has_approved BOOLEAN DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                UNIQUE(task_id, user_id)
            );

            -- Server configuration
            CREATE TABLE IF NOT EXISTS server_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL UNIQUE,
                config_json TEXT NOT NULL DEFAULT '{}',
                setup_completed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Migration: Add header_message_id column if it doesn't exist
        cursor = await db.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in await cursor.fetchall()]
        if 'header_message_id' not in columns:
            await db.execute("ALTER TABLE tasks ADD COLUMN header_message_id INTEGER")
        
        # Migration: Create task_assignees index for performance
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_assignees_task_id 
            ON task_assignees(task_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_assignees_user_id 
            ON task_assignees(user_id)
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
            for name, group_name, is_voice, description in DEFAULT_TEMPLATE:
                await db.execute(
                    "INSERT INTO template_channels (name, group_name, is_voice, description) VALUES (?, ?, ?, ?)",
                    (name, group_name, is_voice, description)
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


async def upsert_group(name: str, emoji: str) -> bool:
    """Insert or update a group."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO groups (name, emoji) VALUES (?, ?)
               ON CONFLICT(name) DO UPDATE SET emoji = excluded.emoji""",
            (name, emoji)
        )
        await db.commit()
        return True


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
                is_voice=bool(r["is_voice"]),
                description=r["description"]
            )
            for r in rows
        ]


async def add_template_channel(name: str, group_name: str, is_voice: bool = False, description: str = None) -> bool:
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO template_channels (name, group_name, is_voice, description) VALUES (?, ?, ?, ?)",
                (name, group_name, is_voice, description)
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


async def clear_template_channels() -> int:
    """Delete all template channels. Returns count deleted."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM template_channels")
        await db.commit()
        return cursor.rowcount


async def upsert_template_channel(name: str, group_name: str, is_voice: bool = False, description: str = None) -> bool:
    """Insert or update a template channel."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO template_channels (name, group_name, is_voice, description) 
               VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET 
               group_name = excluded.group_name,
               is_voice = excluded.is_voice,
               description = excluded.description""",
            (name, group_name, is_voice, description)
        )
        await db.commit()
        return True


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
                is_voice=bool(row["is_voice"]),
                description=row["description"]
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


# ============== TASKS ==============

def _row_to_task(r) -> Task:
    """Helper to convert a database row to a Task object."""
    return Task(
        id=r["id"],
        game_acronym=r["game_acronym"],
        title=r["title"],
        description=r["description"],
        assignee_id=r["assignee_id"],
        target_channel_id=r["target_channel_id"],
        thread_id=r["thread_id"],
        control_message_id=r["control_message_id"],
        header_message_id=r["header_message_id"] if "header_message_id" in r.keys() else None,
        status=r["status"],
        deadline=r["deadline"],
        eta=r["eta"],
        priority=r["priority"],
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )


async def create_task(
    game_acronym: str,
    title: str,
    description: str,
    assignee_id: int,
    target_channel_id: int,
    deadline: str = None,
    priority: str = None
) -> Task:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tasks 
               (game_acronym, title, description, assignee_id, target_channel_id, deadline, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (game_acronym, title, description, assignee_id, target_channel_id, deadline, priority)
        )
        await db.commit()
        return Task(
            id=cursor.lastrowid,
            game_acronym=game_acronym,
            title=title,
            description=description,
            assignee_id=assignee_id,
            target_channel_id=target_channel_id,
            thread_id=None,
            control_message_id=None,
            header_message_id=None,
            status='todo',
            deadline=deadline,
            eta=None,
            priority=priority
        )


async def get_task(task_id: int) -> Optional[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row:
            return _row_to_task(row)
        return None


async def get_task_by_thread_id(thread_id: int) -> Optional[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE thread_id = ?", (thread_id,))
        row = await cursor.fetchone()
        if row:
            return _row_to_task(row)
        return None


async def get_tasks_by_game(game_acronym: str) -> List[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE game_acronym = ? ORDER BY created_at DESC",
            (game_acronym,)
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_tasks_by_assignee(assignee_id: int) -> List[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE assignee_id = ? AND status NOT IN ('done', 'cancelled') ORDER BY deadline ASC",
            (assignee_id,)
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_tasks_by_status(status: str, game_acronym: str = None) -> List[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if game_acronym:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ? AND game_acronym = ? ORDER BY created_at DESC",
                (status, game_acronym)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_overdue_tasks() -> List[Task]:
    """Get tasks past deadline that are not done."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tasks 
               WHERE status NOT IN ('done', 'cancelled')
               AND deadline IS NOT NULL 
               AND deadline < datetime('now')
               ORDER BY deadline ASC"""
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_tasks_due_soon(hours: int = 24) -> List[Task]:
    """Get tasks due within the next N hours."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""SELECT * FROM tasks 
               WHERE status NOT IN ('done', 'cancelled')
               AND deadline IS NOT NULL 
               AND deadline > datetime('now')
               AND deadline <= datetime('now', '+{hours} hours')
               ORDER BY deadline ASC"""
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_stagnant_tasks(days: int = 3) -> List[Task]:
    """Get in-progress tasks not updated in N days."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""SELECT * FROM tasks 
               WHERE status = 'progress' 
               AND updated_at < datetime('now', '-{days} days')
               ORDER BY updated_at ASC"""
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def update_task_thread(task_id: int, thread_id: int, control_message_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """UPDATE tasks SET thread_id = ?, control_message_id = ?, updated_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (thread_id, control_message_id, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_task_status(task_id: int, status: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_task_eta(task_id: int, eta: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET eta = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (eta, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_task_assignee(task_id: int, assignee_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET assignee_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (assignee_id, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_task_priority(task_id: int, priority: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET priority = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (priority, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_task_header_message(task_id: int, header_message_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET header_message_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (header_message_id, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_task(task_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return cursor.rowcount > 0


# ============== TASK HISTORY ==============

async def add_task_history(task_id: int, user_id: int, action: str, old_value: str = None, new_value: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO task_history (task_id, user_id, action, old_value, new_value)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, user_id, action, old_value, new_value)
        )
        await db.commit()


async def get_task_history(task_id: int) -> List[TaskHistory]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_history WHERE task_id = ? ORDER BY timestamp DESC",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [
            TaskHistory(
                id=r["id"],
                task_id=r["task_id"],
                user_id=r["user_id"],
                action=r["action"],
                old_value=r["old_value"],
                new_value=r["new_value"],
                timestamp=r["timestamp"]
            )
            for r in rows
        ]


# ============== TASK BOARDS ==============

async def get_task_board(game_acronym: str) -> Optional[TaskBoard]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_boards WHERE game_acronym = ?",
            (game_acronym,)
        )
        row = await cursor.fetchone()
        if row:
            return TaskBoard(
                id=row["id"],
                game_acronym=row["game_acronym"],
                channel_id=row["channel_id"],
                message_ids=row["message_ids"]
            )
        return None


async def upsert_task_board(game_acronym: str, channel_id: int, message_ids: str) -> TaskBoard:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO task_boards (game_acronym, channel_id, message_ids)
               VALUES (?, ?, ?)
               ON CONFLICT(game_acronym) DO UPDATE SET
               channel_id = excluded.channel_id,
               message_ids = excluded.message_ids""",
            (game_acronym, channel_id, message_ids)
        )
        await db.commit()
        return TaskBoard(
            id=None,
            game_acronym=game_acronym,
            channel_id=channel_id,
            message_ids=message_ids
        )


# ============== TASK ASSIGNEES ==============

async def add_task_assignee(task_id: int, user_id: int, is_primary: bool = False) -> TaskAssignee:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO task_assignees (task_id, user_id, is_primary)
               VALUES (?, ?, ?)
               ON CONFLICT(task_id, user_id) DO UPDATE SET is_primary = excluded.is_primary""",
            (task_id, user_id, is_primary)
        )
        await db.commit()
        return TaskAssignee(
            id=cursor.lastrowid,
            task_id=task_id,
            user_id=user_id,
            is_primary=is_primary,
            has_approved=False
        )


async def remove_task_assignee(task_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM task_assignees WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_task_assignees(task_id: int) -> List[TaskAssignee]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_assignees WHERE task_id = ? ORDER BY is_primary DESC, added_at ASC",
            (task_id,)
        )
        rows = await cursor.fetchall()
        return [
            TaskAssignee(
                id=r["id"],
                task_id=r["task_id"],
                user_id=r["user_id"],
                is_primary=bool(r["is_primary"]),
                has_approved=bool(r["has_approved"]),
                added_at=r["added_at"]
            )
            for r in rows
        ]


async def get_task_primary_assignee(task_id: int) -> Optional[TaskAssignee]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM task_assignees WHERE task_id = ? AND is_primary = 1",
            (task_id,)
        )
        row = await cursor.fetchone()
        if row:
            return TaskAssignee(
                id=row["id"],
                task_id=row["task_id"],
                user_id=row["user_id"],
                is_primary=True,
                has_approved=bool(row["has_approved"]),
                added_at=row["added_at"]
            )
        return None


async def set_task_primary_assignee(task_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE task_assignees SET is_primary = 0 WHERE task_id = ?",
            (task_id,)
        )
        cursor = await db.execute(
            "UPDATE task_assignees SET is_primary = 1 WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_task_primary_assignee(task_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE task_assignees SET is_primary = 0 WHERE task_id = ?",
            (task_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def set_task_assignee_approval(task_id: int, user_id: int, approved: bool) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE task_assignees SET has_approved = ? WHERE task_id = ? AND user_id = ?",
            (approved, task_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_task_approval_status(task_id: int) -> dict:
    assignees = await get_task_assignees(task_id)
    total = len(assignees)
    approved = sum(1 for a in assignees if a.has_approved)
    primary = next((a for a in assignees if a.is_primary), None)
    return {
        'total': total,
        'approved': approved,
        'primary': primary,
        'assignees': assignees
    }


async def reset_task_approvals(task_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "UPDATE task_assignees SET has_approved = 0 WHERE task_id = ?",
            (task_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def is_user_task_assignee(task_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM task_assignees WHERE task_id = ? AND user_id = ?",
            (task_id, user_id)
        )
        return await cursor.fetchone() is not None


async def get_tasks_by_assignee_multi(user_id: int) -> List[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT t.* FROM tasks t
               JOIN task_assignees ta ON t.id = ta.task_id
               WHERE ta.user_id = ? AND t.status NOT IN ('done', 'cancelled')
               ORDER BY t.deadline ASC""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def get_all_tasks() -> List[Task]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]


async def migrate_tasks_to_multi_assignee() -> dict:
    """Migrate existing tasks to multi-assignee system. Returns stats."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute("SELECT id, assignee_id FROM tasks WHERE assignee_id IS NOT NULL")
        tasks = await cursor.fetchall()
        
        migrated = 0
        skipped = 0
        
        for task in tasks:
            existing = await db.execute(
                "SELECT 1 FROM task_assignees WHERE task_id = ?",
                (task["id"],)
            )
            if await existing.fetchone():
                skipped += 1
                continue
            
            await db.execute(
                """INSERT INTO task_assignees (task_id, user_id, is_primary, has_approved)
                   VALUES (?, ?, 1, 0)""",
                (task["id"], task["assignee_id"])
            )
            migrated += 1
        
        await db.commit()
        return {"migrated": migrated, "skipped": skipped, "total": len(tasks)}


# ============== SERVER CONFIG ==============

async def get_server_config(guild_id: int) -> Optional[ServerConfig]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM server_config WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row:
            return ServerConfig(
                id=row["id"],
                guild_id=row["guild_id"],
                config_json=row["config_json"],
                setup_completed=bool(row["setup_completed"])
            )
        return None


async def upsert_server_config(guild_id: int, config_json: str, setup_completed: bool = False) -> ServerConfig:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO server_config (guild_id, config_json, setup_completed)
               VALUES (?, ?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET
               config_json = excluded.config_json,
               setup_completed = excluded.setup_completed,
               updated_at = CURRENT_TIMESTAMP""",
            (guild_id, config_json, setup_completed)
        )
        await db.commit()
        return ServerConfig(
            id=None,
            guild_id=guild_id,
            config_json=config_json,
            setup_completed=setup_completed
        )


async def is_setup_completed(guild_id: int) -> bool:
    config = await get_server_config(guild_id)
    return config.setup_completed if config else False

