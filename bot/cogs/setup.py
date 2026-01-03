import discord
from discord import app_commands
from discord.ext import commands
import json
from typing import Optional

from ..database import (
    get_server_config,
    upsert_server_config,
    get_all_template_channels,
    upsert_template_channel,
    get_all_groups,
    migrate_tasks_to_multi_assignee,
    get_all_tasks,
    get_task_assignees,
)


DEFAULT_CONFIG = {
    'channel_mode': 'per_game',
    'board_channel_template': 'tasks',
    'questions_channel_template': 'questions',
    'leads_channel_template': 'leads',
    'global_board_channel_id': None,
    'global_questions_channel_id': None,
    'global_leads_channel_id': None,
    'lead_role_ids': [],
    'approval_mode': 'auto',
    'approval_threshold': None,
}


class ChannelModeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Per-Game Channels (Recommended)",
                value="per_game",
                description="Each game gets its own board, questions, leads channels",
                emoji="\U0001f3ae"
            ),
            discord.SelectOption(
                label="Global Channels",
                value="global",
                description="One set of channels shared across all games",
                emoji="\U0001f310"
            ),
        ]
        super().__init__(placeholder="Select channel mode...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.config['channel_mode'] = self.values[0]
        await self.view.advance_step(interaction)


class TemplateChannelSelect(discord.ui.Select):
    def __init__(self, template_channels: list, config_key: str, label: str):
        self.config_key = config_key
        options = [
            discord.SelectOption(
                label=f"{ch.name} ({ch.group_name})",
                value=ch.name,
                description=ch.description[:50] if ch.description else None
            )
            for ch in template_channels[:25]
        ]
        options.append(discord.SelectOption(
            label="Create New Channel",
            value="__create_new__",
            description="Add a new channel to the template",
            emoji="\u2795"
        ))
        super().__init__(placeholder=f"Select {label} channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "__create_new__":
            modal = CreateChannelModal(self.config_key, self.view)
            await interaction.response.send_modal(modal)
        else:
            self.view.config[self.config_key] = self.values[0]
            await self.view.advance_step(interaction)


class GlobalChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, config_key: str, label: str):
        self.config_key = config_key
        super().__init__(
            placeholder=f"Select {label} channel...",
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.config[self.config_key] = self.values[0].id
        await self.view.advance_step(interaction)


class CreateChannelModal(discord.ui.Modal, title='Create New Template Channel'):
    channel_name = discord.ui.TextInput(
        label='Channel Name',
        placeholder='e.g., tasks-board',
        required=True,
        max_length=50
    )
    channel_group = discord.ui.TextInput(
        label='Group',
        placeholder='e.g., general, code, design',
        required=True,
        max_length=20
    )
    channel_description = discord.ui.TextInput(
        label='Description',
        placeholder='What is this channel for?',
        required=False,
        max_length=100
    )

    def __init__(self, config_key: str, view: 'SetupWizardView'):
        super().__init__()
        self.config_key = config_key
        self.wizard_view = view

    async def on_submit(self, interaction: discord.Interaction):
        name = str(self.channel_name).lower().replace(' ', '-')
        group = str(self.channel_group).lower()
        description = str(self.channel_description) if self.channel_description else None
        await upsert_template_channel(name, group, False, description)
        self.wizard_view.config[self.config_key] = name
        await self.wizard_view.advance_step(interaction)


class LeadRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select lead role(s)...", min_values=1, max_values=5)

    async def callback(self, interaction: discord.Interaction):
        self.view.config['lead_role_ids'] = [r.id for r in self.values]
        await self.view.advance_step(interaction)


class ApprovalModeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Auto (Recommended)", value="auto", description="2 people = all approve, 3+ = majority", emoji="\u2699\ufe0f"),
            discord.SelectOption(label="All Must Approve", value="all", description="Every team member must approve", emoji="\u2705"),
            discord.SelectOption(label="Majority Approval", value="majority", description="50%+ of team must approve", emoji="\U0001f4ca"),
            discord.SelectOption(label="Any Can Close", value="any", description="Any team member can close the task", emoji="\u26a1"),
        ]
        super().__init__(placeholder="Select approval mode...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.config['approval_mode'] = self.values[0]
        await self.view.advance_step(interaction)


class SetupLandingView(discord.ui.View):
    def __init__(self, guild_id: int, existing_config: dict = None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.existing_config = existing_config

    @discord.ui.button(label="Quick Setup", style=discord.ButtonStyle.success, emoji="⚡")
    async def quick_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild

        category = discord.utils.get(guild.categories, name="Tasks")
        if not category:
            category = await guild.create_category("Tasks")

        board_channel = discord.utils.get(category.text_channels, name="task-board")
        if not board_channel:
            board_channel = await category.create_text_channel("task-board", topic="Task management dashboard")

        questions_channel = discord.utils.get(category.text_channels, name="task-questions")
        if not questions_channel:
            questions_channel = await category.create_text_channel("task-questions", topic="Questions about tasks")

        leads_channel = discord.utils.get(category.text_channels, name="task-leads")
        if not leads_channel:
            leads_channel = await category.create_text_channel("task-leads", topic="Lead notifications")

        config = self.existing_config.copy() if self.existing_config else DEFAULT_CONFIG.copy()
        config['channel_mode'] = 'global'
        config['global_board_channel_id'] = board_channel.id
        config['global_questions_channel_id'] = questions_channel.id
        config['global_leads_channel_id'] = leads_channel.id

        embed = discord.Embed(
            title="⚡ Channels Created!",
            description=(
                f"Created task channels in **{category.name}** category:\n\n"
                f"• {board_channel.mention} - task dashboard\n"
                f"• {questions_channel.mention} - task questions\n"
                f"• {leads_channel.mention} - lead notifications\n\n"
                "Now let's configure lead roles and approval settings..."
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        view = SetupWizardView(self.guild_id, config)
        view.step = 4
        await view.start_from_step(interaction)
        self.stop()

    @discord.ui.button(label="Custom Setup", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def custom_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = SetupWizardView(self.guild_id, self.existing_config)
        await view.start(interaction)
        self.stop()


class SetupWizardView(discord.ui.View):
    def __init__(self, guild_id: int, existing_config: dict = None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = existing_config.copy() if existing_config else DEFAULT_CONFIG.copy()
        self.step = 0
        self.message: Optional[discord.Message] = None
        self.template_channels = []

    async def start(self, interaction: discord.Interaction):
        self.template_channels = await get_all_template_channels()
        await self.show_step(interaction)

    async def start_from_step(self, interaction: discord.Interaction):
        self.template_channels = await get_all_template_channels()
        await self.show_step_followup(interaction)

    async def show_step(self, interaction: discord.Interaction):
        self.clear_items()

        if self.step == 0:
            embed = discord.Embed(
                title="\U0001f527 Task System Setup - Step 1/4",
                description=(
                    "**Channel Mode**\n\n"
                    "How should task channels be organized?\n\n"
                    "\U0001f3ae **Per-Game** (Recommended): Each game gets its own task board, "
                    "questions, and leads channels.\n\n"
                    "\U0001f310 **Global**: One set of channels shared across all games."
                ),
                color=discord.Color.blue()
            )
            self.add_item(ChannelModeSelect())

        elif self.step == 1:
            if self.config['channel_mode'] == 'per_game':
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 2/4",
                    description="**Task Board Channel**\n\nSelect which template channel will be used for task boards.",
                    color=discord.Color.blue()
                )
                self.add_item(TemplateChannelSelect(self.template_channels, 'board_channel_template', 'task board'))
            else:
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 2/4",
                    description="**Task Board Channel**\n\nSelect the channel where task boards will be displayed.",
                    color=discord.Color.blue()
                )
                self.add_item(GlobalChannelSelect('global_board_channel_id', 'task board'))

        elif self.step == 2:
            if self.config['channel_mode'] == 'per_game':
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 3/4",
                    description="**Questions Channel**\n\nSelect template channel for questions.",
                    color=discord.Color.blue()
                )
                self.add_item(TemplateChannelSelect(self.template_channels, 'questions_channel_template', 'questions'))
            else:
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 3/4",
                    description="**Questions Channel**\n\nSelect the channel for task-related questions.",
                    color=discord.Color.blue()
                )
                self.add_item(GlobalChannelSelect('global_questions_channel_id', 'questions'))

        elif self.step == 3:
            if self.config['channel_mode'] == 'per_game':
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 3/4 (continued)",
                    description="**Leads Channel**\n\nSelect template channel for lead notifications.",
                    color=discord.Color.blue()
                )
                self.add_item(TemplateChannelSelect(self.template_channels, 'leads_channel_template', 'leads'))
            else:
                embed = discord.Embed(
                    title="\U0001f527 Task System Setup - Step 3/4 (continued)",
                    description="**Leads Channel**\n\nSelect the channel where leads receive notifications.",
                    color=discord.Color.blue()
                )
                self.add_item(GlobalChannelSelect('global_leads_channel_id', 'leads'))

        elif self.step == 4:
            embed = discord.Embed(
                title="\U0001f527 Task System Setup - Step 4/4",
                description="**Lead Roles**\n\nSelect role(s) that should be considered 'Leads'.",
                color=discord.Color.blue()
            )
            self.add_item(LeadRoleSelect())

        elif self.step == 5:
            embed = discord.Embed(
                title="\U0001f527 Task System Setup - Step 5/5",
                description="**Task Approval Mode**\n\nWhen a task has multiple assignees, how should completion approval work?",
                color=discord.Color.blue()
            )
            self.add_item(ApprovalModeSelect())

        elif self.step == 6:
            embed = self._create_summary_embed()
            confirm_btn = discord.ui.Button(label="Confirm Setup", style=discord.ButtonStyle.success, emoji="\u2705")
            confirm_btn.callback = self.confirm_setup
            self.add_item(confirm_btn)
            back_btn = discord.ui.Button(label="Start Over", style=discord.ButtonStyle.secondary, emoji="\u21a9\ufe0f")
            back_btn.callback = self.restart_setup
            self.add_item(back_btn)

        if self.message:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
            self.message = await interaction.original_response()

    def _create_summary_embed(self) -> discord.Embed:
        embed = discord.Embed(title="\U0001f527 Task System Setup - Summary", description="Review your configuration.", color=discord.Color.green())
        mode = "Per-Game" if self.config['channel_mode'] == 'per_game' else "Global"
        embed.add_field(name="Channel Mode", value=mode, inline=True)

        if self.config['channel_mode'] == 'per_game':
            embed.add_field(name="Board Template", value=f"`{self.config['board_channel_template']}`", inline=True)
            embed.add_field(name="Questions Template", value=f"`{self.config['questions_channel_template']}`", inline=True)
            embed.add_field(name="Leads Template", value=f"`{self.config['leads_channel_template']}`", inline=True)
        else:
            embed.add_field(name="Board Channel", value=f"<#{self.config['global_board_channel_id']}>", inline=True)
            embed.add_field(name="Questions Channel", value=f"<#{self.config['global_questions_channel_id']}>", inline=True)
            embed.add_field(name="Leads Channel", value=f"<#{self.config['global_leads_channel_id']}>", inline=True)

        lead_mentions = ' '.join(f"<@&{rid}>" for rid in self.config['lead_role_ids'])
        embed.add_field(name="Lead Roles", value=lead_mentions or "None", inline=True)

        approval_modes = {'auto': "Auto", 'all': "All Must Approve", 'majority': "Majority", 'any': "Any Can Close"}
        embed.add_field(name="Approval Mode", value=approval_modes.get(self.config['approval_mode'], self.config['approval_mode']), inline=True)
        return embed

    async def advance_step(self, interaction: discord.Interaction):
        self.step += 1
        self.template_channels = await get_all_template_channels()
        await self.show_step(interaction)

    async def show_step_followup(self, interaction: discord.Interaction):
        self.clear_items()
        embed = self._get_step_embed()
        self.message = await interaction.followup.send(embed=embed, view=self, ephemeral=True, wait=True)

    def _get_step_embed(self) -> discord.Embed:
        if self.step == 4:
            embed = discord.Embed(
                title="🔧 Task System Setup - Lead Roles",
                description="**Lead Roles**\n\nSelect role(s) that should be considered 'Leads'.",
                color=discord.Color.blue()
            )
            self.add_item(LeadRoleSelect())
        elif self.step == 5:
            embed = discord.Embed(
                title="🔧 Task System Setup - Approval Mode",
                description="**Task Approval Mode**\n\nWhen a task has multiple assignees, how should completion approval work?",
                color=discord.Color.blue()
            )
            self.add_item(ApprovalModeSelect())
        elif self.step == 6:
            embed = self._create_summary_embed()
            confirm_btn = discord.ui.Button(label="Confirm Setup", style=discord.ButtonStyle.success, emoji="✅")
            confirm_btn.callback = self.confirm_setup
            self.add_item(confirm_btn)
            back_btn = discord.ui.Button(label="Start Over", style=discord.ButtonStyle.secondary, emoji="↩️")
            back_btn.callback = self.restart_setup
            self.add_item(back_btn)
        else:
            embed = discord.Embed(title="Setup", color=discord.Color.blue())
        return embed

    async def confirm_setup(self, interaction: discord.Interaction):
        config_json = json.dumps(self.config)
        await upsert_server_config(self.guild_id, config_json, setup_completed=True)
        embed = discord.Embed(
            title="\u2705 Setup Complete!",
            description="The task system has been configured.\n\nUse `/task new` to create tasks, `/task board` to view boards.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def restart_setup(self, interaction: discord.Interaction):
        self.step = 0
        self.config = DEFAULT_CONFIG.copy()
        await self.show_step(interaction)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Server administration and setup")

    @admin_group.command(name="setup", description="Configure the task management system")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_setup(self, interaction: discord.Interaction):
        existing = await get_server_config(interaction.guild.id)
        existing_config = None
        if existing and existing.config_json:
            try:
                existing_config = json.loads(existing.config_json)
            except json.JSONDecodeError:
                pass

        embed = discord.Embed(
            title="🔧 Task System Setup",
            description=(
                "**⚡ Quick Setup**\n"
                "Auto-creates a `Tasks` category with pre-configured channels "
                "(task-board, task-questions, task-leads). Best for getting started fast.\n\n"
                "**⚙️ Custom Setup**\n"
                "Step-by-step wizard to configure channel mode, lead roles, "
                "approval rules, and use existing channels."
            ),
            color=discord.Color.blue()
        )

        view = SetupLandingView(interaction.guild.id, existing_config)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin_group.command(name="status", description="Show current setup configuration")
    async def admin_status(self, interaction: discord.Interaction):
        config = await get_server_config(interaction.guild.id)

        if not config or not config.setup_completed:
            embed = discord.Embed(
                title="\u26a0\ufe0f Setup Not Completed",
                description="Run `/admin setup` to configure the task system.",
                color=discord.Color.yellow()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            cfg = json.loads(config.config_json)
        except json.JSONDecodeError:
            cfg = DEFAULT_CONFIG

        embed = discord.Embed(title="\u2699\ufe0f Server Configuration", color=discord.Color.blue())
        mode = "Per-Game" if cfg.get('channel_mode') == 'per_game' else "Global"
        embed.add_field(name="Channel Mode", value=mode, inline=True)

        if cfg.get('channel_mode') == 'per_game':
            embed.add_field(
                name="Templates",
                value=f"Board: `{cfg.get('board_channel_template', 'tasks')}`\nQuestions: `{cfg.get('questions_channel_template', 'questions')}`\nLeads: `{cfg.get('leads_channel_template', 'leads')}`",
                inline=True
            )
        else:
            embed.add_field(
                name="Channels",
                value=f"Board: <#{cfg.get('global_board_channel_id')}>\nQuestions: <#{cfg.get('global_questions_channel_id')}>\nLeads: <#{cfg.get('global_leads_channel_id')}>",
                inline=True
            )

        lead_ids = cfg.get('lead_role_ids', [])
        lead_mentions = ' '.join(f"<@&{rid}>" for rid in lead_ids) if lead_ids else "Not set"
        embed.add_field(name="Lead Roles", value=lead_mentions, inline=False)

        approval_modes = {'auto': "Auto", 'all': "All Must Approve", 'majority': "Majority", 'any': "Any Can Close"}
        embed.add_field(name="Approval Mode", value=approval_modes.get(cfg.get('approval_mode', 'auto'), 'Auto'), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="migrate", description="Migrate existing tasks to multi-assignee system")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_migrate(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats = await migrate_tasks_to_multi_assignee()

        if stats["total"] == 0:
            embed = discord.Embed(title="\U0001f4ed No Tasks Found", description="No existing tasks to migrate.", color=discord.Color.yellow())
        elif stats["migrated"] == 0:
            embed = discord.Embed(title="\u2705 Already Migrated", description=f"All {stats['total']} tasks already migrated.", color=discord.Color.green())
        else:
            embed = discord.Embed(
                title="\u2705 Migration Complete",
                description=f"**Migrated:** {stats['migrated']} tasks\n**Skipped:** {stats['skipped']} tasks\n**Total:** {stats['total']} tasks",
                color=discord.Color.green()
            )
        await interaction.followup.send(embed=embed)

    @admin_group.command(name="channels", description="List channels with their IDs (for imports)")
    @app_commands.describe(category_id="Optional category ID to filter")
    async def admin_channels(self, interaction: discord.Interaction, category_id: str = None):
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

        lines = []
        for ch in sorted(channels, key=lambda c: c.name):
            if isinstance(ch, discord.CategoryChannel):
                lines.append(f"**[Category]** {ch.name} | `{ch.id}`")
            elif isinstance(ch, discord.TextChannel):
                lines.append(f"# {ch.name} | `{ch.id}`")
            elif isinstance(ch, discord.VoiceChannel):
                lines.append(f"vc {ch.name} | `{ch.id}`")

        output = "\n".join(lines[:50])
        if len(lines) > 50:
            output += f"\n... and {len(lines) - 50} more"

        embed = discord.Embed(title="Channels", description=output, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="members", description="List members with their IDs (for imports)")
    @app_commands.describe(role="Optional role to filter by")
    async def admin_members(self, interaction: discord.Interaction, role: discord.Role = None):
        guild = interaction.guild

        if role:
            members = role.members
        else:
            members = [m for m in guild.members if not m.bot]

        lines = [f"{m.display_name} | `{m.id}`" for m in members[:50]]
        if len(members) > 50:
            lines.append(f"... and {len(members) - 50} more")

        embed = discord.Embed(
            title=f"Members{f' with {role.name}' if role else ''}",
            description="\n".join(lines) or "No members",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
