
import datetime
import logging

from corptools import models as ctm
from django.utils import timezone

from .base import NotificationPing
from .helpers import (create_timer, filetime_to_dt, format_timedelta,
                      time_till_to_td, timers_enabled)

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


class SkyhookUnderAttack(NotificationPing):
    category = "orbital-attack"  # orbital-attack

    """
        allianceID: 1900696668
        allianceLinkData:
        - showinfo
        - 16159
        - 1900696668
        allianceName: The Initiative.
        armorPercentage: 100.0
        charID: 90406623
        corpLinkData:
        - showinfo
        - 2
        - 98434316
        corpName: Tactically Challenged
        hullPercentage: 100.0
        isActive: true
        itemID: &id001 1045736027496
        planetID: 40290676
        planetShowInfoData:
        - showinfo
        - 2015
        - 40290676
        shieldPercentage: 94.98293275026545
        skyhookShowInfoData:
        - showinfo
        - 81080
        - *id001
        solarsystemID: 30004600
        typeID: 81080
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarsystemID'])  # WTF...
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name
        planet_name = planet_db.name

        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        title = "Skyhook Under Attack"
        body = "{} - {} under Attack!\nS: {:.2f}% A: {:.2f}, H: {:.2f}".format(
            structure_type.name,
            system_name,
            float(self._data['shieldPercentage']),
            float(self._data['armorPercentage']),
            float(self._data['hullPercentage']))

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        attacking_char, _ = ctm.EveName.objects.get_or_create_from_esi(
            self._data['charID'])
        attacking_corp = self._data['corpName']

        attacking_alli = None
        if self._data['allianceName']:
            attacking_alli = self._data['allianceName']

        attackerStr = "*[%s](https://zkillboard.com/search/%s/)*, [%s](https://zkillboard.com/search/%s/), **[%s](https://zkillboard.com/search/%s/)**" % \
            (attacking_char.name,
             attacking_char.name.replace(" ", "%20"),
             attacking_corp,
             attacking_corp.replace(" ", "%20"),
             attacking_alli if attacking_alli else "*-*",
             attacking_alli.replace(" ", "%20") if attacking_alli else "")

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


class SkyhookLostShields(NotificationPing):
    category = "orbital-attack"  # orbital-attack

    """
    itemID: &id001 1046042982766
    planetID: 40288591
    planetShowInfoData:
    - showinfo
    - 2017
    - 40288591
    skyhookShowInfoData:
    - showinfo
    - 81080
    - *id001
    solarsystemID: 30004563
    timeLeft: 1859680938756               # figure out what this is
    timestamp: 133690999080000000         # figure out what this is
    typeID: 81080
    vulnerableTime: 9000000000            # figure out what this is
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarsystemID'])
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        planet_name = planet_db.name
        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        _timeTill = filetime_to_dt(self._data['timestamp']).replace(
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


class SkyhookOnline(NotificationPing):
    category = "orbital-attack"  # orbital-attack

    """
        itemID: &id002 1046336471456
        planetID: &id001 40288233
        planetShowInfoData:
        - showinfo
        - 13
        - *id001
        skyhookShowInfoData:
        - showinfo
        - 81080
        - *id002
        solarsystemID: 30004557
        typeID: 81080
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarsystemID'])  # WTF...
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name
        planet_name = planet_db.name

        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        title = "Skyhook Online"
        body = "{} - {} - {} Online".format(
            system_name,
            region_name,
            planet_name
        )

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        footer = {
            "icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
            "text": f"{self._notification.character.character.corporation_name} ({corp_ticker})"
        }

        fields = [
            {'name': 'Planet', 'value': planet_name, 'inline': True},
            {'name': 'System', 'value': system_name, 'inline': True},
            {'name': 'Region', 'value': region_name, 'inline': True},
            {'name': 'Type', 'value': structure_type.name, 'inline': True}
        ]

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


class SkyhookDeployed(NotificationPing):
    category = "orbital-attack"  # orbital-attack

    """
        itemID: &id002 1046336471456
        ownerCorpLinkData:
        - showinfo
        - 2
        - 98609787
        ownerCorpName: Initiative Trust
        planetID: &id001 40288233
        planetShowInfoData:
        - showinfo
        - 13
        - *id001
        skyhookShowInfoData:
        - showinfo
        - 81080
        - *id002
        solarsystemID: 30004557
        timeLeft: 18000000000
        typeID: 81080
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(
            system_id=self._data['solarsystemID'])  # WTF...
        planet_db, _ = ctm.MapSystemPlanet.objects.get_or_create_from_esi(
            planet_id=self._data['planetID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name
        planet_name = planet_db.name

        system_name = f"[{planet_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(
            self._data['typeID'])

        title = "Skyhook Online"
        body = "{} - {} - {} Online".format(
            system_name,
            region_name,
            planet_name
        )

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        footer = {
            "icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
            "text": f"{self._notification.character.character.corporation_name} ({corp_ticker})"
        }

        #out_time = timezone.now() + time_till_to_td()

        fields = [
            {'name': 'Planet', 'value': planet_name, 'inline': True},
            {'name': 'System', 'value': system_name, 'inline': True},
            {'name': 'Region', 'value': region_name, 'inline': True},
            {'name': 'Type', 'value': structure_type.name, 'inline': True}
        ]

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
