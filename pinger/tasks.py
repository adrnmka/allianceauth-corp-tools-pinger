import datetime
import logging
import json
import requests

from celery import shared_task, chain
from django.core.cache import cache

from allianceauth.services.tasks import QueueOnce
from django.utils import timezone

from corptools.task_helpers.char_tasks import update_character_notifications

from corptools.models import CharacterAudit, Notification

from django.db.models import Q
from django.db.models import Max
from pinger.models import DiscordWebhook, Ping

from . import notifications

TZ_STRING = "%Y-%m-%dT%H:%M:%SZ"

CACHE_TIME_SECONDS = 10*60

TASK_PRIO = 3

logger = logging.getLogger(__name__)


def _get_head_id(char_id):
    return Notification.objects.filter(
        character_character_id=char_id,
    ).aggregate(
        Max('id')
    ).get("id__max", 0)


def _build_corp_cache_id(corp_id):
    return f"ct-pingger-corp-{corp_id}"


def _get_cache_data_for_corp(corp_id):
    cached_data = cache.get(_build_corp_cache_id(corp_id), False)
    if cached_data:
        cached_data = json.loads(cached_data)
        last_char = cached_data.get("last_char")
        char_array = cached_data.get("char_array")
        return (last_char, char_array)
    else:
        return False


def _set_cache_data_for_corp(corp_id, last_char, char_array):
    data = {
        "last_char": last_char,
        "char_array": char_array,
    }
    cache.set(_build_corp_cache_id(corp_id), json.dumps(data), CACHE_TIME_SECONDS)


@shared_task
def bootstrap_notification_tasks():
    # build model for all known corps and fire off updates to get the ball rolling.
    # run at 10m intervals to keep sync, otherwise run at 10m/people in corp with roles intervals

    # get list of all active corp tasks from cache

    # get all new corps not in cache
    all_member_corps_in_audit = CharacterAudit.objects.filter(character__character_ownership__user__profiles__state__name__in=["Member"],
                                                              characterroles__station_manager=True,
                                                              active=True).values_list("character__corporation_id", flat=True)
    
    # fire off tasks for each corp with active models
    for cid in all_member_corps_in_audit:
        corporation_notification_update.apply_async(args=(cid), priority=TASK_PRIO+1)

@shared_task(bind=True, base=QueueOnce)
def corporation_notification_update(corporation_id):
    # get oldest token and update notifications chained with a notification check
    data = _get_cache_data_for_corp(corporation_id)
    
    if data:
        last_character = data[1]

        logger.info(f"Last Update was with {last_character}")

        all_chars_in_corp = list(set(CharacterAudit.objects.filter((Q(characterroles__station_manager=True) | Q(characterroles__personnel_manager=True)),
                                                          character__corporation_id=corporation_id,
                                                          active=True).values_list("character__character_id", flat=True)))
        
        logger.info(f"We have these Characters {all_chars_in_corp}")

        all_chars_in_corp.sort()
        if last_character in all_chars_in_corp:
            idx = all_chars_in_corp.index(last_character) + 1
            if idx == len(all_chars_in_corp):
                idx = 0
            character_id = all_chars_in_corp[idx]
            logger.info(f"Updating with {character_id}")
            current_head_id = _get_head_id(character_id)
            #update notifications for this character
            update_character_notifications(character_id)
            # did we get any?
            if current_head_id != _get_head_id(character_id):
                # process pings and send them!

                process_notifications.apply_async(priority=TASK_PRIO)

            # leverage cache
            _set_cache_data_for_corp(corporation_id, )

            # schedule the next corp token depending on the amount available ( 10 min / characters we have ) for each corp
            delay = CACHE_TIME_SECONDS / len(all_chars_in_corp)
            corporation_notification_update.apply_async(priority=(TASK_PRIO+1), countdown=delay)


@shared_task(bind=True, base=QueueOnce)
def process_notifications(self):
    cuttoff = timezone.now() - datetime.timedelta(hours=96)
    
    pings = {}
    # grab all notifications within scope.
    types = notifications.get_available_types()
    pinged_already = set(list(Ping.objects.filter(time__gte=cuttoff).values_list("notification_id", flat=True)))
    new_notifs = Notification.objects.filter(timestamp__gte=cuttoff,
        notification_type__in=types.keys()) \
        .exclude(notification_id__in=pinged_already)
    # parse them into the parsers
    for n in new_notifs:
        if n.notification_id not in pinged_already:
            pinged_already.add(n.notification_id)
            note = types[n.notification_type](n)
            if n.notification_type not in pings:
                pings[n.notification_type] = []
            pings[n.notification_type].append(note)

    # send them to webhooks as needed
    for k, l in pings.items():
        webhooks = DiscordWebhook.objects.filter(ping_types__class_tag=k)\
            .prefetch_related("alliance_filter", "corporation_filter", "region_filter")
        
        for hook in webhooks:
            for p in l:
                corp_filter, alli_filter, region_filter = l.get_filters()

                if corp_filter is not None:
                    corporations = hook.corporation_filter.all().values_list("corporation_id", flat=True)
                    if corp_filter not in corporations:
                        continue

                if alli_filter is not None:
                    alliances = hook.alliance_filters.all().values_list("alliance_id", flat=True)
                    if corp_filter not in alliances:
                        continue

                if region_filter is not None:
                    regions = hook.region_filter.all().values_list("region_id", flat=True)
                    if region_filter not in regions:
                        continue

                ping_ob = Ping.objects.create(
                    notification_id=p._notification.notification_id,
                    time = p._notification.timestamp,
                    body = p._ping,
                    hook = hook,
                    alerting = p.force_at_ping
                )
                ping_ob.send_ping()
            

@shared_task(bind=True, max_retries=None)
def send_ping(self, ping_id):
    ping_ob = Ping.objects.get(id=ping_id)

    if ping_ob.ping_sent == True:
        return "Already done!"

    alertText = ""
    if ping_ob.alerting == True:
        alertText = '"content": "@here", '

    payload = '{%s"embeds": [%s]}' % (
        alertText,
        ping_ob.body
    )
    logger.debug(payload)
    url = ping_ob.hook.discord_webhook
    custom_headers = {'Content-Type': 'application/json'}

    response = requests.post(url,
                             headers=custom_headers,
                             data=payload,
                             params={'wait': True})

    if response.status_code in [200,204]:
        logger.debug(f"{ping_ob.notification_id} Ping Sent!")
        ping_ob.ping_sent = True
        ping_ob.save()
    elif response.status_code == 429:
        errors = json.loads(response.content.decode('utf-8'))
        wh_sleep = (int(errors['retry_after']) / 1000) + 0.15
        logger.warning(f"Webhook rate limited: trying again in {wh_sleep} seconds...")
        self.retry(countdown=wh_sleep)
    else:
        logger.error(f"{ping_ob.notification_id} failed ({response.status_code}) to: {url}")
        response.raise_for_status()
    # TODO 404/403/500 etc etc etc etc
