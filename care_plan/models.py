import uuid

from django.db import models


class CarePlan(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    patient_data = models.JSONField()

    care_plan = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
