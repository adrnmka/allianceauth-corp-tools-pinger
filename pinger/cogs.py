# Cog Stuff
from discord.ext import commands
# AA Contexts
import pprint
from corptools.models import CharacterAudit
from django.conf import settings
from django.db.models.query_utils import Q
from allianceauth.eveonline.models import EveCharacter

from pinger.tasks import get_settings, _get_cache_data_for_corp

from aadiscordbot import app_settings

import logging

logger = logging.getLogger(__name__)

class PingerCog(commands.Cog):
    """
    All about pinger!
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def pinger_stats(self, ctx):

        if ctx.message.author.id not in app_settings.get_admins():  # https://media1.tenor.com/images/1796f0fa0b4b07e51687fad26a2ce735/tenor.gif
            return await ctx.message.add_reaction(chr(0x1F44E))

        if ctx.message.channel.id not in settings.ADMIN_DISCORD_BOT_CHANNELS:
            return await ctx.message.add_reaction(chr(0x1F44E))

        allis, corps, _ = get_settings()

        # get all new corps not in cache
        all_member_corps_in_audit = CharacterAudit.objects.filter(character__character_ownership__user__profile__state__name__in=["Member"],
                                                                characterroles__station_manager=True,
                                                                active=True)
        
        filters = []
        if len(allis) > 0:
            filters.append(Q(character__alliance_id__in=allis))
        
        if len(corps) > 0:
            filters.append(Q(character__corporation_id__in=corps))

        if len(filters) > 0:
            query = filters.pop()
            for q in filters:
                query |= q
            all_member_corps_in_audit = all_member_corps_in_audit.filter(query)

        corps = all_member_corps_in_audit.values_list("character__corporation_id", "character__corporation_name")

        done = {}
        seen_cid = set()
        for c in corps:
            if c[0] not in seen_cid:
                seen_cid.add(c[0])
                last_char, chars, last_update = _get_cache_data_for_corp(c[0])
                if last_char:
                    last_char_model = EveCharacter.objects.get(character_id=last_char)
                    if last_update < 1:
                        done[c[1]] = f"{c[1]} Total Characters : {len(chars)}, Last Character: {last_char_model.character_name} ({last_char}), Next Update: {last_update} Seconds"
                else:
                    done[c[1]] = f"{c[1]} Not Updated Yet"

        await ctx.message.reply(f"Found {len(done)} Valid Corps!")
        sorted_keys = list(done.keys())
        sorted_keys.sort()

        n = 10
        chunks = [list(sorted_keys[i * n:(i + 1) * n]) for i in range((len(sorted_keys) + n - 1) // n)]

        for c in chunks:
            output = ""
            for i in c:
                output += done[i] + "\n"
            await ctx.send(output)

def setup(bot):
    bot.add_cog(PingerCog(bot))
