import pytest
from apps.core.tasks import catch_bid
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta
import uuid

@pytest.fixture
def get_new_feedback():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    return feedback



@pytest.mark.django_db
def test_correct_catch_bid(
    get_new_feedback: Feedback
):

    before_time = timezone.now()

    token = catch_bid(feedback_id=get_new_feedback.id)

    get_new_feedback.refresh_from_db()

    assert isinstance(token, uuid.UUID)
    assert get_new_feedback.status == Feedback.Status.PROCESSING
    assert get_new_feedback.started_attempts_count == 1
    assert get_new_feedback.processing_expires_at <= timezone.now() + timedelta(minutes=5)
    assert get_new_feedback.processing_expires_at > before_time
    assert get_new_feedback.processing_token == token

@pytest.mark.django_db
def test_catch_bid_already_processing(
    get_new_feedback: Feedback
):

    before_time = timezone.now()

    token = catch_bid(feedback_id=get_new_feedback.id)

    after_time = timezone.now() + timedelta(minutes=5)
    
    get_new_feedback.refresh_from_db()

    token2 = catch_bid(feedback_id=get_new_feedback.id)

    assert isinstance(token, uuid.UUID)
    assert not token2
    assert get_new_feedback.status == Feedback.Status.PROCESSING
    assert get_new_feedback.started_attempts_count == 1
    assert get_new_feedback.processing_expires_at <= after_time
    assert get_new_feedback.processing_expires_at > before_time
    assert get_new_feedback.processing_token == token