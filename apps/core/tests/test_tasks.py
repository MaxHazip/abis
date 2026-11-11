import pytest
from apps.core.tasks import catch_bid
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta

@pytest.mark.django_db
def test_something():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    token = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    assert token
    assert feedback.status == Feedback.Status.PROCESSING
    assert feedback.started_attempts_count == 1
    assert feedback.processing_expires_at <= timezone.now() + timedelta(minutes=5)
    assert feedback.processing_token == token