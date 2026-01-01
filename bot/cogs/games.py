import discord
from discord import app_commands
from discord.ext import commands
import random

from ..config import MEMBER_ROLES

# Predefined colors for game roles (vibrant, distinguishable)
ROLE_COLORS = [
    0xe74c3c,  # red
    0xe67e22,  # orange
    0xf1c40f,  # yellow
    0x2ecc71,  # green
    0x1abc9c,  # teal
    0x3498db,  # blue
    0x9b59b6,  # purple
    0xe91e63,  # pink
    0x00bcd4,  # cyan
    0x8bc34a,  # lime
    0xff5722,  # deep orange
    0x673ab7,  # deep purple
]
from ..database import (
    get_all_games,
    get_game_by_acronym,
    get_all_acronyms,
    create_game,
    delete_game,
    get_all_template_channels,
    get_groups_dict,
    add_game_channel,
    remove_game_channel as db_remove_game_channel,
    get_game_channels,
    get_game_channel_by_name,
    add_game_role,
    get_game_roles,
    get_all_groups,
    get_group,
)
from ..utils import (
    generate_acronym,
    resolve_acronym_conflict,
    format_channel_name,
    format_role_name,
)


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    game_group = app_commands.Group(name="game", description="Manage games")
    assign_group = app_commands.Group(name="assign", description="Assign member roles")
    
    # ============== ASSIGN COMMANDS ==============
    
    @assign_group.command(name="add", description="Assign a member role to a user")
    @app_commands.describe(
        user="User to assign the role to",
        role="Member role to assign"
    )
    @app_commands.choices(role=[
        app_commands.Choice(name="Coder", value="Coder"),
        app_commands.Choice(name="Artist", value="Artist"),
        app_commands.Choice(name="Audio", value="Audio"),
        app_commands.Choice(name="Writer", value="Writer"),
        app_commands.Choice(name="QA", value="QA"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def assign_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: str
    ):
        guild = interaction.guild
        
        # Find or create the member role
        discord_role = discord.utils.get(guild.roles, name=role)
        if not discord_role:
            # Create the role if it doesn't exist
            discord_role = await guild.create_role(
                name=role,
                reason=f"Member role created by /assign"
            )
        
        if discord_role in user.roles:
            await interaction.response.send_message(
                f"{user.mention} already has the {role} role."
            )
            return
        
        try:
            await user.add_roles(discord_role, reason=f"Assigned by {interaction.user}")
            await interaction.response.send_message(
                f"Assigned **{role}** to {user.mention}. Game roles will sync automatically."
            )
            # Sync game roles for this user
            await self.bot.sync_member_game_roles(user)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Missing permissions to assign roles."
            )
    
    @assign_group.command(name="remove", description="Remove a member role from a user")
    @app_commands.describe(
        user="User to remove the role from",
        role="Member role to remove"
    )
    @app_commands.choices(role=[
        app_commands.Choice(name="Coder", value="Coder"),
        app_commands.Choice(name="Artist", value="Artist"),
        app_commands.Choice(name="Audio", value="Audio"),
        app_commands.Choice(name="Writer", value="Writer"),
        app_commands.Choice(name="QA", value="QA"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def assign_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: str
    ):
        guild = interaction.guild
        discord_role = discord.utils.get(guild.roles, name=role)
        
        if not discord_role or discord_role not in user.roles:
            await interaction.response.send_message(
                f"{user.mention} doesn't have the {role} role."
            )
            return
        
        try:
            await user.remove_roles(discord_role, reason=f"Removed by {interaction.user}")
            await interaction.response.send_message(
                f"Removed **{role}** from {user.mention}. Game roles will sync automatically."
            )
            # Sync game roles for this user
            await self.bot.sync_member_game_roles(user)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Missing permissions to remove roles."
            )
    
    @assign_group.command(name="list", description="List all users with member roles")
    @app_commands.checks.has_permissions(administrator=True)
    async def assign_list(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        embed = discord.Embed(title="Member Roles", color=discord.Color.blue())
        
        for role_name in MEMBER_ROLES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                members = [m.mention for m in role.members if not m.bot]
                value = ", ".join(members) if members else "No members"
            else:
                value = "Role not created"
            
            embed.add_field(name=role_name, value=value, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    # ============== NEWGAME ==============
    
    @app_commands.command(name="newgame", description="Create a new game with channels and roles")
    @app_commands.describe(
        name="Game name (e.g., 'Steal a Brainrot')",
        acronym="Custom acronym (optional, auto-generated if not provided)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def newgame(
        self,
        interaction: discord.Interaction,
        name: str,
        acronym: str = None
    ):
        await interaction.response.defer()
        
        guild = interaction.guild
        
        # Generate or validate acronym
        existing_acronyms = await get_all_acronyms()
        
        if acronym:
            # User provided custom acronym
            if acronym.lower() in {a.lower() for a in existing_acronyms}:
                acronym = resolve_acronym_conflict(acronym, existing_acronyms)
                await interaction.followup.send(
                    f"Acronym already exists, using `{acronym}` instead."
                )
        else:
            # Auto-generate
            base_acronym = generate_acronym(name)
            acronym = resolve_acronym_conflict(base_acronym, existing_acronyms)
        
        # Get template and groups
        template_channels = await get_all_template_channels()
        groups = await get_groups_dict()
        
        try:
            # Create category
            category = await guild.create_category(name=name)
            
            # Save game to DB
            game = await create_game(name, acronym, category.id)
            
            # Pick a random color for this game's roles
            role_color = discord.Color(random.choice(ROLE_COLORS))
            
            # Create roles with the same color
            created_roles = []
            for role_name in MEMBER_ROLES:
                game_role_name = format_role_name(acronym, role_name)
                role = await guild.create_role(
                    name=game_role_name,
                    color=role_color,
                    reason=f"Game: {name}"
                )
                await add_game_role(game.id, role.id, role_name)
                created_roles.append(role)
            
            # Create channels from template
            for template_ch in template_channels:
                emoji = groups.get(template_ch.group_name, "")
                channel_name = format_channel_name(emoji, acronym, template_ch.name)
                
                if template_ch.is_voice:
                    channel = await category.create_voice_channel(name=channel_name)
                else:
                    channel = await category.create_text_channel(
                        name=channel_name,
                        topic=template_ch.description
                    )
                
                await add_game_channel(
                    game_id=game.id,
                    channel_id=channel.id,
                    name=template_ch.name,
                    group_name=template_ch.group_name,
                    is_custom=False,
                    is_voice=template_ch.is_voice
                )
            
            # Sync roles to members
            await self.bot.sync_all_game_roles()
            
            # Summary
            embed = discord.Embed(
                title=f"Created: {name}",
                description=f"Acronym: `{acronym}`",
                color=role_color
            )
            embed.add_field(
                name="Category",
                value=category.mention,
                inline=True
            )
            embed.add_field(
                name="Channels",
                value=str(len(template_channels)),
                inline=True
            )
            embed.add_field(
                name="Roles",
                value=", ".join(r.mention for r in created_roles),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except discord.HTTPException as e:
            await interaction.followup.send(f"Error creating game: {e}")
    
    # ============== DELETEGAME ==============
    
    @app_commands.command(name="deletegame", description="Delete a game and all its channels/roles")
    @app_commands.describe(acronym="Game acronym to delete")
    @app_commands.checks.has_permissions(administrator=True)
    async def deletegame(self, interaction: discord.Interaction, acronym: str):
        await interaction.response.defer()
        
        game = await get_game_by_acronym(acronym)
        if not game:
            await interaction.followup.send(f"Game `{acronym}` not found.")
            return
        
        guild = interaction.guild
        errors = []
        
        # Delete channels
        game_channels = await get_game_channels(game.id)
        for game_ch in game_channels:
            channel = guild.get_channel(game_ch.channel_id)
            if channel:
                try:
                    await channel.delete(reason=f"Deleting game: {game.name}")
                except discord.HTTPException as e:
                    errors.append(f"Channel {game_ch.name}: {e}")
        
        # Delete category
        category = guild.get_channel(game.category_id)
        if category:
            try:
                await category.delete(reason=f"Deleting game: {game.name}")
            except discord.HTTPException as e:
                errors.append(f"Category: {e}")
        
        # Delete roles
        game_roles = await get_game_roles(game.id)
        for game_role in game_roles:
            role = guild.get_role(game_role.role_id)
            if role:
                try:
                    await role.delete(reason=f"Deleting game: {game.name}")
                except discord.HTTPException as e:
                    errors.append(f"Role {game_role.suffix}: {e}")
        
        # Delete from DB (cascades to game_channels and game_roles)
        await delete_game(game.id)
        
        result = f"Deleted game `{game.name}` ({acronym})."
        if errors:
            result += f"\n\nErrors:\n" + "\n".join(errors)
        
        await interaction.followup.send(result)
    
    # ============== GAME LIST ==============
    
    @game_group.command(name="list", description="List all games")
    @app_commands.checks.has_permissions(administrator=True)
    async def game_list(self, interaction: discord.Interaction):
        games = await get_all_games()
        
        if not games:
            await interaction.response.send_message("No games created yet.")
            return
        
        embed = discord.Embed(title="Games", color=discord.Color.blue())
        
        for game in games:
            category = interaction.guild.get_channel(game.category_id)
            category_status = category.mention if category else "(category deleted)"
            
            embed.add_field(
                name=f"{game.acronym} - {game.name}",
                value=category_status,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    # ============== GAME ADDCHANNEL ==============
    
    @game_group.command(name="addchannel", description="Add a custom channel to a game")
    @app_commands.describe(
        acronym="Game acronym",
        name="Channel name",
        group="Group for emoji prefix",
        is_voice="Is this a voice channel?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def game_addchannel(
        self,
        interaction: discord.Interaction,
        acronym: str,
        name: str,
        group: str,
        is_voice: bool = False
    ):
        game = await get_game_by_acronym(acronym)
        if not game:
            await interaction.response.send_message(f"Game `{acronym}` not found.")
            return
        
        # Validate group
        group_obj = await get_group(group)
        if not group_obj:
            groups = await get_all_groups()
            group_names = ", ".join(g.name for g in groups)
            await interaction.response.send_message(
                f"Group `{group}` not found. Available: {group_names}"
            )
            return
        
        # Normalize name
        name = name.lower().replace(" ", "-")
        
        # Check if already exists
        existing = await get_game_channel_by_name(game.id, name)
        if existing:
            await interaction.response.send_message(
                f"Channel `{name}` already exists in this game."
            )
            return
        
        await interaction.response.defer()
        
        groups = await get_groups_dict()
        emoji = groups.get(group, "")
        channel_name = format_channel_name(emoji, game.acronym, name)
        
        category = interaction.guild.get_channel(game.category_id)
        if not category:
            await interaction.followup.send("Game category not found.")
            return
        
        try:
            if is_voice:
                channel = await category.create_voice_channel(name=channel_name)
            else:
                channel = await category.create_text_channel(name=channel_name)
            
            await add_game_channel(
                game_id=game.id,
                channel_id=channel.id,
                name=name,
                group_name=group,
                is_custom=True,
                is_voice=is_voice
            )
            
            await interaction.followup.send(
                f"Created custom channel: {channel.mention}"
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"Error: {e}")
    
    # ============== GAME REMOVECHANNEL ==============
    
    @game_group.command(name="removechannel", description="Remove a channel from a game")
    @app_commands.describe(
        acronym="Game acronym",
        name="Channel name to remove"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def game_removechannel(
        self,
        interaction: discord.Interaction,
        acronym: str,
        name: str
    ):
        game = await get_game_by_acronym(acronym)
        if not game:
            await interaction.response.send_message(f"Game `{acronym}` not found.")
            return
        
        name = name.lower().replace(" ", "-")
        
        channel_id = await db_remove_game_channel(game.id, name)
        if not channel_id:
            await interaction.response.send_message(
                f"Channel `{name}` not found in this game."
            )
            return
        
        # Delete Discord channel
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            try:
                await channel.delete(reason=f"Removed from game: {game.name}")
                await interaction.response.send_message(
                    f"Removed channel `{name}` from {game.name}."
                )
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    f"Removed from DB but failed to delete channel: {e}"
                )
        else:
            await interaction.response.send_message(
                f"Removed `{name}` from DB (channel already deleted)."
            )
    
    # ============== AUTOCOMPLETE ==============
    
    @deletegame.autocomplete("acronym")
    @game_addchannel.autocomplete("acronym")
    @game_removechannel.autocomplete("acronym")
    async def acronym_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):
        games = await get_all_games()
        return [
            app_commands.Choice(name=f"{g.acronym} - {g.name}", value=g.acronym)
            for g in games
            if current.lower() in g.acronym.lower() or current.lower() in g.name.lower()
        ][:25]
    
    @game_addchannel.autocomplete("group")
    async def group_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):
        groups = await get_all_groups()
        return [
            app_commands.Choice(name=f"{g.emoji} {g.name}", value=g.name)
            for g in groups
            if current.lower() in g.name.lower()
        ][:25]
    
    @game_removechannel.autocomplete("name")
    async def channel_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ):
        # Get acronym from other parameter
        acronym = interaction.namespace.acronym
        if not acronym:
            return []
        
        game = await get_game_by_acronym(acronym)
        if not game:
            return []
        
        channels = await get_game_channels(game.id)
        return [
            app_commands.Choice(name=ch.name, value=ch.name)
            for ch in channels
            if current.lower() in ch.name.lower()
        ][:25]
    
    # ============== FUN COMMANDS ==============
    
    @app_commands.command(name="thuglife", description="Thug life")
    async def thuglife(self, interaction: discord.Interaction):
        await interaction.response.send_message("https://tenor.com/view/thug-life-gif-25350966")


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
