# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.3.0] - 2026-01-02

### Added
- **Enhanced Task Embeds**
  - Role-based task styling (Coder=blue, Artist=purple, Audio=gold, Writer=teal, QA=red)
  - Role-specific emoji and labels (e.g., "Code Task:", "Art Task:")
  - Priority parameter on `/task create` with dropdown choices
  - Cancelled task status support
- **Header Message Buttons** (for leads/admins)
  - View Thread - quick link to discussion
  - Reassign - reassign task to different user
  - Change Priority - dropdown to update priority
  - Cancel Task - cancel and archive thread
- **Database**
  - `header_message_id` field for tracking channel embed
  - `update_task_assignee`, `update_task_priority` functions
  - Auto-migration for existing databases

### Changed
- Header embed (channel) now compact: title, assignee, status, priority, due date
- Control embed (thread) now detailed: full description, all fields, action buttons
- Removed duplicate info between header and control embeds
- Task queries refactored to use helper function

## [1.2.0] - 2026-01-02

### Added
- **Template Import/Export**
  - `/template export` - Download template as JSON file
  - `/template import` - Import template from JSON file
  - Merge mode: add/update entries without removing existing
  - Replace mode: clear template and import fresh

### Changed
- Updated `.gitignore` with venv, IDE, and common patterns

### Removed
- `FEATURE_TASK_MANAGEMENT.md` and `PLAN.md` spec files

## [1.1.0] - 2026-01-02

### Added
- **Task Management System** - Trello-style task tracking within Discord
  - `/task create` - Create tasks with dedicated threads
  - `/task board` - Dashboard with 4 status columns (To Do, In Progress, In Review, Done)
  - `/task list` - View active tasks per user
  - `/task import` - Bulk import from JSON/XML files
  - `/task help` - Detailed usage guide
- **Interactive Task Controls** - Buttons in task threads
  - Start/Pause work
  - Update ETA via modal
  - Ask question (pings leads)
  - Submit for review
  - Approve & Close (lead only)
- **Discovery Commands**
  - `/debug list-channels` - Get channel IDs for imports
  - `/debug list-members` - Get member IDs for imports
- **Automation**
  - Hourly reminder loop for tasks due within 24 hours
  - Stagnation check for tasks with no update in 3+ days
  - Thread moderation (only assignee/leads can post)
  - Auto-archive and lock completed task threads
  - Dashboard auto-updates on status changes
- **Database Tables**
  - `tasks` - Task storage with status, deadline, ETA, priority
  - `task_history` - Audit log for all changes
  - `task_boards` - Dashboard message tracking per game

### Changed
- Updated README with task management documentation
- Updated Dockerfile to include assets directory
- Updated docker-compose.yml with assets volume mount

## [1.0.1] - 2026-01-01

### Added
- `/thuglife` command with local gif
- `/dodolife` command with tenor link

### Fixed
- Swapped thuglife/dodolife responses
- Moved gif to assets/ directory

## [1.0.0] - 2026-01-01

### Added
- **Game Management**
  - `/newgame` - Create game with auto-generated channels and roles
  - `/deletegame` - Remove game and all associated channels/roles
  - `/game list` - List all games
  - `/game addchannel` - Add custom channel to game
  - `/game removechannel` - Remove channel from game
- **Role Management**
  - `/assign add` - Assign member role (Coder, Artist, Audio, Writer, QA)
  - `/assign remove` - Remove member role
  - `/assign list` - List all members with roles
  - Auto-sync game roles based on member roles
- **Template System**
  - `/template list` - View channel template
  - `/template add` - Add channel to template
  - `/template remove` - Remove from template
  - `/template sync` - Sync template to all existing games
- **Group Management**
  - `/group list` - List groups and emojis
  - `/group emoji` - Change group emoji
- **Features**
  - 25+ default channels organized by group
  - Smart acronym generation (e.g., "Neon Drift" -> ND)
  - Automatic acronym conflict resolution
  - Channel descriptions/topics
  - Colored roles (random per game)
  - Emoji prefixes for channels
- Docker support with docker-compose
