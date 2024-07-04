
import time

from corptools import models as ctm

from ..exceptions import MutedException
from ..models import MutedStructure
from ..providers import cache_client
from .base import NotificationPing


class TowerAlertMsg(NotificationPing):
    category = "starbase-attack"  # starbase Alerts

    """
    TowerAlertMsg Example

    aggressorAllianceID: 933731581
    aggressorCorpID: 98656901
    aggressorID: 109390934
    armorValue: 0.35075108372869623
    hullValue: 1.0
    moonID: 40255844
    shieldValue: 6.249723757441368e-10
    solarSystemID: 30004040
    typeID: 27786
    """

    def build_ping(self):
        try:
            muted = MutedStructure.objects.get(
                structure_id=self._data['moonID'])
            if muted.expired():
                muted.delete()
            else:
                raise MutedException()
        except MutedStructure.DoesNotExist:
            # no mutes move on
            pass

        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarSystemID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name

        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        moon, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(
            self._data['moonID'])

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        title = "Starbase Under Attack!"
        shld = float(self._data['shieldValue']*100)
        armr = float(self._data['armorValue']*100)
        hull = float(self._data['hullValue']*100)
        body = "Structure under Attack!\n[ S: {0:.2f}% A: {1:.2f}% H: {2:.2f}% ]".format(
            shld, armr, hull)

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        corp_name = "[%s](https://zkillboard.com/search/%s/)" % \
            (self._notification.character.character.corporation_name,
             self._notification.character.character.corporation_name.replace(" ", "%20"))
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        attackerStr = "Unknown"
        if self._data['aggressorID']:
            attacking_char, _ = ctm.EveName.objects.get_or_create_from_esi(
                self._data['aggressorID'])
            attacking_char_corp, _ = ctm.EveName.objects.get_or_create_from_esi(
                self._data['aggressorCorpID'])
            attacking_alliance_name = ""
            if self._data.get('aggressorAllianceID', False):
                attacking_char_alliance, _ = ctm.EveName.objects.get_or_create_from_esi(
                    self._data['aggressorAllianceID'])
                attacking_alliance_name = attacking_char_alliance.name

            attackerStr = "*[%s](https://zkillboard.com/search/%s/)*, [%s](https://zkillboard.com/search/%s/), **[%s](https://zkillboard.com/search/%s/)**" % \
                (attacking_char.name,
                 attacking_char.name.replace(" ", "%20"),
                 attacking_char_corp.name,
                 attacking_char_corp.name.replace(" ", "%20"),
                 attacking_alliance_name,
                 attacking_alliance_name.replace(" ", "%20"))

        fields = [{'name': 'Moon', 'value': moon.name, 'inline': True},
                  {'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Region', 'value': region_name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Attacker', 'value': attackerStr, 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=15105570)

        self._corp = self._notification.character.character.corporation_id
        self._alli = self._notification.character.character.alliance_id
        self._region = system_db.constellation.region.region_id
        self.force_at_ping = True

        if moon.name:
            epoch_time = int(time.time())
            cache_client.zadd("ctpingermute", {moon.name: epoch_time})
            rcount = cache_client.zcard("ctpingermute")
            if rcount > 5:
                cache_client.bzpopmin("ctpingermute")


"""
TowerResourceAlertMsg

allianceID: 1900696668
corpID: 680022174
moonID: 40066395
solarSystemID: 30001041
typeID: 16214
wants:
- quantity: 780
  typeID: 4246
"""
