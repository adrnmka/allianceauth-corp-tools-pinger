from django.db import models
from allianceauth.eveonline.models import EveAllianceInfo, EveCorporationInfo
from corptools.models import MapRegion


class PingType(models.Model):
    name = models.CharField(max_length=100)
    class_tag = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class DiscordWebhook(models.Model):
    nickname = models.TextField(default = "Discord Webhook")
    discord_webhook = models.TextField()

    corporation_filter = models.ManyToManyField(EveCorporationInfo,
        related_name="corp_filters",
        blank=True)

    alliance_filter = models.ManyToManyField(EveAllianceInfo,
        related_name="alli_filters",
        blank=True)

    region_filter = models.ManyToManyField(MapRegion,
        related_name="region_filters",
        blank=True)

    ping_types = models.ManyToManyField(PingType,
        blank=True)


class Ping(models.Model):
    notification_id = models.BigIntegerField()
    hook = models.ForeignKey(DiscordWebhook, on_delete=models.CASCADE)
    body = models.TextField()
    time = models.DateTimeField()
    ping_sent = models.BooleanField(default=False)
    alerting = models.BooleanField(default=False)

    def __str__(self):
        return "%s, %s" % (self.notification_id, str(self.time.strftime("%Y %m %d %H:%M:%S")))

    class Meta:
        indexes = (
            models.Index(fields=['notification_id']),
            models.Index(fields=['time']),
        )
    
    def send_ping(self):
        from . import tasks
        tasks.send_ping.apply_async(
            priority=2,
            args=[
                    self.id
                ]
            )
