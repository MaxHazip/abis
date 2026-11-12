import pytest
from apps.core.tasks import catch_bid
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta
import uuid

@pytest.fixture
def feedback():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    return feedback

@pytest.fixture
def feedback_with_early_retry():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True,
        next_retry_at= timezone.now() + timedelta(minutes=5)
    )
    
    return feedback


@pytest.mark.django_db
def test_correct_catch_bid(
    feedback: Feedback
):

    before_time = timezone.now()

    token = catch_bid(feedback_id=feedback.id)

    after_time = timezone.now() + timedelta(minutes=5)

    feedback.refresh_from_db()

    assert isinstance(token, uuid.UUID)
    assert feedback.status == Feedback.Status.PROCESSING
    assert feedback.started_attempts_count == 1
    assert feedback.processing_expires_at <= after_time
    assert feedback.processing_expires_at > before_time
    assert feedback.processing_token == token

@pytest.mark.django_db
def test_catch_bid_already_processing(
    feedback: Feedback
):

    before_time = timezone.now()

    token = catch_bid(feedback_id=feedback.id)

    after_time = timezone.now() + timedelta(minutes=5)

    token2 = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    assert isinstance(token, uuid.UUID)
    assert token2 is None
    assert feedback.status == Feedback.Status.PROCESSING
    assert feedback.started_attempts_count == 1
    assert feedback.processing_expires_at <= after_time
    assert feedback.processing_expires_at > before_time
    assert feedback.processing_token == token

@pytest.mark.django_db
def test_catch_bid_early_time_retry(
    feedback_with_early_retry: Feedback
):

    initial_feedback_time = feedback_with_early_retry.next_retry_at
    initial_feedback_status = feedback_with_early_retry.status
    initial_feedback_attempts_count = feedback_with_early_retry.started_attempts_count
    initial_feedback_token = feedback_with_early_retry.processing_token
    initial_feedback_processing_expires_at = feedback_with_early_retry.processing_expires_at

    token = catch_bid(feedback_id=feedback_with_early_retry.id)

    feedback_with_early_retry.refresh_from_db()

    assert token is None
    assert feedback_with_early_retry.status == initial_feedback_status
    assert feedback_with_early_retry.started_attempts_count == initial_feedback_attempts_count
    assert feedback_with_early_retry.next_retry_at == initial_feedback_time
    assert feedback_with_early_retry.processing_token == initial_feedback_token
    assert feedback_with_early_retry.processing_expires_at == initial_feedback_processing_expires_at