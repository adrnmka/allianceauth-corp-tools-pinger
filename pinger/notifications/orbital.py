
import datetime
import logging

from corptools import models as ctm
from django.utils import timezone

from .base import NotificationPing
from .helpers import (create_timer, filetime_to_dt, format_timedelta,
                      timers_enabled)

logger = logging.getLogger(__name__)


class OrbitalAttacked(NotificationPing):
    category = "orbital-attack"  # Structure Alerts

    """
    aggressorAllianceID: null
    aggressorCorpID: 98729563
    aggressorID: 90308296
    planetID: 40066681
    planetTypeID: 2016
    shieldLevel: 0.0
    solarSystemID: 30001046
    typeID: 2233
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarSystemID'])
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name
        planet_name = planet_db.name

        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        title = "Poco Under Attack"
        shld = float(self._data['shieldLevel'])*100
        body = "{} under Attack!\nShield Level: {:.2f}%".format(
            structure_type.name, shld)

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        attacking_char, _ = ctm.EveName.objects.get_or_create_from_esi(
            self._data['aggressorID'])
        attacking_corp, _ = ctm.EveName.objects.get_or_create_from_esi(
            self._data['aggressorCorpID'])

        attacking_alli = None
        if self._data['aggressorAllianceID']:
            attacking_alli, _ = ctm.EveName.objects.get_or_create_from_esi(
                self._data['aggressorAllianceID'])

        attackerStr = "*[%s](https://zkillboard.com/search/%s/)*, [%s](https://zkillboard.com/search/%s/), **[%s](https://zkillboard.com/search/%s/)**" % \
            (attacking_char.name,
             attacking_char.name.replace(" ", "%20"),
             attacking_corp.name,
             attacking_corp.name.replace(" ", "%20"),
             attacking_alli.name if attacking_alli else "*-*",
             attacking_alli.name.replace(" ", "%20") if attacking_alli else "")

        fields = [{'name': 'System/Planet', 'value': system_name, 'inline': True},
                  {'name': 'Region', 'value': region_name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Attacker', 'value': attackerStr, 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=15158332)

        self._corp = self._notification.character.character.corporation_id
        self._alli = self._notification.character.character.alliance_id
        self._region = system_db.constellation.region.region_id
        self.force_at_ping = True


class OrbitalReinforced(NotificationPing):
    category = "orbital-attack"  # orbital-attack

    """
    aggressorAllianceID: null
    aggressorCorpID: 98183625
    aggressorID: 94416120
    planetID: 40066687
    planetTypeID: 2016
    reinforceExitTime: 133307777010000000
    solarSystemID: 30001046
    typeID: 2233
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarSystemID'])
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        planet_name = planet_db.name
        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        _timeTill = filetime_to_dt(self._data['reinforceExitTime']).replace(
            tzinfo=datetime.timezone.utc)
        _refTimeDelta = _timeTill - timezone.now()
        tile_till = format_timedelta(_refTimeDelta)

        title = "Poco Reinforced"
        body = f"{structure_type.name} has lost its Shields"

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        corp_name = "[%s](https://zkillboard.com/search/%s/)" % \
            (self._notification.character.character.corporation_name,
             self._notification.character.character.corporation_name.replace(" ", "%20"))
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Owner', 'value': corp_name, 'inline': False},
                  {'name': 'Time Till Out', 'value': tile_till, 'inline': False},
                  {'name': 'Date Out', 'value': _timeTill.strftime("%Y-%m-%d %H:%M"), 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=7419530)

        if timers_enabled():
            try:
                from allianceauth.timerboard.models import TimerType

                self.timer = create_timer(
                    f"{planet_name} POCO",
                    structure_type.name,
                    system_db.name,
                    TimerType.ARMOR,
                    _timeTill,
                    self._notification.character.character.corporation
                )
            except Exception as e:
                logger.exception(
                    f"PINGER: Failed to build timer OrbitalReinforced {e}")

        self._corp = self._notification.character.character.corporation_id
        self._alli = self._notification.character.character.alliance_id
        self._region = system_db.constellation.region.region_id
