import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
import json
import xml.etree.ElementTree as ET
from typing import Optional, List

from ..config import GUILD_ID
from ..database import (
    get_all_games,
    get_game_by_acronym,
    create_task,
    get_task,
    get_task_by_thread_id,
    get_tasks_by_game,
    get_tasks_by_assignee,
    get_tasks_by_status,
    get_tasks_due_soon,
    get_stagnant_tasks,
    update_task_thread,
    update_task_status,
    update_task_eta,
    update_task_assignee,
    update_task_priority,
    update_task_header_message,
    add_task_history,
    get_task_board,
    upsert_task_board,
)
from ..models import Task


# Status display mapping
STATUS_DISPLAY = {
    'todo': 'To Do',
    'progress': 'In Progress',
    'review': 'In Review',
    'done': 'Done',
    'cancelled': 'Cancelled'
}

STATUS_COLORS = {
    'todo': discord.Color.light_grey(),
    'progress': discord.Color.blue(),
    'review': discord.Color.orange(),
    'done': discord.Color.green(),
    'cancelled': discord.Color.dark_grey()
}

STATUS_EMOJI = {
    'todo': '\U0001f4cb',      # clipboard
    'progress': '\U0001f6a7',  # construction
    'review': '\U0001f50d',    # magnifying glass
    'done': '\u2705',          # check mark
    'cancelled': '\u274c'      # x mark
}

PRIORITY_EMOJI = {
    'Critical': '\U0001f534',  # red circle
    'High': '\U0001f7e0',      # orange circle
    'Medium': '\U0001f7e1',    # yellow circle
    'Low': '\U0001f7e2',       # green circle
}

# Role-based task styling
ROLE_TASK_STYLE = {
    'coder': {
        'emoji': '\U0001f4bb',  # laptop
        'color': discord.Color.blue(),
        'label': 'Code Task'
    },
    'artist': {
        'emoji': '\U0001f3a8',  # palette
        'color': discord.Color.purple(),
        'label': 'Art Task'
    },
    'audio': {
        'emoji': '\U0001f3b5',  # music note
        'color': discord.Color.gold(),
        'label': 'Audio Task'
    },
    'writer': {
        'emoji': '\u270d\ufe0f',  # writing hand
        'color': discord.Color.teal(),
        'label': 'Writing Task'
    },
    'qa': {
        'emoji': '\U0001f9ea',  # test tube
        'color': discord.Color.red(),
        'label': 'QA Task'
    },
    'default': {
        'emoji': '\U0001f4cb',  # clipboard
        'color': discord.Color.greyple(),
        'label': 'Task'
    }
}


class ReassignModal(discord.ui.Modal, title='Reassign Task'):
    user_id_input = discord.ui.TextInput(
        label='New Assignee User ID',
        placeholder='e.g., 123456789012345678',
        required=True,
        max_length=20
    )
    
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__()
        self.task_id = task_id
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return

        try:
            new_assignee_id = int(str(self.user_id_input))
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
            return

        new_assignee = interaction.guild.get_member(new_assignee_id)
        if not new_assignee:
            await interaction.response.send_message("User not found in this server.", ephemeral=True)
            return

        old_assignee_id = task.assignee_id
        await update_task_assignee(self.task_id, new_assignee_id)
        await add_task_history(self.task_id, interaction.user.id, 'reassign', str(old_assignee_id), str(new_assignee_id))

        # Update control panel in thread
        task.assignee_id = new_assignee_id
        await self.cog.update_control_panel(interaction, task)
        
        # Update header message
        await self.cog.update_header_message(interaction, task)
        
        # Notify new assignee in thread
        if task.thread_id:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread:
                await thread.send(f"{new_assignee.mention} You have been assigned this task!")

        await self.cog.update_dashboard(task.game_acronym, interaction.client)
        await interaction.response.send_message(f"Task reassigned to {new_assignee.mention}", ephemeral=True)


class HeaderView(discord.ui.View):
    """View attached to the header message (channel message before thread)."""
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.cog = cog

    async def check_lead(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        lead_roles = [r for r in interaction.user.roles if 'lead' in r.name.lower() or 'admin' in r.name.lower()]
        if not lead_roles:
            await interaction.response.send_message("Only Leads/Admins can use this button.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label='View Thread', style=discord.ButtonStyle.primary, emoji='\U0001f4ac', custom_id='header_view_thread')
    async def view_thread_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        task = await get_task(self.task_id)
        if not task or not task.thread_id:
            await interaction.response.send_message("Thread not found.", ephemeral=True)
            return
        
        thread = interaction.guild.get_channel(task.thread_id)
        if thread:
            await interaction.response.send_message(f"Go to thread: {thread.jump_url}", ephemeral=True)
        else:
            await interaction.response.send_message("Thread not found.", ephemeral=True)

    @discord.ui.button(label='Reassign', style=discord.ButtonStyle.secondary, emoji='\U0001f465', custom_id='header_reassign')
    async def reassign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_lead(interaction):
            return
        
        modal = ReassignModal(self.task_id, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Priority', style=discord.ButtonStyle.secondary, emoji='\u26a1', custom_id='header_priority')
    async def priority_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_lead(interaction):
            return
        
        # Show priority select
        view = PrioritySelectView(self.task_id, self.cog)
        await interaction.response.send_message("Select new priority:", view=view, ephemeral=True)

    @discord.ui.button(label='Cancel Task', style=discord.ButtonStyle.danger, emoji='\u274c', custom_id='header_cancel')
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_lead(interaction):
            return
        
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return

        if task.status == 'done':
            await interaction.response.send_message("Task is already completed.", ephemeral=True)
            return

        old_status = task.status
        await update_task_status(self.task_id, 'cancelled')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', old_status, 'cancelled')

        # Update embeds
        task.status = 'cancelled'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

        # Archive thread
        if task.thread_id:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread and isinstance(thread, discord.Thread):
                await thread.send(f"\u274c Task cancelled by {interaction.user.mention}")
                await thread.edit(archived=True, locked=True)

        await interaction.response.send_message("Task cancelled.", ephemeral=True)


class PrioritySelectView(discord.ui.View):
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__(timeout=60)
        self.task_id = task_id
        self.cog = cog

    @discord.ui.select(
        placeholder="Select priority...",
        options=[
            discord.SelectOption(label="Critical", value="Critical", emoji="\U0001f534"),
            discord.SelectOption(label="High", value="High", emoji="\U0001f7e0"),
            discord.SelectOption(label="Medium", value="Medium", emoji="\U0001f7e1"),
            discord.SelectOption(label="Low", value="Low", emoji="\U0001f7e2"),
        ]
    )
    async def priority_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return

        old_priority = task.priority
        new_priority = select.values[0]
        await update_task_priority(self.task_id, new_priority)
        await add_task_history(self.task_id, interaction.user.id, 'priority_change', old_priority, new_priority)

        task.priority = new_priority
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

        await interaction.response.send_message(f"Priority updated to: {new_priority}", ephemeral=True)


class ETAModal(discord.ui.Modal, title='Update ETA'):
    eta_input = discord.ui.TextInput(
        label='ETA',
        placeholder='e.g., Tomorrow, Friday, 2026-02-15',
        required=True,
        max_length=100
    )

    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__()
        self.task_id = task_id
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return

        old_eta = task.eta
        await update_task_eta(self.task_id, str(self.eta_input))
        await add_task_history(self.task_id, interaction.user.id, 'eta_update', old_eta, str(self.eta_input))

        # Update control panel
        task.eta = str(self.eta_input)
        await self.cog.update_control_panel(interaction, task)
        await interaction.response.send_message(f"ETA updated to: {self.eta_input}", ephemeral=True)


class TaskView(discord.ui.View):
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return False
        return True

    async def check_assignee(self, interaction: discord.Interaction) -> bool:
        task = await get_task(self.task_id)
        if interaction.user.id != task.assignee_id:
            await interaction.response.send_message("Only the assignee can use this button.", ephemeral=True)
            return False
        return True

    async def check_lead(self, interaction: discord.Interaction) -> bool:
        # Check if user has admin perms or a Lead role
        if interaction.user.guild_permissions.administrator:
            return True
        lead_roles = [r for r in interaction.user.roles if 'lead' in r.name.lower() or 'admin' in r.name.lower()]
        if not lead_roles:
            await interaction.response.send_message("Only Leads/Admins can use this button.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Start', style=discord.ButtonStyle.success, emoji='\u25b6\ufe0f', custom_id='task_start')
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_assignee(interaction):
            return

        task = await get_task(self.task_id)
        if task.status != 'todo':
            await interaction.response.send_message("Task must be in 'To Do' status to start.", ephemeral=True)
            return

        await update_task_status(self.task_id, 'progress')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', 'todo', 'progress')
        
        task.status = 'progress'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)
        await interaction.response.send_message("Task started!", ephemeral=True)

    @discord.ui.button(label='Pause', style=discord.ButtonStyle.secondary, emoji='\u23f8\ufe0f', custom_id='task_pause')
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_assignee(interaction):
            return

        task = await get_task(self.task_id)
        if task.status != 'progress':
            await interaction.response.send_message("Task must be 'In Progress' to pause.", ephemeral=True)
            return

        await update_task_status(self.task_id, 'todo')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', 'progress', 'todo')

        task.status = 'todo'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)
        await interaction.response.send_message("Task paused.", ephemeral=True)

    @discord.ui.button(label='Update ETA', style=discord.ButtonStyle.primary, emoji='\U0001f4c5', custom_id='task_eta')
    async def eta_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_assignee(interaction):
            return

        modal = ETAModal(self.task_id, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Question', style=discord.ButtonStyle.secondary, emoji='\u2753', custom_id='task_question')
    async def question_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_assignee(interaction):
            return

        task = await get_task(self.task_id)
        
        # Find leads channel for this game
        game = await get_game_by_acronym(task.game_acronym)
        if game:
            guild = interaction.guild
            leads_channel = discord.utils.find(
                lambda c: 'lead' in c.name.lower() and task.game_acronym.lower() in c.name.lower(),
                guild.text_channels
            )
            if leads_channel:
                thread = guild.get_channel(task.thread_id)
                thread_link = thread.jump_url if thread else "Thread not found"
                await leads_channel.send(
                    f"\u2753 **Question on Task:** {task.title}\n"
                    f"From: {interaction.user.mention}\n"
                    f"Thread: {thread_link}"
                )
                await interaction.response.send_message("Lead has been notified!", ephemeral=True)
                return

        await interaction.response.send_message("Could not find leads channel. Please contact a lead directly.", ephemeral=True)

    @discord.ui.button(label='Submit for Review', style=discord.ButtonStyle.success, emoji='\u2705', custom_id='task_review')
    async def review_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_assignee(interaction):
            return

        task = await get_task(self.task_id)
        if task.status not in ['todo', 'progress']:
            await interaction.response.send_message("Task cannot be submitted for review in current status.", ephemeral=True)
            return

        old_status = task.status
        await update_task_status(self.task_id, 'review')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', old_status, 'review')

        task.status = 'review'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

        # Notify leads
        game = await get_game_by_acronym(task.game_acronym)
        if game:
            guild = interaction.guild
            leads_channel = discord.utils.find(
                lambda c: 'lead' in c.name.lower() and task.game_acronym.lower() in c.name.lower(),
                guild.text_channels
            )
            if leads_channel:
                thread = guild.get_channel(task.thread_id)
                thread_link = thread.jump_url if thread else "Thread not found"
                await leads_channel.send(
                    f"\U0001f4e5 **Task Submitted for Review:** {task.title}\n"
                    f"By: {interaction.user.mention}\n"
                    f"Thread: {thread_link}"
                )

        await interaction.response.send_message("Task submitted for review! Lead has been notified.", ephemeral=True)

    @discord.ui.button(label='Approve & Close', style=discord.ButtonStyle.danger, emoji='\U0001f3c1', custom_id='task_approve')
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_lead(interaction):
            return

        task = await get_task(self.task_id)
        if task.status != 'review':
            await interaction.response.send_message("Task must be 'In Review' to approve.", ephemeral=True)
            return

        await update_task_status(self.task_id, 'done')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', 'review', 'done')

        task.status = 'done'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

        # Archive and lock thread
        thread = interaction.channel
        if isinstance(thread, discord.Thread):
            await thread.edit(archived=True, locked=True)

        await interaction.response.send_message("Task approved and closed!", ephemeral=True)


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    task_group = app_commands.Group(name="task", description="Task management")
    debug_group = app_commands.Group(name="debug", description="Debug/discovery commands")

    # ============== HELP COMMAND ==============

    @task_group.command(name="help", description="Show task management help and usage guide")
    async def task_help(self, interaction: discord.Interaction):
        embeds = []

        # Overview embed
        overview = discord.Embed(
            title="Task Management System",
            description=(
                "A Trello-style task tracking system for game development projects.\n\n"
                "**Key Concepts:**\n"
                "- **Task Board** - Dashboard showing all tasks by status\n"
                "- **Task Thread** - Dedicated thread per task for discussion\n"
                "- **Control Panel** - Interactive buttons in each thread"
            ),
            color=discord.Color.blue()
        )
        embeds.append(overview)

        # Commands embed
        commands_embed = discord.Embed(
            title="Commands",
            color=discord.Color.green()
        )
        commands_embed.add_field(
            name="Task Management (Admin)",
            value=(
                "`/task create` - Create a new task with thread\n"
                "`/task board <game>` - Show/refresh task dashboard\n"
                "`/task import <file>` - Bulk import from JSON/XML"
            ),
            inline=False
        )
        commands_embed.add_field(
            name="Task Viewing",
            value=(
                "`/task list [user]` - List active tasks\n"
                "`/task help` - Show this help"
            ),
            inline=False
        )
        commands_embed.add_field(
            name="Discovery (for imports)",
            value=(
                "`/debug list-channels` - Get channel IDs\n"
                "`/debug list-members` - Get member IDs"
            ),
            inline=False
        )
        embeds.append(commands_embed)

        # Workflow embed
        workflow = discord.Embed(
            title="Task Workflow",
            description=(
                "**Status Flow:**\n"
                "To Do -> In Progress -> In Review -> Done\n\n"
                "**Thread Buttons (Assignee):**\n"
                "- `Start` - Begin working (To Do -> In Progress)\n"
                "- `Pause` - Pause work (In Progress -> To Do)\n"
                "- `Update ETA` - Set estimated completion\n"
                "- `Question` - Ping leads for help\n"
                "- `Submit for Review` - Request approval\n\n"
                "**Thread Buttons (Lead/Admin):**\n"
                "- `Approve & Close` - Complete task, archive thread"
            ),
            color=discord.Color.orange()
        )
        embeds.append(workflow)

        # Import format embed
        import_embed = discord.Embed(
            title="Import Formats",
            color=discord.Color.purple()
        )
        import_embed.add_field(
            name="JSON Format",
            value=(
                "```json\n"
                "[\n"
                "  {\n"
                '    "title": "Task Name",\n'
                '    "description": "Details",\n'
                '    "assignee_id": "123456789",\n'
                '    "target_channel_id": "987654321",\n'
                '    "deadline": "2026-05-20",\n'
                '    "priority": "High"\n'
                "  }\n"
                "]\n"
                "```"
            ),
            inline=False
        )
        import_embed.add_field(
            name="XML Format",
            value=(
                "```xml\n"
                "<tasks>\n"
                "  <task>\n"
                "    <title>Task Name</title>\n"
                "    <assignee_id>123456789</assignee_id>\n"
                "    <target_channel_id>987654321</target_channel_id>\n"
                "  </task>\n"
                "</tasks>\n"
                "```"
            ),
            inline=False
        )
        import_embed.add_field(
            name="Getting IDs",
            value="Use `/debug list-channels` and `/debug list-members` to get Discord IDs for import files.",
            inline=False
        )
        embeds.append(import_embed)

        # Automation embed
        automation = discord.Embed(
            title="Automation",
            description=(
                "**Automatic Reminders:**\n"
                "- Tasks due within 24 hours get a warning ping\n"
                "- In-progress tasks with no update for 3 days get a check-in ping\n\n"
                "**Thread Moderation:**\n"
                "- Only assignee and leads can post in task threads\n"
                "- Completed tasks auto-archive and lock\n\n"
                "**Dashboard Updates:**\n"
                "- Board auto-updates when task status changes"
            ),
            color=discord.Color.red()
        )
        embeds.append(automation)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    # ============== DEBUG COMMANDS ==============

    @debug_group.command(name="list-channels", description="List channels with their IDs")
    @app_commands.describe(category_id="Optional category ID to filter")
    async def list_channels(self, interaction: discord.Interaction, category_id: str = None):
        guild = interaction.guild
        
        if category_id:
            try:
                cat = guild.get_channel(int(category_id))
                if not cat or not isinstance(cat, discord.CategoryChannel):
                    await interaction.response.send_message("Category not found.")
                    return
                channels = cat.channels
            except ValueError:
                await interaction.response.send_message("Invalid category ID.")
                return
        else:
            channels = guild.channels

        # Build output
        lines = []
        for ch in sorted(channels, key=lambda c: c.name):
            if isinstance(ch, discord.CategoryChannel):
                lines.append(f"**[Category]** {ch.name} | `{ch.id}`")
            elif isinstance(ch, discord.TextChannel):
                lines.append(f"#  {ch.name} | `{ch.id}`")
            elif isinstance(ch, discord.VoiceChannel):
                lines.append(f"vc {ch.name} | `{ch.id}`")

        # Paginate if needed
        output = "\n".join(lines[:50])  # Limit to 50
        if len(lines) > 50:
            output += f"\n... and {len(lines) - 50} more"

        embed = discord.Embed(title="Channels", description=output, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @debug_group.command(name="list-members", description="List members with their IDs")
    @app_commands.describe(role="Optional role to filter by")
    async def list_members(self, interaction: discord.Interaction, role: discord.Role = None):
        guild = interaction.guild
        
        if role:
            members = role.members
        else:
            members = [m for m in guild.members if not m.bot]

        lines = [f"{m.display_name} | `{m.id}`" for m in sorted(members, key=lambda m: m.display_name)]

        output = "\n".join(lines[:50])
        if len(lines) > 50:
            output += f"\n... and {len(lines) - 50} more"

        embed = discord.Embed(title="Members", description=output, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============== TASK CREATE ==============

    @task_group.command(name="create", description="Create a new task")
    @app_commands.describe(
        title="Task title",
        description="Task description",
        target_channel="Channel where the thread will be created",
        assignee="User to assign the task to",
        priority="Task priority",
        deadline="Deadline (YYYY-MM-DD)",
        game="Game acronym (auto-detected from channel if not provided)"
    )
    @app_commands.choices(priority=[
        app_commands.Choice(name="Critical", value="Critical"),
        app_commands.Choice(name="High", value="High"),
        app_commands.Choice(name="Medium", value="Medium"),
        app_commands.Choice(name="Low", value="Low"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def task_create(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        target_channel: discord.TextChannel,
        assignee: discord.Member,
        priority: str = None,
        deadline: str = None,
        game: str = None
    ):
        await interaction.response.defer()

        # Determine game acronym
        if game:
            game_obj = await get_game_by_acronym(game)
            if not game_obj:
                await interaction.followup.send(f"Game `{game}` not found.")
                return
            game_acronym = game_obj.acronym
        else:
            # Try to detect from channel name
            games = await get_all_games()
            game_acronym = None
            for g in games:
                if g.acronym.lower() in target_channel.name.lower():
                    game_acronym = g.acronym
                    break
            if not game_acronym:
                await interaction.followup.send("Could not detect game. Please specify with `game` parameter.")
                return

        # Create task in DB
        task = await create_task(
            game_acronym=game_acronym,
            title=title,
            description=description,
            assignee_id=assignee.id,
            target_channel_id=target_channel.id,
            deadline=deadline,
            priority=priority
        )

        # Get game name for embed
        game_obj = await get_game_by_acronym(game_acronym)
        game_name = game_obj.name if game_obj else game_acronym

        # Create header message with detailed embed and buttons
        header_embed = self.create_header_embed(task, assignee, game_name)
        header_view = HeaderView(task.id, self)
        header_msg = await target_channel.send(embed=header_embed, view=header_view)

        # Create thread
        thread = await header_msg.create_thread(name=f"Task: {title[:50]}")

        # Create control panel in thread
        control_embed = self.create_control_embed(task, assignee)
        view = TaskView(task.id, self)
        control_msg = await thread.send(embed=control_embed, view=view)

        # Update task with thread/message IDs
        await update_task_thread(task.id, thread.id, control_msg.id)
        await update_task_header_message(task.id, header_msg.id)
        
        # Update task object for later use
        task.thread_id = thread.id
        task.header_message_id = header_msg.id

        # Update header embed with thread link
        header_embed = self.create_header_embed(task, assignee, game_name)
        await header_msg.edit(embed=header_embed, view=header_view)

        # Ping assignee
        await thread.send(f"{assignee.mention} You have been assigned this task!")

        # Update dashboard
        await self.update_dashboard(game_acronym, self.bot)

        await interaction.followup.send(
            f"Task created: {thread.mention}\n"
            f"Assignee: {assignee.mention}\n"
            f"Deadline: {deadline or 'None'}"
        )

    def _get_role_style(self, member: discord.Member = None) -> dict:
        """Get task styling based on member's roles."""
        if not member:
            return ROLE_TASK_STYLE['default']
        
        role_names = [r.name.lower() for r in member.roles]
        
        for role_key in ['coder', 'artist', 'audio', 'writer', 'qa']:
            if role_key in role_names:
                return ROLE_TASK_STYLE[role_key]
        
        return ROLE_TASK_STYLE['default']

    def create_control_embed(self, task: Task, assignee: discord.Member = None) -> discord.Embed:
        """Create the detailed control panel embed shown inside the thread."""
        status = task.status or 'todo'
        role_style = self._get_role_style(assignee)
        
        # Use status color if not todo, otherwise use role color
        if status == 'todo':
            color = role_style['color']
        else:
            color = STATUS_COLORS.get(status, discord.Color.greyple())
        
        embed = discord.Embed(
            title=f"{role_style['emoji']} {task.title}",
            description=task.description or "No description provided.",
            color=color
        )
        
        # Status (prominent)
        embed.add_field(
            name="Status", 
            value=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}", 
            inline=True
        )
        
        # Priority
        if task.priority:
            priority_emoji = PRIORITY_EMOJI.get(task.priority, '')
            embed.add_field(name="Priority", value=f"{priority_emoji} {task.priority}", inline=True)
        
        # Deadline
        if task.deadline:
            embed.add_field(name="Deadline", value=f"\U0001f4c5 {str(task.deadline)[:10]}", inline=True)
        
        # ETA (assignee sets this)
        if task.eta:
            embed.add_field(name="Your ETA", value=f"\u23f0 {task.eta}", inline=True)
        
        # Footer
        embed.set_footer(text=f"Task #{task.id} | Use buttons below to update")

        return embed

    async def update_control_panel(self, interaction: discord.Interaction, task: Task):
        """Update the control panel embed in the thread."""
        if not task.control_message_id or not task.thread_id:
            return

        try:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread:
                msg = await thread.fetch_message(task.control_message_id)
                # Try to get assignee for role styling
                assignee = interaction.guild.get_member(task.assignee_id)
                embed = self.create_control_embed(task, assignee)
                view = TaskView(task.id, self) if task.status not in ('done', 'cancelled') else None
                await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    def create_header_embed(self, task: Task, assignee: discord.Member = None, game_name: str = None) -> discord.Embed:
        """Create the compact header embed shown in the channel (before thread)."""
        status = task.status or 'todo'
        role_style = self._get_role_style(assignee)
        
        # Use status color if not todo, otherwise use role color
        if status == 'todo':
            color = role_style['color']
        else:
            color = STATUS_COLORS.get(status, discord.Color.greyple())
        
        # Compact title with role label
        embed = discord.Embed(
            title=f"{role_style['emoji']} {role_style['label']}: {task.title}",
            color=color
        )
        
        # Assignee
        if assignee:
            embed.add_field(name="Assigned", value=assignee.mention, inline=True)
        else:
            embed.add_field(name="Assigned", value=f"<@{task.assignee_id}>", inline=True)
        
        # Status
        embed.add_field(
            name="Status", 
            value=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}", 
            inline=True
        )
        
        # Priority (if set)
        if task.priority:
            priority_emoji = PRIORITY_EMOJI.get(task.priority, '')
            embed.add_field(name="Priority", value=f"{priority_emoji} {task.priority}", inline=True)
        
        # Deadline (if set)
        if task.deadline:
            embed.add_field(name="Due", value=str(task.deadline)[:10], inline=True)
        
        # Footer with task ID
        embed.set_footer(text=f"#{task.id} | {game_name or task.game_acronym}")

        return embed

    async def update_header_message(self, interaction: discord.Interaction, task: Task):
        """Update the header message embed in the channel."""
        if not task.header_message_id or not task.target_channel_id:
            return

        try:
            channel = interaction.guild.get_channel(task.target_channel_id)
            if channel:
                msg = await channel.fetch_message(task.header_message_id)
                embed = self.create_header_embed(task)
                view = HeaderView(task.id, self) if task.status not in ('done', 'cancelled') else None
                await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    # ============== TASK BOARD ==============

    @task_group.command(name="board", description="Show or refresh the task board for a game")
    @app_commands.describe(
        game="Game acronym",
        refresh="Force refresh the board"
    )
    async def task_board(self, interaction: discord.Interaction, game: str, refresh: bool = False):
        await interaction.response.defer()

        game_obj = await get_game_by_acronym(game)
        if not game_obj:
            await interaction.followup.send(f"Game `{game}` not found.")
            return

        tasks = await get_tasks_by_game(game)

        # Group by status
        by_status = {
            'todo': [],
            'progress': [],
            'review': [],
            'done': []
        }
        for t in tasks:
            if t.status in by_status:
                by_status[t.status].append(t)

        # Create embeds
        embeds = []
        for status, status_tasks in by_status.items():
            embed = discord.Embed(
                title=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}",
                color=STATUS_COLORS.get(status, discord.Color.greyple())
            )
            
            if status_tasks:
                desc_lines = []
                for t in status_tasks[:10]:  # Limit to 10 per status
                    thread_link = f"<#{t.thread_id}>" if t.thread_id else ""
                    assignee = f"<@{t.assignee_id}>"
                    deadline_str = f" (Due: {str(t.deadline)[:10]})" if t.deadline else ""
                    desc_lines.append(f"**{t.title}** - {assignee}{deadline_str}\n{thread_link}")
                embed.description = "\n".join(desc_lines)
            else:
                embed.description = "*No tasks*"
            
            embeds.append(embed)

        # Check if board exists
        existing_board = await get_task_board(game)
        
        if existing_board and not refresh:
            # Try to edit existing messages
            try:
                channel = interaction.guild.get_channel(existing_board.channel_id)
                if channel:
                    msg_ids = json.loads(existing_board.message_ids)
                    for i, msg_id in enumerate(msg_ids):
                        if i < len(embeds):
                            msg = await channel.fetch_message(msg_id)
                            await msg.edit(embed=embeds[i])
                    await interaction.followup.send("Board updated!")
                    return
            except (discord.NotFound, discord.HTTPException):
                pass  # Fall through to create new

        # Create new board messages
        msg_ids = []
        for embed in embeds:
            msg = await interaction.channel.send(embed=embed)
            msg_ids.append(msg.id)

        await upsert_task_board(game, interaction.channel.id, json.dumps(msg_ids))
        await interaction.followup.send("Task board created!")

    async def update_dashboard(self, game_acronym: str, bot: commands.Bot):
        """Update the dashboard for a game."""
        board = await get_task_board(game_acronym)
        if not board:
            return

        guild = bot.get_guild(int(GUILD_ID)) if GUILD_ID else None
        if not guild:
            return

        channel = guild.get_channel(board.channel_id)
        if not channel:
            return

        tasks = await get_tasks_by_game(game_acronym)

        # Group by status
        by_status = {
            'todo': [],
            'progress': [],
            'review': [],
            'done': []
        }
        for t in tasks:
            if t.status in by_status:
                by_status[t.status].append(t)

        # Update embeds
        try:
            msg_ids = json.loads(board.message_ids)
            statuses = ['todo', 'progress', 'review', 'done']
            
            for i, status in enumerate(statuses):
                if i >= len(msg_ids):
                    break
                    
                embed = discord.Embed(
                    title=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}",
                    color=STATUS_COLORS.get(status, discord.Color.greyple())
                )
                
                status_tasks = by_status[status]
                if status_tasks:
                    desc_lines = []
                    for t in status_tasks[:10]:
                        thread_link = f"<#{t.thread_id}>" if t.thread_id else ""
                        assignee = f"<@{t.assignee_id}>"
                        deadline_str = f" (Due: {str(t.deadline)[:10]})" if t.deadline else ""
                        desc_lines.append(f"**{t.title}** - {assignee}{deadline_str}\n{thread_link}")
                    embed.description = "\n".join(desc_lines)
                else:
                    embed.description = "*No tasks*"

                try:
                    msg = await channel.fetch_message(msg_ids[i])
                    await msg.edit(embed=embed)
                except discord.NotFound:
                    pass
        except (json.JSONDecodeError, discord.HTTPException):
            pass

    # ============== TASK LIST ==============

    @task_group.command(name="list", description="List your tasks or tasks for a user")
    @app_commands.describe(user="User to list tasks for (defaults to you)")
    async def task_list(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        tasks = await get_tasks_by_assignee(target.id)

        if not tasks:
            await interaction.response.send_message(
                f"No active tasks for {target.mention}.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Tasks for {target.display_name}",
            color=discord.Color.blue()
        )

        for task in tasks[:10]:
            status_str = f"{STATUS_EMOJI.get(task.status, '')} {STATUS_DISPLAY.get(task.status, task.status)}"
            thread_link = f"<#{task.thread_id}>" if task.thread_id else ""
            deadline_str = f"\nDeadline: {str(task.deadline)[:10]}" if task.deadline else ""
            
            embed.add_field(
                name=f"{task.title} [{task.game_acronym}]",
                value=f"Status: {status_str}{deadline_str}\n{thread_link}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============== TASK IMPORT ==============

    @task_group.command(name="import", description="Import tasks from JSON or XML file")
    @app_commands.describe(file="JSON or XML file with tasks")
    @app_commands.checks.has_permissions(administrator=True)
    async def task_import(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer()

        if not file.filename.endswith(('.json', '.xml')):
            await interaction.followup.send("File must be .json or .xml")
            return

        content = await file.read()
        content = content.decode('utf-8')

        tasks_data = []

        try:
            if file.filename.endswith('.json'):
                tasks_data = json.loads(content)
            else:
                root = ET.fromstring(content)
                for task_elem in root.findall('task'):
                    task_dict = {
                        'title': task_elem.findtext('title', ''),
                        'description': task_elem.findtext('description', ''),
                        'assignee_id': task_elem.findtext('assignee_id', ''),
                        'target_channel_id': task_elem.findtext('target_channel_id', ''),
                        'deadline': task_elem.findtext('deadline'),
                        'priority': task_elem.findtext('priority')
                    }
                    tasks_data.append(task_dict)
        except (json.JSONDecodeError, ET.ParseError) as e:
            await interaction.followup.send(f"Parse error: {e}")
            return

        # Validate and create tasks
        created = 0
        errors = []

        for i, td in enumerate(tasks_data):
            try:
                # Validate required fields
                if not td.get('title'):
                    errors.append(f"Task {i+1}: missing title")
                    continue
                if not td.get('assignee_id'):
                    errors.append(f"Task {i+1}: missing assignee_id")
                    continue
                if not td.get('target_channel_id'):
                    errors.append(f"Task {i+1}: missing target_channel_id")
                    continue

                assignee_id = int(td['assignee_id'])
                target_channel_id = int(td['target_channel_id'])

                # Verify channel exists
                channel = interaction.guild.get_channel(target_channel_id)
                if not channel:
                    errors.append(f"Task {i+1}: channel {target_channel_id} not found")
                    continue

                # Verify member exists
                member = interaction.guild.get_member(assignee_id)
                if not member:
                    errors.append(f"Task {i+1}: member {assignee_id} not found")
                    continue

                # Detect game from channel
                games = await get_all_games()
                game_acronym = None
                for g in games:
                    if g.acronym.lower() in channel.name.lower():
                        game_acronym = g.acronym
                        break
                
                if not game_acronym:
                    errors.append(f"Task {i+1}: could not detect game from channel")
                    continue

                # Create task
                task = await create_task(
                    game_acronym=game_acronym,
                    title=td['title'],
                    description=td.get('description', ''),
                    assignee_id=assignee_id,
                    target_channel_id=target_channel_id,
                    deadline=td.get('deadline'),
                    priority=td.get('priority')
                )

                # Get game name for embed
                game_obj = await get_game_by_acronym(game_acronym)
                game_name = game_obj.name if game_obj else game_acronym

                # Create header message with detailed embed and buttons
                header_embed = self.create_header_embed(task, member, game_name)
                header_view = HeaderView(task.id, self)
                header_msg = await channel.send(embed=header_embed, view=header_view)
                
                # Create thread
                thread = await header_msg.create_thread(name=f"Task: {task.title[:50]}")

                # Create control panel in thread
                control_embed = self.create_control_embed(task, member)
                view = TaskView(task.id, self)
                control_msg = await thread.send(embed=control_embed, view=view)

                # Update task with thread/message IDs
                await update_task_thread(task.id, thread.id, control_msg.id)
                await update_task_header_message(task.id, header_msg.id)
                
                # Update task object and refresh header with thread link
                task.thread_id = thread.id
                task.header_message_id = header_msg.id
                header_embed = self.create_header_embed(task, member, game_name)
                await header_msg.edit(embed=header_embed, view=header_view)

                # Notify assignee
                await thread.send(f"{member.mention} You have been assigned this task!")

                created += 1

            except Exception as e:
                errors.append(f"Task {i+1}: {str(e)}")

        # Update dashboards
        games = await get_all_games()
        for g in games:
            await self.update_dashboard(g.acronym, self.bot)

        result = f"Imported {created} tasks."
        if errors:
            result += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                result += f"\n... and {len(errors) - 10} more"

        await interaction.followup.send(result)

    # ============== BACKGROUND TASKS ==============

    @tasks.loop(hours=1)
    async def reminder_loop(self):
        """Check for upcoming deadlines and stagnant tasks."""
        if not GUILD_ID:
            return

        guild = self.bot.get_guild(int(GUILD_ID))
        if not guild:
            return

        # Check tasks due within 24 hours
        due_soon = await get_tasks_due_soon(24)
        for task in due_soon:
            if task.thread_id:
                thread = guild.get_channel(task.thread_id)
                if thread:
                    try:
                        await thread.send(
                            f"\u26a0\ufe0f <@{task.assignee_id}> This task is due within 24 hours!"
                        )
                    except discord.HTTPException:
                        pass

        # Check stagnant tasks (no update in 3 days)
        stagnant = await get_stagnant_tasks(3)
        for task in stagnant:
            if task.thread_id:
                thread = guild.get_channel(task.thread_id)
                if thread:
                    try:
                        await thread.send(
                            f"\U0001f4ac <@{task.assignee_id}> Update request: How is this task going?"
                        )
                    except discord.HTTPException:
                        pass

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    # ============== THREAD MONITOR ==============

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor messages in task threads."""
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.Thread):
            return

        # Check if this thread is a task thread
        task = await get_task_by_thread_id(message.channel.id)
        if not task:
            return

        # Check if sender is assignee or lead/admin
        is_assignee = message.author.id == task.assignee_id
        is_lead = message.author.guild_permissions.administrator
        
        if not is_lead:
            lead_roles = [r for r in message.author.roles if 'lead' in r.name.lower() or 'admin' in r.name.lower()]
            is_lead = len(lead_roles) > 0

        if not is_assignee and not is_lead:
            # Optional: warn or delete
            try:
                await message.reply(
                    "Only the assignee and leads can discuss in this task thread.",
                    delete_after=10
                )
                await message.delete()
            except discord.HTTPException:
                pass

    # ============== AUTOCOMPLETE ==============

    @task_create.autocomplete("game")
    @task_board.autocomplete("game")
    async def game_autocomplete(self, interaction: discord.Interaction, current: str):
        games = await get_all_games()
        return [
            app_commands.Choice(name=f"{g.acronym} - {g.name}", value=g.acronym)
            for g in games
            if current.lower() in g.acronym.lower() or current.lower() in g.name.lower()
        ][:25]


async def setup(bot: commands.Bot):
    cog = TasksCog(bot)
    await bot.add_cog(cog)
    
    # Register persistent views for existing tasks
    # This is called when bot restarts to re-attach button handlers
    from ..database import get_tasks_by_status
    
    for status in ['todo', 'progress', 'review']:
        tasks = await get_tasks_by_status(status)
        for task in tasks:
            if task.thread_id:
                bot.add_view(TaskView(task.id, cog))
            if task.header_message_id:
                bot.add_view(HeaderView(task.id, cog))
