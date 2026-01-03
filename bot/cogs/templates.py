import discord
from discord import app_commands
from discord.ext import commands
import json
import io

from ..database import (
    get_all_template_channels,
    add_template_channel,
    remove_template_channel,
    get_template_channel,
    get_all_groups,
    get_group,
    update_group_emoji,
    upsert_group,
    get_all_games,
    get_game_channels,
    get_non_custom_game_channels,
    add_game_channel,
    remove_game_channel as db_remove_game_channel,
    get_groups_dict,
    clear_template_channels,
    upsert_template_channel,
)
from ..utils import format_channel_name


class TemplatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    template_group = app_commands.Group(name="template", description="Manage channel templates and groups")
    
    @template_group.command(name="list", description="List all template channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_list(self, interaction: discord.Interaction):
        channels = await get_all_template_channels()
        groups = await get_groups_dict()
        
        if not channels:
            await interaction.response.send_message("No template channels configured.")
            return
        
        by_group = {}
        for ch in channels:
            if ch.group_name not in by_group:
                by_group[ch.group_name] = []
            by_group[ch.group_name].append(ch)
        
        embed = discord.Embed(title="Channel Template", color=discord.Color.blue())
        
        for group_name, group_channels in by_group.items():
            emoji = groups.get(group_name, "")
            channel_list = "\n".join(
                f"{'(VC) ' if ch.is_voice else ''}{ch.name}" 
                for ch in group_channels
            )
            embed.add_field(
                name=f"{emoji} {group_name}",
                value=f"```\n{channel_list}\n```",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @template_group.command(name="add", description="Add a channel to the template")
    @app_commands.describe(
        name="Channel name (e.g., code-debugging)",
        group="Group name (e.g., code, design, audio)",
        description="Channel description/topic",
        is_voice="Is this a voice channel?"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def template_add(
        self,
        interaction: discord.Interaction,
        name: str,
        group: str,
        description: str = None,
        is_voice: bool = False
    ):
        group_obj = await get_group(group)
        if not group_obj:
            groups = await get_all_groups()
            group_names = ", ".join(g.name for g in groups)
            await interaction.response.send_message(f"Group `{group}` not found. Available: {group_names}")
            return
        
        name = name.lower().replace(" ", "-")
        success = await add_template_channel(name, group, is_voice, description)
        if success:
            await interaction.response.send_message(f"Added `{name}` to template in group `{group}`.")
        else:
            await interaction.response.send_message(f"Channel `{name}` already exists in template.")
    
    @template_group.command(name="remove", description="Remove a channel from the template")
    @app_commands.describe(name="Channel name to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_remove(self, interaction: discord.Interaction, name: str):
        name = name.lower().replace(" ", "-")
        success = await remove_template_channel(name)
        if success:
            await interaction.response.send_message(f"Removed `{name}` from template.")
        else:
            await interaction.response.send_message(f"Channel `{name}` not found in template.")
    
    @template_group.command(name="sync", description="Sync template to all existing games")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        games = await get_all_games()
        if not games:
            await interaction.followup.send("No games to sync.")
            return
        
        template_channels = await get_all_template_channels()
        template_names = {ch.name for ch in template_channels}
        groups = await get_groups_dict()
        
        added_count = 0
        removed_count = 0
        errors = []
        
        for game in games:
            category = interaction.guild.get_channel(game.category_id)
            if not category:
                errors.append(f"Category not found for {game.name}")
                continue
            
            game_channels = await get_non_custom_game_channels(game.id)
            game_channel_names = {ch.name for ch in game_channels}
            
            for template_ch in template_channels:
                if template_ch.name not in game_channel_names:
                    emoji = groups.get(template_ch.group_name, "")
                    channel_name = format_channel_name(emoji, game.acronym, template_ch.name)
                    
                    try:
                        if template_ch.is_voice:
                            new_channel = await category.create_voice_channel(name=channel_name)
                        else:
                            new_channel = await category.create_text_channel(
                                name=channel_name,
                                topic=template_ch.description
                            )
                        
                        await add_game_channel(
                            game_id=game.id,
                            channel_id=new_channel.id,
                            name=template_ch.name,
                            group_name=template_ch.group_name,
                            is_custom=False,
                            is_voice=template_ch.is_voice
                        )
                        added_count += 1
                    except discord.HTTPException as e:
                        errors.append(f"Failed to create {channel_name}: {e}")
            
            for game_ch in game_channels:
                if game_ch.name not in template_names:
                    channel = interaction.guild.get_channel(game_ch.channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Template sync")
                            removed_count += 1
                        except discord.HTTPException as e:
                            errors.append(f"Failed to delete {game_ch.name}: {e}")
                    await db_remove_game_channel(game.id, game_ch.name)
        
        result = f"Sync complete.\nAdded: {added_count} channels\nRemoved: {removed_count} channels"
        if errors:
            result += f"\n\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                result += f"\n... and {len(errors) - 10} more errors"
        
        await interaction.followup.send(result)
    
    @template_group.command(name="export", description="Export template to JSON file")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_export(self, interaction: discord.Interaction):
        channels = await get_all_template_channels()
        groups = await get_all_groups()
        
        export_data = {
            "groups": [{"name": g.name, "emoji": g.emoji} for g in groups],
            "channels": [
                {
                    "name": ch.name,
                    "group": ch.group_name,
                    "is_voice": ch.is_voice,
                    "description": ch.description
                }
                for ch in channels
            ]
        }
        
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        file = discord.File(io.BytesIO(json_str.encode('utf-8')), filename="template.json")
        
        await interaction.response.send_message(
            f"Template exported: {len(groups)} groups, {len(channels)} channels",
            file=file
        )
    
    @template_group.command(name="import", description="Import template from JSON file")
    @app_commands.describe(
        file="JSON file with template data",
        mode="merge: add/update entries, replace: clear and import fresh"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="merge", value="merge"),
        app_commands.Choice(name="replace", value="replace"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def template_import(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        mode: str = "merge"
    ):
        if not file.filename.endswith('.json'):
            await interaction.response.send_message("File must be .json")
            return
        
        await interaction.response.defer()
        
        try:
            content = await file.read()
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            await interaction.followup.send(f"Invalid JSON: {e}")
            return
        
        groups_imported = 0
        channels_imported = 0
        errors = []
        
        if mode == "replace":
            await clear_template_channels()
        
        if "groups" in data:
            for g in data["groups"]:
                try:
                    name = g.get("name")
                    emoji = g.get("emoji", "")
                    if name:
                        await upsert_group(name, emoji)
                        groups_imported += 1
                except Exception as e:
                    errors.append(f"Group {g}: {e}")
        
        if "channels" in data:
            for ch in data["channels"]:
                try:
                    name = ch.get("name")
                    group = ch.get("group")
                    if not name or not group:
                        errors.append(f"Channel missing name or group: {ch}")
                        continue
                    
                    is_voice = ch.get("is_voice", False)
                    description = ch.get("description")
                    await upsert_template_channel(name, group, is_voice, description)
                    channels_imported += 1
                except Exception as e:
                    errors.append(f"Channel {ch}: {e}")
        
        result = f"Import complete ({mode} mode).\nGroups: {groups_imported}\nChannels: {channels_imported}"
        if errors:
            result += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                result += f"\n... and {len(errors) - 10} more"
        
        await interaction.followup.send(result)
    
    @template_group.command(name="groups", description="List all groups and their emojis")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_groups(self, interaction: discord.Interaction):
        groups = await get_all_groups()
        
        if not groups:
            await interaction.response.send_message("No groups configured.")
            return
        
        embed = discord.Embed(title="Channel Groups", color=discord.Color.green())
        for group in groups:
            embed.add_field(name=f"{group.emoji} {group.name}", value=f"Emoji: {group.emoji}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @template_group.command(name="emoji", description="Change a group's emoji")
    @app_commands.describe(group="Group name", emoji="New emoji for the group")
    @app_commands.checks.has_permissions(administrator=True)
    async def template_emoji(self, interaction: discord.Interaction, group: str, emoji: str):
        group_obj = await get_group(group)
        if not group_obj:
            groups = await get_all_groups()
            group_names = ", ".join(g.name for g in groups)
            await interaction.response.send_message(f"Group `{group}` not found. Available: {group_names}")
            return
        
        old_emoji = group_obj.emoji
        await update_group_emoji(group, emoji)
        await interaction.response.send_message(
            f"Updated `{group}` emoji: {old_emoji} -> {emoji}\nUse `/template sync` to update existing channels."
        )
    
    @template_remove.autocomplete("name")
    async def template_name_autocomplete(self, interaction: discord.Interaction, current: str):
        channels = await get_all_template_channels()
        return [
            app_commands.Choice(name=ch.name, value=ch.name)
            for ch in channels
            if current.lower() in ch.name.lower()
        ][:25]
    
    @template_add.autocomplete("group")
    @template_emoji.autocomplete("group")
    async def group_autocomplete(self, interaction: discord.Interaction, current: str):
        groups = await get_all_groups()
        return [
            app_commands.Choice(name=f"{g.emoji} {g.name}", value=g.name)
            for g in groups
            if current.lower() in g.name.lower()
        ][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(TemplatesCog(bot))
