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
    delete_task,
    add_task_assignee,
    remove_task_assignee,
    get_task_assignees,
    get_task_primary_assignee,
    set_task_primary_assignee,
    clear_task_primary_assignee,
    set_task_assignee_approval,
    get_task_approval_status,
    reset_task_approvals,
    is_user_task_assignee,
    get_tasks_by_assignee_multi,
    get_server_config,
    is_setup_completed,
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


class AddMemberModal(discord.ui.Modal, title='Add Team Member'):
    user_id_input = discord.ui.TextInput(
        label='User ID',
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
            user_id = int(str(self.user_id_input))
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
            return

        member = interaction.guild.get_member(user_id)
        if not member:
            await interaction.response.send_message("User not found in this server.", ephemeral=True)
            return

        await add_task_assignee(self.task_id, user_id)
        await add_task_history(self.task_id, interaction.user.id, 'add_assignee', None, str(user_id))

        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)

        if task.thread_id:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread:
                await thread.send(f"{member.mention} You have been added to this task!")

        await self.cog.update_dashboard(task.game_acronym, interaction.client)
        await interaction.response.send_message(f"Added {member.mention} to the team.", ephemeral=True)


class ManageTeamView(discord.ui.View):
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__(timeout=120)
        self.task_id = task_id
        self.cog = cog

    @discord.ui.button(label='Add Member', style=discord.ButtonStyle.success, emoji='\u2795')
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddMemberModal(self.task_id, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Remove Member', style=discord.ButtonStyle.danger, emoji='\u2796')
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        assignees = await get_task_assignees(self.task_id)
        if len(assignees) <= 1:
            await interaction.response.send_message("Cannot remove the last team member.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=f"<@{a.user_id}>" if not interaction.guild.get_member(a.user_id) 
                      else interaction.guild.get_member(a.user_id).display_name,
                value=str(a.user_id),
                description="Primary owner" if a.is_primary else None
            )
            for a in assignees
        ]

        select = RemoveMemberSelect(self.task_id, self.cog, options)
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Select member to remove:", view=view, ephemeral=True)

    @discord.ui.button(label='Set Primary', style=discord.ButtonStyle.primary, emoji='\u2b50')
    async def set_primary(self, interaction: discord.Interaction, button: discord.ui.Button):
        assignees = await get_task_assignees(self.task_id)
        if len(assignees) < 2:
            await interaction.response.send_message("Need at least 2 members to set a primary.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=interaction.guild.get_member(a.user_id).display_name 
                      if interaction.guild.get_member(a.user_id) else str(a.user_id),
                value=str(a.user_id),
                description="Current primary" if a.is_primary else None,
                default=a.is_primary
            )
            for a in assignees
        ]

        select = SetPrimarySelect(self.task_id, self.cog, options)
        view = discord.ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Select primary owner:", view=view, ephemeral=True)

    @discord.ui.button(label='Remove Primary', style=discord.ButtonStyle.secondary, emoji='\u274c')
    async def remove_primary(self, interaction: discord.Interaction, button: discord.ui.Button):
        primary = await get_task_primary_assignee(self.task_id)
        if not primary:
            await interaction.response.send_message("No primary owner set.", ephemeral=True)
            return

        await clear_task_primary_assignee(self.task_id)
        task = await get_task(self.task_id)
        await add_task_history(self.task_id, interaction.user.id, 'remove_primary', str(primary.user_id), None)
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)
        await interaction.response.send_message("Primary owner removed. Team approval rules now apply.", ephemeral=True)


class RemoveMemberSelect(discord.ui.Select):
    def __init__(self, task_id: int, cog: 'TasksCog', options: list):
        super().__init__(placeholder="Select member to remove...", options=options)
        self.task_id = task_id
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        user_id = int(self.values[0])
        await remove_task_assignee(self.task_id, user_id)
        task = await get_task(self.task_id)
        await add_task_history(self.task_id, interaction.user.id, 'remove_assignee', str(user_id), None)
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

        member = interaction.guild.get_member(user_id)
        name = member.mention if member else f"User {user_id}"
        await interaction.response.send_message(f"Removed {name} from the team.", ephemeral=True)


class SetPrimarySelect(discord.ui.Select):
    def __init__(self, task_id: int, cog: 'TasksCog', options: list):
        super().__init__(placeholder="Select primary owner...", options=options)
        self.task_id = task_id
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        user_id = int(self.values[0])
        old_primary = await get_task_primary_assignee(self.task_id)
        await set_task_primary_assignee(self.task_id, user_id)
        task = await get_task(self.task_id)
        
        old_val = str(old_primary.user_id) if old_primary else None
        await add_task_history(self.task_id, interaction.user.id, 'set_primary', old_val, str(user_id))
        
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)

        member = interaction.guild.get_member(user_id)
        name = member.mention if member else f"User {user_id}"
        await interaction.response.send_message(f"Set {name} as primary owner.", ephemeral=True)


class HeaderView(discord.ui.View):
    """View attached to the header message (channel message before thread)."""
    def __init__(self, task_id: int, cog: 'TasksCog'):
        super().__init__(timeout=None)
        self.task_id = task_id
        self.cog = cog
        
        # Update custom_ids to include task_id for persistence
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id:
                item.custom_id = f"{item.custom_id}:{task_id}"

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

    @discord.ui.button(label='Manage Team', style=discord.ButtonStyle.secondary, emoji='\U0001f465', custom_id='header_manage_team')
    async def manage_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_lead(interaction):
            return
        
        view = ManageTeamView(self.task_id, self.cog)
        await interaction.response.send_message("Manage task team:", view=view, ephemeral=True)

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
        
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id:
                item.custom_id = f"{item.custom_id}:{task_id}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        task = await get_task(self.task_id)
        if not task:
            await interaction.response.send_message("Task not found.", ephemeral=True)
            return False
        return True

    async def check_assignee(self, interaction: discord.Interaction) -> bool:
        is_assignee = await is_user_task_assignee(self.task_id, interaction.user.id)
        if not is_assignee:
            await interaction.response.send_message("Only team members can use this button.", ephemeral=True)
            return False
        return True

    async def check_assignee_or_lead(self, interaction: discord.Interaction) -> bool:
        is_assignee = await is_user_task_assignee(self.task_id, interaction.user.id)
        if is_assignee:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
        lead_roles = [r for r in interaction.user.roles if 'lead' in r.name.lower() or 'admin' in r.name.lower()]
        if lead_roles:
            return True
        await interaction.response.send_message("Only team members or leads can use this button.", ephemeral=True)
        return False

    async def check_lead(self, interaction: discord.Interaction) -> bool:
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
        if not await self.check_assignee_or_lead(interaction):
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
        await self.cog.update_header_message(interaction, task)
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
        if not await self.check_assignee_or_lead(interaction):
            return

        task = await get_task(self.task_id)
        if task.status not in ['todo', 'progress', 'review']:
            await interaction.response.send_message("Task is already completed.", ephemeral=True)
            return

        approval_status = await get_task_approval_status(self.task_id)
        is_lead = interaction.user.guild_permissions.administrator or any(
            'lead' in r.name.lower() or 'admin' in r.name.lower() 
            for r in interaction.user.roles
        )

        if is_lead:
            await self._complete_task(interaction, task)
            return

        if approval_status['primary'] and approval_status['primary'].user_id == interaction.user.id:
            await self._complete_task(interaction, task)
            return

        if approval_status['primary']:
            await interaction.response.send_message(
                f"Only the primary owner (<@{approval_status['primary'].user_id}>) can close this task.",
                ephemeral=True
            )
            return

        await set_task_assignee_approval(self.task_id, interaction.user.id, True)
        approval_status = await get_task_approval_status(self.task_id)

        config = await get_server_config(interaction.guild.id)
        approval_mode = 'auto'
        if config and config.config_json:
            try:
                cfg = json.loads(config.config_json)
                approval_mode = cfg.get('approval_mode', 'auto')
            except json.JSONDecodeError:
                pass

        total = approval_status['total']
        approved = approval_status['approved']
        required = self._calculate_required_approvals(total, approval_mode)

        if approved >= required:
            await self._complete_task(interaction, task)
        else:
            await self.cog.update_control_panel(interaction, task)
            await interaction.response.send_message(
                f"Your approval recorded! ({approved}/{required} needed to close)",
                ephemeral=True
            )

    def _calculate_required_approvals(self, total: int, mode: str) -> int:
        if mode == 'any':
            return 1
        if mode == 'all':
            return total
        if mode == 'majority':
            return (total // 2) + 1
        if total == 2:
            return 2
        return (total // 2) + 1

    async def _complete_task(self, interaction: discord.Interaction, task: Task):
        old_status = task.status
        await update_task_status(self.task_id, 'done')
        await add_task_history(self.task_id, interaction.user.id, 'status_change', old_status, 'done')

        task.status = 'done'
        await self.cog.update_control_panel(interaction, task)
        await self.cog.update_header_message(interaction, task)
        await self.cog.update_dashboard(task.game_acronym, interaction.client)

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
                "`/task import <file>` - Bulk import from JSON/XML\n"
                "`/task close [id]` - Close task (run in thread or specify ID)"
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

    @task_group.command(name="new", description="Create a new task")
    @app_commands.describe(
        title="Task title",
        description="Task description",
        target_channel="Channel where the thread will be created",
        assignee="Primary user to assign the task to",
        additional_assignees="Additional team members (comma-separated user IDs)",
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
    async def task_new(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        target_channel: discord.TextChannel,
        assignee: discord.Member,
        additional_assignees: str = None,
        priority: str = None,
        deadline: str = None,
        game: str = None
    ):
        await interaction.response.defer()

        setup_complete = await is_setup_completed(interaction.guild.id)
        if not setup_complete:
            await interaction.followup.send(
                "\u26a0\ufe0f **Setup not complete.** Some features may not work correctly.\n"
                "Run `/setup` to configure the task system.\n\n"
                "Creating task anyway...",
                ephemeral=True
            )

        if game:
            game_obj = await get_game_by_acronym(game)
            if not game_obj:
                await interaction.followup.send(f"Game `{game}` not found.")
                return
            game_acronym = game_obj.acronym
        else:
            games = await get_all_games()
            game_acronym = None
            for g in games:
                if g.acronym.lower() in target_channel.name.lower():
                    game_acronym = g.acronym
                    break
            if not game_acronym:
                await interaction.followup.send("Could not detect game. Please specify with `game` parameter.")
                return

        task = await create_task(
            game_acronym=game_acronym,
            title=title,
            description=description,
            assignee_id=assignee.id,
            target_channel_id=target_channel.id,
            deadline=deadline,
            priority=priority
        )

        all_assignees = [assignee]
        is_primary = len(additional_assignees.split(',')) > 0 if additional_assignees else False
        await add_task_assignee(task.id, assignee.id, is_primary=is_primary)

        if additional_assignees:
            for uid_str in additional_assignees.split(','):
                uid_str = uid_str.strip()
                try:
                    uid = int(uid_str)
                    member = interaction.guild.get_member(uid)
                    if member:
                        await add_task_assignee(task.id, uid, is_primary=False)
                        all_assignees.append(member)
                except ValueError:
                    pass

        game_obj = await get_game_by_acronym(game_acronym)
        game_name = game_obj.name if game_obj else game_acronym

        header_embed = self.create_header_embed(task, all_assignees, game_name)
        header_view = HeaderView(task.id, self)
        header_msg = await target_channel.send(embed=header_embed, view=header_view)

        thread = await header_msg.create_thread(name=f"Task: {title[:50]}")

        control_embed = self.create_control_embed(task, all_assignees, game_name)
        view = TaskView(task.id, self)
        control_msg = await thread.send(embed=control_embed, view=view)

        await update_task_thread(task.id, thread.id, control_msg.id)
        await update_task_header_message(task.id, header_msg.id)
        
        task.thread_id = thread.id
        task.header_message_id = header_msg.id

        header_embed = self.create_header_embed(task, all_assignees, game_name)
        await header_msg.edit(embed=header_embed, view=header_view)

        mentions = ' '.join(m.mention for m in all_assignees)
        await thread.send(f"{mentions} You have been assigned this task!")

        await self.update_dashboard(game_acronym, self.bot)

        assignee_list = ', '.join(m.mention for m in all_assignees)
        await interaction.followup.send(
            f"Task created: {thread.mention}\n"
            f"Team: {assignee_list}\n"
            f"Deadline: {deadline or 'None'}"
        )

    def _get_role_style(self, members=None) -> dict:
        if not members:
            return ROLE_TASK_STYLE['default']
        
        if isinstance(members, list):
            member = members[0] if members else None
        else:
            member = members
            
        if not member:
            return ROLE_TASK_STYLE['default']
        
        role_names = [r.name.lower() for r in member.roles]
        
        for role_key in ['coder', 'artist', 'audio', 'writer', 'qa']:
            if role_key in role_names:
                return ROLE_TASK_STYLE[role_key]
        
        return ROLE_TASK_STYLE['default']

    def create_control_embed(self, task: Task, assignees=None, game_name: str = None) -> discord.Embed:
        status = task.status or 'todo'
        role_style = self._get_role_style(assignees)
        
        if status == 'todo':
            color = role_style['color']
        else:
            color = STATUS_COLORS.get(status, discord.Color.greyple())
        
        embed = discord.Embed(
            title=f"{role_style['emoji']} {task.title}",
            description=task.description or "No description provided.",
            color=color
        )
        
        if assignees:
            if isinstance(assignees, list):
                mentions = ', '.join(m.mention for m in assignees)
                embed.add_field(name="Team", value=mentions, inline=True)
            else:
                embed.add_field(name="Assignee", value=assignees.mention, inline=True)
        else:
            embed.add_field(name="Assignee", value=f"<@{task.assignee_id}>", inline=True)
        
        embed.add_field(
            name="Status", 
            value=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}", 
            inline=True
        )
        
        if game_name:
            embed.add_field(name="Project", value=f"\U0001f3ae {game_name}", inline=True)
        elif task.game_acronym:
            embed.add_field(name="Project", value=f"\U0001f3ae {task.game_acronym}", inline=True)
        
        if task.priority:
            priority_emoji = PRIORITY_EMOJI.get(task.priority, '')
            embed.add_field(name="Priority", value=f"{priority_emoji} {task.priority}", inline=True)
        else:
            embed.add_field(name="Priority", value="Not set", inline=True)
        
        if task.deadline:
            embed.add_field(name="Deadline", value=f"\U0001f4c5 {str(task.deadline)[:10]}", inline=True)
        else:
            embed.add_field(name="Deadline", value="Not set", inline=True)
        
        if task.eta:
            embed.add_field(name="ETA", value=f"\u23f0 {task.eta}", inline=True)
        else:
            embed.add_field(name="ETA", value="Not set", inline=True)
        
        if task.created_at:
            embed.add_field(name="Created", value=str(task.created_at)[:10], inline=True)
        
        embed.set_footer(text=f"Task #{task.id} | Use buttons below to update status")

        return embed

    async def update_control_panel(self, interaction: discord.Interaction, task: Task):
        if not task.control_message_id or not task.thread_id:
            return

        try:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread:
                msg = await thread.fetch_message(task.control_message_id)
                assignees_data = await get_task_assignees(task.id)
                assignees = [interaction.guild.get_member(a.user_id) for a in assignees_data]
                assignees = [m for m in assignees if m]
                game_obj = await get_game_by_acronym(task.game_acronym)
                game_name = game_obj.name if game_obj else None
                embed = self.create_control_embed(task, assignees if assignees else None, game_name)
                view = TaskView(task.id, self) if task.status not in ('done', 'cancelled') else None
                await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    def create_header_embed(self, task: Task, assignees=None, game_name: str = None) -> discord.Embed:
        status = task.status or 'todo'
        role_style = self._get_role_style(assignees)
        
        if status == 'todo':
            color = role_style['color']
        else:
            color = STATUS_COLORS.get(status, discord.Color.greyple())
        
        embed = discord.Embed(
            title=f"{role_style['emoji']} {task.title}",
            color=color
        )
        
        if assignees:
            if isinstance(assignees, list):
                mentions = ', '.join(m.mention for m in assignees)
                embed.add_field(name="Team", value=mentions, inline=True)
            else:
                embed.add_field(name="Assigned to", value=assignees.mention, inline=True)
        else:
            embed.add_field(name="Assigned to", value=f"<@{task.assignee_id}>", inline=True)
        
        embed.add_field(
            name="Status", 
            value=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)}", 
            inline=True
        )

        return embed

    async def update_header_message(self, interaction: discord.Interaction, task: Task):
        if not task.header_message_id or not task.target_channel_id:
            return

        try:
            channel = interaction.guild.get_channel(task.target_channel_id)
            if channel:
                msg = await channel.fetch_message(task.header_message_id)
                assignees_data = await get_task_assignees(task.id)
                assignees = [interaction.guild.get_member(a.user_id) for a in assignees_data]
                assignees = [m for m in assignees if m]
                embed = self.create_header_embed(task, assignees if assignees else None)
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

    @task_group.command(name="setup", description="Set up a task board channel for a game")
    @app_commands.describe(
        game="Game acronym",
        channel="Channel to use as the task board (current channel if not specified)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def task_setup(
        self,
        interaction: discord.Interaction,
        game: str,
        channel: discord.TextChannel = None
    ):
        """Set up or update the task board channel for a game."""
        await interaction.response.defer()

        game_obj = await get_game_by_acronym(game)
        if not game_obj:
            await interaction.followup.send(f"Game `{game}` not found.")
            return

        target_channel = channel or interaction.channel

        # Check if board already exists
        existing_board = await get_task_board(game)
        if existing_board:
            # Delete old board messages if possible
            try:
                old_channel = interaction.guild.get_channel(existing_board.channel_id)
                if old_channel:
                    msg_ids = json.loads(existing_board.message_ids)
                    for msg_id in msg_ids:
                        try:
                            msg = await old_channel.fetch_message(msg_id)
                            await msg.delete()
                        except discord.NotFound:
                            pass
            except (json.JSONDecodeError, discord.HTTPException):
                pass

        # Get tasks for this game
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

        # Create header embed
        header_embed = discord.Embed(
            title=f"\U0001f4cb Task Board: {game_obj.name}",
            description=f"All tasks for **{game_obj.name}** ({game_obj.acronym})\nUpdates automatically when task status changes.",
            color=discord.Color.blue()
        )
        await target_channel.send(embed=header_embed)

        # Create status embeds
        msg_ids = []
        for status in ['todo', 'progress', 'review', 'done']:
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
                    priority_str = f" [{t.priority}]" if t.priority else ""
                    deadline_str = f" (Due: {str(t.deadline)[:10]})" if t.deadline else ""
                    desc_lines.append(f"**{t.title}**{priority_str} - {assignee}{deadline_str}\n{thread_link}")
                embed.description = "\n".join(desc_lines)
            else:
                embed.description = "*No tasks*"
            
            msg = await target_channel.send(embed=embed)
            msg_ids.append(msg.id)

        await upsert_task_board(game, target_channel.id, json.dumps(msg_ids))
        await interaction.followup.send(f"Task board set up in {target_channel.mention}!")

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
        tasks = await get_tasks_by_assignee_multi(target.id)

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

    # ============== TASK DELETE ==============

    @task_group.command(name="delete", description="Delete a task by ID")
    @app_commands.describe(task_id="Task ID to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def task_delete(self, interaction: discord.Interaction, task_id: int):
        await interaction.response.defer(ephemeral=True)

        task = await get_task(task_id)
        if not task:
            await interaction.followup.send(f"Task #{task_id} not found.")
            return

        game_acronym = task.game_acronym

        # Delete thread if exists
        if task.thread_id:
            try:
                thread = interaction.guild.get_channel(task.thread_id)
                if thread and isinstance(thread, discord.Thread):
                    await thread.delete()
            except discord.HTTPException:
                pass

        # Delete header message if exists
        if task.header_message_id and task.target_channel_id:
            try:
                channel = interaction.guild.get_channel(task.target_channel_id)
                if channel:
                    msg = await channel.fetch_message(task.header_message_id)
                    await msg.delete()
            except discord.HTTPException:
                pass

        # Delete from database
        await delete_task(task_id)

        # Update dashboard
        await self.update_dashboard(game_acronym, self.bot)

        await interaction.followup.send(f"Task #{task_id} ({task.title}) deleted.")

    @task_group.command(name="close", description="Close/complete a task (run inside task thread or specify ID)")
    @app_commands.describe(task_id="Task ID (optional if running inside task thread)")
    async def task_close(self, interaction: discord.Interaction, task_id: int = None):
        await interaction.response.defer(ephemeral=True)

        if task_id is None:
            if isinstance(interaction.channel, discord.Thread):
                task = await get_task_by_thread_id(interaction.channel.id)
                if not task:
                    await interaction.followup.send("This thread is not a task thread. Provide task_id.")
                    return
            else:
                await interaction.followup.send("Run inside a task thread or provide task_id.")
                return
        else:
            task = await get_task(task_id)
            if not task:
                await interaction.followup.send(f"Task #{task_id} not found.")
                return

        if task.status in ('done', 'cancelled'):
            await interaction.followup.send("Task already completed or cancelled.")
            return

        is_assignee = await is_user_task_assignee(task.id, interaction.user.id)
        is_lead = interaction.user.guild_permissions.administrator or any(
            'lead' in r.name.lower() or 'admin' in r.name.lower()
            for r in interaction.user.roles
        )

        if not is_assignee and not is_lead:
            await interaction.followup.send("Only assignees or leads can close tasks.")
            return

        approval_status = await get_task_approval_status(task.id)

        if is_lead:
            pass
        elif approval_status['primary'] and approval_status['primary'].user_id == interaction.user.id:
            pass
        elif approval_status['primary']:
            await interaction.followup.send(
                f"Only the primary owner (<@{approval_status['primary'].user_id}>) can close this task."
            )
            return
        else:
            await set_task_assignee_approval(task.id, interaction.user.id, True)
            approval_status = await get_task_approval_status(task.id)

            config = await get_server_config(interaction.guild.id)
            approval_mode = 'auto'
            if config and config.config_json:
                try:
                    cfg = json.loads(config.config_json)
                    approval_mode = cfg.get('approval_mode', 'auto')
                except json.JSONDecodeError:
                    pass

            total = approval_status['total']
            approved = approval_status['approved']
            
            if approval_mode == 'any':
                required = 1
            elif approval_mode == 'all':
                required = total
            elif approval_mode == 'majority':
                required = (total // 2) + 1
            elif total == 2:
                required = 2
            else:
                required = (total // 2) + 1

            if approved < required:
                await interaction.followup.send(
                    f"Approval recorded! ({approved}/{required} needed to close)"
                )
                return

        old_status = task.status
        await update_task_status(task.id, 'done')
        await add_task_history(task.id, interaction.user.id, 'status_change', old_status, 'done')

        task.status = 'done'
        await self.update_control_panel(interaction, task)
        await self.update_header_message(interaction, task)
        await self.update_dashboard(task.game_acronym, self.bot)

        if task.thread_id:
            thread = interaction.guild.get_channel(task.thread_id)
            if thread and isinstance(thread, discord.Thread):
                try:
                    await thread.edit(archived=True, locked=True)
                except discord.HTTPException:
                    pass

        await interaction.followup.send(f"Task #{task.id} ({task.title}) closed!")

    @task_group.command(name="manage", description="List all tasks for a game with management options")
    @app_commands.describe(game="Game acronym")
    @app_commands.checks.has_permissions(administrator=True)
    async def task_manage(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer(ephemeral=True)

        game_obj = await get_game_by_acronym(game)
        if not game_obj:
            await interaction.followup.send(f"Game `{game}` not found.")
            return

        tasks = await get_tasks_by_game(game)

        if not tasks:
            await interaction.followup.send(f"No tasks for {game_obj.name}.")
            return

        # Create embed with all tasks
        embed = discord.Embed(
            title=f"Task Management: {game_obj.name}",
            description="Use `/task delete <id>` to remove a task.",
            color=discord.Color.blue()
        )

        # Group by status
        by_status = {}
        for t in tasks:
            if t.status not in by_status:
                by_status[t.status] = []
            by_status[t.status].append(t)

        for status in ['todo', 'progress', 'review', 'done', 'cancelled']:
            if status not in by_status:
                continue
            
            status_tasks = by_status[status]
            lines = []
            for t in status_tasks[:8]:
                assignee = f"<@{t.assignee_id}>"
                priority = f" [{t.priority}]" if t.priority else ""
                lines.append(f"`#{t.id}` **{t.title}**{priority} - {assignee}")
            
            if len(status_tasks) > 8:
                lines.append(f"*... and {len(status_tasks) - 8} more*")
            
            embed.add_field(
                name=f"{STATUS_EMOJI.get(status, '')} {STATUS_DISPLAY.get(status, status)} ({len(status_tasks)})",
                value="\n".join(lines) or "*None*",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @task_manage.autocomplete("game")
    async def task_manage_autocomplete(self, interaction: discord.Interaction, current: str):
        games = await get_all_games()
        return [
            app_commands.Choice(name=f"{g.acronym} - {g.name}", value=g.acronym)
            for g in games
            if current.lower() in g.acronym.lower() or current.lower() in g.name.lower()
        ][:25]

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
                # Handle double-encoded JSON (string containing JSON)
                if isinstance(tasks_data, str):
                    tasks_data = json.loads(tasks_data)
                # Validate it's a list
                if not isinstance(tasks_data, list):
                    await interaction.followup.send("JSON must be an array of task objects")
                    return
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
                control_embed = self.create_control_embed(task, member, game_name)
                view = TaskView(task.id, self)
                control_msg = await thread.send(embed=control_embed, view=view)

                # Update task with thread/message IDs
                await update_task_thread(task.id, thread.id, control_msg.id)
                await update_task_header_message(task.id, header_msg.id)
                
                # Add primary assignee to task_assignees table
                await add_task_assignee(task.id, assignee_id, is_primary=True)
                
                # Handle additional assignees if provided
                additional_ids = td.get('additional_assignees', [])
                if isinstance(additional_ids, str):
                    additional_ids = [x.strip() for x in additional_ids.split(',') if x.strip()]
                for add_id in additional_ids:
                    try:
                        add_member = interaction.guild.get_member(int(add_id))
                        if add_member:
                            await add_task_assignee(task.id, int(add_id), is_primary=False)
                    except (ValueError, TypeError):
                        pass
                
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

        due_soon = await get_tasks_due_soon(24)
        for task in due_soon:
            if task.thread_id:
                thread = guild.get_channel(task.thread_id)
                if thread:
                    try:
                        assignees = await get_task_assignees(task.id)
                        mentions = ' '.join(f"<@{a.user_id}>" for a in assignees) if assignees else f"<@{task.assignee_id}>"
                        await thread.send(f"\u26a0\ufe0f {mentions} This task is due within 24 hours!")
                    except discord.HTTPException:
                        pass

        stagnant = await get_stagnant_tasks(3)
        for task in stagnant:
            if task.thread_id:
                thread = guild.get_channel(task.thread_id)
                if thread:
                    try:
                        assignees = await get_task_assignees(task.id)
                        mentions = ' '.join(f"<@{a.user_id}>" for a in assignees) if assignees else f"<@{task.assignee_id}>"
                        await thread.send(f"\U0001f4ac {mentions} Update request: How is this task going?")
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

        task = await get_task_by_thread_id(message.channel.id)
        if not task:
            return

        is_assignee = await is_user_task_assignee(task.id, message.author.id)
        is_lead = message.author.guild_permissions.administrator
        
        if not is_lead:
            lead_roles = [r for r in message.author.roles if 'lead' in r.name.lower() or 'admin' in r.name.lower()]
            is_lead = len(lead_roles) > 0

        if not is_assignee and not is_lead:
            try:
                await message.reply(
                    "Only the assignee and leads can discuss in this task thread.",
                    delete_after=10
                )
                await message.delete()
            except discord.HTTPException:
                pass

    @task_new.autocomplete("game")
    @task_board.autocomplete("game")
    @task_setup.autocomplete("game")
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
