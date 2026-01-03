import discord
from discord.ext import commands

from .config import DISCORD_TOKEN, GUILD_ID, MEMBER_ROLES
from .database import init_db, get_all_games, get_game_roles, get_all_game_roles
from .utils import format_role_name


class GameDevBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        await init_db()
        await self.load_extension("bot.cogs.templates")
        await self.load_extension("bot.cogs.games")
        await self.load_extension("bot.cogs.tasks")
        await self.load_extension("bot.cogs.setup")
        
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
    
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        
        # Sync roles on startup
        await self.sync_all_game_roles()
    
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """When member roles change, update their game roles."""
        before_roles = set(r.name for r in before.roles)
        after_roles = set(r.name for r in after.roles)
        
        # Check if any member roles changed
        member_roles_changed = False
        for role_name in MEMBER_ROLES:
            if (role_name in before_roles) != (role_name in after_roles):
                member_roles_changed = True
                break
        
        if not member_roles_changed:
            return
        
        # Update game roles for this member
        await self.sync_member_game_roles(after)
    
    async def sync_all_game_roles(self):
        """Sync game roles for all members based on their member roles."""
        if not GUILD_ID:
            return
        
        guild = self.get_guild(int(GUILD_ID))
        if not guild:
            return
        
        games = await get_all_games()
        if not games:
            return
        
        print(f"Syncing game roles for {len(guild.members)} members...")
        
        for member in guild.members:
            if member.bot:
                continue
            await self.sync_member_game_roles(member)
        
        print("Game role sync complete.")
    
    async def sync_member_game_roles(self, member: discord.Member):
        """Sync game roles for a single member based on their member roles."""
        guild = member.guild
        member_role_names = {r.name for r in member.roles}
        
        # Get all game roles from DB
        all_game_roles = await get_all_game_roles()
        
        # Map suffix -> member role name
        suffix_to_member_role = {role: role for role in MEMBER_ROLES}
        
        roles_to_add = []
        roles_to_remove = []
        
        for game_role in all_game_roles:
            discord_role = guild.get_role(game_role.role_id)
            if not discord_role:
                continue
            
            # Check if member has corresponding member role
            member_role_name = suffix_to_member_role.get(game_role.suffix)
            has_member_role = member_role_name and member_role_name in member_role_names
            has_game_role = discord_role in member.roles
            
            if has_member_role and not has_game_role:
                roles_to_add.append(discord_role)
            elif not has_member_role and has_game_role:
                roles_to_remove.append(discord_role)
        
        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Game role sync")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Game role sync")
        except discord.Forbidden:
            print(f"Missing permissions to modify roles for {member.name}")
        except discord.HTTPException as e:
            print(f"Failed to modify roles for {member.name}: {e}")


def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set in environment")
        return
    
    bot = GameDevBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
