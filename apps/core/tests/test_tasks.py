import pytest
from apps.core.tasks import catch_bid
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta
import uuid
import threading
from django.db import transaction, connection, close_old_connections, connections
import queue

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
def feedback_with_future_retry():

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

    before_time = timezone.now() + timedelta(minutes=5)

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

    before_time = timezone.now() + timedelta(minutes=5)

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
    feedback_with_future_retry: Feedback
):

    initial_feedback_time = feedback_with_future_retry.next_retry_at
    initial_feedback_status = feedback_with_future_retry.status
    initial_feedback_attempts_count = feedback_with_future_retry.started_attempts_count
    initial_feedback_token = feedback_with_future_retry.processing_token
    initial_feedback_processing_expires_at = feedback_with_future_retry.processing_expires_at

    token = catch_bid(feedback_id=feedback_with_future_retry.id)

    feedback_with_future_retry.refresh_from_db()

    assert token is None
    assert feedback_with_future_retry.status == initial_feedback_status
    assert feedback_with_future_retry.started_attempts_count == initial_feedback_attempts_count
    assert feedback_with_future_retry.next_retry_at == initial_feedback_time
    assert feedback_with_future_retry.processing_token == initial_feedback_token
    assert feedback_with_future_retry.processing_expires_at == initial_feedback_processing_expires_at

@pytest.mark.django_db
def test_catch_bid_too_many_attempts(
    feedback: Feedback
):

    feedback.started_attempts_count = 5
    feedback.save()

    initial_feedback_status = feedback.status
    initial_feedback_attempts_count = feedback.started_attempts_count
    initial_feedback_token = feedback.processing_token
    initial_feedback_processing_expires_at = feedback.processing_expires_at

    token = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    assert token is None
    assert feedback.status == initial_feedback_status
    assert feedback.started_attempts_count == initial_feedback_attempts_count
    assert feedback.processing_token == initial_feedback_token
    assert feedback.processing_expires_at == initial_feedback_processing_expires_at

@pytest.mark.django_db
def test_catch_bid_sent(
    feedback: Feedback
):

    feedback.status = Feedback.Status.SENT
    feedback.save()

    initial_feedback_attempts_count = feedback.started_attempts_count
    initial_feedback_token = feedback.processing_token
    initial_feedback_processing_expires_at = feedback.processing_expires_at

    token = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    assert token is None
    assert feedback.status == Feedback.Status.SENT
    assert feedback.started_attempts_count == initial_feedback_attempts_count
    assert feedback.processing_token == initial_feedback_token
    assert feedback.processing_expires_at == initial_feedback_processing_expires_at

@pytest.mark.django_db
def test_catch_bid_ready_for_attempt(
    feedback: Feedback
):

    feedback.next_retry_at = timezone.now() - timedelta(minutes=10)
    feedback.started_attempts_count = 2 
    feedback.save()

    before_time = timezone.now() + timedelta(minutes=5)
    token = catch_bid(feedback_id=feedback.id)
    after_time = timezone.now() + timedelta(minutes=5)

    feedback.refresh_from_db()

    assert isinstance(token, uuid.UUID)
    assert feedback.status == Feedback.Status.PROCESSING
    assert feedback.started_attempts_count == 3
    assert feedback.processing_expires_at <= after_time
    assert feedback.processing_expires_at > before_time
    assert feedback.processing_token == token

@pytest.mark.django_db
def test_catch_bid_no_such_feedback():

    with pytest.raises(Feedback.DoesNotExist) as exc_info:
        token = catch_bid(feedback_id=1)

def thread_a(
    feedback_id: int,
    lock_event: threading.Event,
    free_event: threading.Event,
    errors: queue.Queue
):

    try: 
        with transaction.atomic():

            feedback = Feedback.objects.select_for_update(nowait=True).get(id=feedback_id)
            lock_event.set()
            free_event.wait()
    except Exception as e:

        errors.put(e)
        
    finally:

        connections.close_all()

@pytest.mark.django_db(transaction=True)
def test_catch_bid_competing_workers(
    feedback: Feedback
):

    try: 

        errors = queue.Queue()

        lock_event = threading.Event()
        free_event = threading.Event()
        thread = threading.Thread(target=thread_a, args=(feedback.id, lock_event, free_event, errors))
        thread.start()
        lock_event.wait(timeout=10)


    finally:


        free_event.set()

        thread.join(timeout=10)

        close_old_connections()

        assert errors.empty()