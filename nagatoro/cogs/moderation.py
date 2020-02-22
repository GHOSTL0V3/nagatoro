from datetime import datetime
from pony.orm import db_session
from discord import Role
from discord.ext.tasks import loop
from discord.ext.commands import Cog, Context, command, group, cooldown, \
    has_permissions, BucketType, check_any


from nagatoro.checks import is_moderator
from nagatoro.objects import Embed
from nagatoro.converters import Member, Timedelta
from nagatoro.utils.db import get_warns, make_warn, get_guild, get_mutes, \
    make_mute, get_mod_role, get_mute_role, is_muted


class Moderation(Cog):
    """Server moderation"""

    def __init__(self, bot):
        self.bot = bot
        self.check_mutes.start()

    def cog_unload(self):
        self.check_mutes.cancel()

    @group(name="modrole")
    async def mod_role(self, ctx: Context):
        """Check the moderator role"""

        if ctx.invoked_subcommand:
            return

        if not (mod_role := await get_mod_role(self.bot, ctx.guild.id)):
            return await ctx.send(
                "This guild doesn't have mod role set or it was deleted.")

        return await ctx.send(
            f"Mod role for this server: **{mod_role.name}**")

    @mod_role.command(name="set")
    @has_permissions(manage_roles=True)
    @cooldown(rate=1, per=30, type=BucketType.guild)
    async def mod_role_set(self, ctx: Context, role: Role):
        """Set the moderator role for this server"""

        with db_session:
            guild = await get_guild(ctx.guild.id)
            guild.mod_role = role.id

        await ctx.send(f"Set the mod role to **{role.name}**.")

    @mod_role.command(name="remove")
    @has_permissions(manage_roles=True)
    @cooldown(rate=1, per=30, type=BucketType.guild)
    async def mod_role_remove(self, ctx: Context):
        """Remove the mod role for this server

        It is recommended to use use this before deleting the role.
        """

        with db_session:
            guild = await get_guild(ctx.guild.id)
            guild.mod_role = None

        await ctx.send(f"Removed the mod role from {ctx.guild.name}.")

    @group(name="muterole")
    async def mute_role(self, ctx: Context):
        """Check the mute role"""

        if ctx.invoked_subcommand:
            return

        if not (mute_role := await get_mute_role(self.bot, ctx.guild.id)):
            return await ctx.send(
                "This guild doesn't have mute role set or it was deleted.")

        return await ctx.send(
            f"Mute role for this server: **{mute_role.name}**")

    @mute_role.command(name="set")
    @has_permissions(manage_roles=True)
    @cooldown(rate=1, per=30, type=BucketType.guild)
    async def mute_role_set(self, ctx: Context, role: Role):
        """Set the mute role for this server"""

        with db_session:
            guild = await get_guild(ctx.guild.id)
            guild.mute_role = role.id

        await ctx.send(f"Set the mute role to **{role.name}**.")

    @mute_role.command(name="remove")
    @has_permissions(manage_roles=True)
    @cooldown(rate=1, per=30, type=BucketType.guild)
    async def mute_role_remove(self, ctx: Context):
        """Remove the mute role for this server

        It is recommended to use use this before deleting the role.
        """

        with db_session:
            guild = await get_guild(ctx.guild.id)
            guild.mute_role = None

        await ctx.send(f"Removed the mute role from {ctx.guild.name}.")

    @command(name="ban")
    @check_any(is_moderator(), has_permissions(ban_members=True))
    async def ban(self, ctx: Context, member: Member, *,
                  reason: str = None):
        """Ban a member without deleting their messages"""

        await member.ban(reason=reason, delete_message_days=0)

        await ctx.send(f"Banned {member}, reason: *{reason}*. :hammer:")

    @command(name="warn")
    @is_moderator()
    async def warn(self, ctx: Context, member: Member, *, reason: str):
        """Warn a member

        Most emotes don't work with warn reasons.
        """

        # FIXME: Database does not recognise emoji
        await make_warn(ctx, member.id, reason)

        embed = Embed(ctx, title="Warn", color=member.color)
        embed.set_thumbnail(url=member.avatar_url)
        embed.description = f"Warned {member.mention}, reason: *{reason}*"

        await ctx.send(embed=embed)
        await member.send(f"You have been warned in **{ctx.guild.name}**, "
                          f"reason: *{reason}*")

    @command(name="warns")
    @cooldown(rate=3, per=15, type=BucketType.guild)
    async def warns(self, ctx: Context, member: Member = None):
        """See someone else's warns"""

        if not member:
            member = ctx.author

        embed = Embed(ctx, title=f"{member.name}'s warns", description="")
        embed.set_thumbnail(url=member.avatar_url)
        await ctx.trigger_typing()

        with db_session:
            if not (warns := await get_warns(member.id, ctx.guild.id)):
                return await ctx.send(
                    f"{member.name} doesn't have any warns on this server.")

            for i in reversed(warns[:15]):
                moderator = self.bot.get_user(i.given_by)
                embed.description += \
                    f"[{i.when}] {moderator} - *{i.reason}*\n"

        await ctx.send(embed=embed)

    @command(name="mute")
    @is_moderator()
    async def mute(self, ctx: Context, member: Member, time: Timedelta, *,
                   reason: str = "No reason"):
        """Mute a member

        Most emotes don't work with mute reasons.
        """

        if await is_muted(member.id, ctx.guild.id):
            # TODO: Mute time extension
            return await ctx.send(f"{member.name} is already muted.")

        # FIXME: Database does not recognise emoji
        await make_mute(ctx, member.id, time, reason)

        mute_role = await get_mute_role(self.bot, ctx.guild.id)
        await member.add_roles(
            mute_role,
            reason=f"Muted by {ctx.author} for {time}, reason: {reason}"
        )

        embed = Embed(ctx, title="Mute", color=member.color)
        embed.set_thumbnail(url=member.avatar_url)
        embed.description = f"Muted {member.mention} for {time}\n" \
                            f"Reason: *{reason}*"

        await ctx.send(embed=embed)
        await member.send(f"You have been muted in **{ctx.guild.name}** "
                          f"for {time}, reason: *{reason}*")

    @group(name="mutes", invoke_without_command=True)
    @cooldown(rate=3, per=15, type=BucketType.guild)
    async def mutes(self, ctx: Context, member: Member = None):
        """See someone else's mutes"""

        if ctx.invoked_subcommand:
            return

        if not member:
            member = ctx.author

        embed = Embed(ctx, title=f"{member.name}'s mutes", description="")
        embed.set_thumbnail(url=member.avatar_url)
        await ctx.trigger_typing()

        with db_session:
            if not (mutes := await get_mutes(ctx.guild.id, member.id)):
                return await ctx.send(
                    f"{member.name} doesn't have any mutes on this server.")

            for i in reversed(mutes[:15]):
                moderator = await self.bot.fetch_user(i.given_by)
                embed.description += f"[{i.end - i.start}] " \
                                     f"{moderator} - *{i.reason}*\n"

        await ctx.send(embed=embed)

    @mutes.command(name="active")
    @cooldown(rate=2, per=10, type=BucketType.guild)
    async def mutes_active(self, ctx: Context):
        """See active mutes"""

        embed = Embed(ctx, title="Active mutes")
        await ctx.trigger_typing()

        with db_session:
            if not (mutes := await get_mutes(ctx.guild.id, active_only=True)):
                return await ctx.send(
                    f"There are no active mutes in {ctx.guild.name}.")

            for i in reversed(mutes[:10]):
                moderator = await self.bot.fetch_user(i.given_by)
                user = await self.bot.fetch_user(i.user.id)
                embed.add_field(name=str(user),
                                value=f"**Given at**: {i.start}\n"
                                      f"**Duration**: {i.end - i.start}\n"
                                      f"**Moderator**: {moderator.mention}\n"
                                      f"**Reason**: *{i.reason}*")

        await ctx.send(embed=embed)

    @loop(seconds=15)
    async def check_mutes(self):
        with db_session:
            mutes = await get_mutes(active_only=True)

            if not mutes:
                return

            for i in mutes:
                if i.end >= datetime.now():
                    continue

                # Mute ended, remove role and notify in DM's

                guild = self.bot.get_guild(i.guild.id)
                mute_role = guild.get_role(i.guild.mute_role)
                member = guild.get_member(i.user.id)

                await member.remove_roles(mute_role, reason="Mute ended.")
                i.active = False

                await member.send(f"Your mute on {guild.name} has ended.")

    @check_mutes.before_loop
    async def before_check_mutes(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Moderation(bot))
