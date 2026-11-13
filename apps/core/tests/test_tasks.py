import pytest
from apps.core.tasks import catch_bid, mark_feedback_as_sent, check_unsuccessful_sent_attempt
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta
import uuid
import threading
from django.db import transaction, connection, close_old_connections, connections
import queue
from copy import copy

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
            assert free_event.wait(timeout=10)
    except Exception as e:

        errors.put(e)
        
    finally:

        connections.close_all()

@pytest.mark.django_db(transaction=True)
def test_catch_bid_competing_workers(
    feedback: Feedback
):

    lock_event = threading.Event()
    free_event = threading.Event()

    init_feedback = copy(feedback)

    try: 

        errors = queue.Queue()
        thread = threading.Thread(target=thread_a, args=(feedback.id, lock_event, free_event, errors))
        thread.start()

        assert lock_event.wait(timeout=10)

        token = catch_bid(feedback.id)

        feedback.refresh_from_db()

        assert token is None
        assert feedback.status == init_feedback.status
        assert feedback.started_attempts_count == init_feedback.started_attempts_count
        assert feedback.processing_expires_at == init_feedback.processing_expires_at
        assert feedback.processing_token == init_feedback.processing_token


    finally:


        free_event.set()

        thread.join(timeout=10)

        assert not thread.is_alive()

        close_old_connections()

        assert errors.empty()

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
def test_mark_feedback_as_sent_correct(
    feedback: Feedback      
):

    token = catch_bid(feedback_id=feedback.id)

    assert mark_feedback_as_sent(feedback_id=feedback.id, processing_token=token)

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.SENT
    assert feedback.processing_token is None
    assert feedback.processing_expires_at is None

@pytest.mark.django_db
def test_mark_feedback_as_sent_incorrect_token(
    feedback: Feedback      
):

    token = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    init_feedback = copy(feedback)

    fake_token = uuid.uuid4()

    assert not mark_feedback_as_sent(feedback_id=feedback.id, processing_token=fake_token)

    feedback.refresh_from_db()

    assert token == feedback.processing_token
    assert feedback.status == init_feedback.status
    assert feedback.processing_token == init_feedback.processing_token
    assert feedback.processing_expires_at == init_feedback.processing_expires_at

@pytest.mark.django_db
def test_mark_feedback_as_sent_resubmiission(
    feedback: Feedback
):

    token = catch_bid(feedback_id=feedback.id)

    assert mark_feedback_as_sent(feedback_id=feedback.id, processing_token=token)

    assert not mark_feedback_as_sent(feedback_id=feedback.id, processing_token=token)

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.SENT
    assert feedback.processing_token is None
    assert feedback.processing_expires_at is None

@pytest.mark.django_db
def test_mark_feedback_as_sent_outdated_worker(
    feedback: Feedback
):

    feedback.status = Feedback.Status.PROCESSING

    token_b = uuid.uuid4()

    feedback.processing_token = token_b
    feedback.save()

    token_a = uuid.uuid4()

    assert not mark_feedback_as_sent(feedback_id=feedback.id, processing_token=token_a)

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.PROCESSING
    assert feedback.processing_token == token_b 

@pytest.mark.parametrize(
    "started_attempts_count, delay_mins",
    [
        (0, 5),
        (1, 15),
        (2, 60),
        (3, 360),
    ]       
)
@pytest.mark.django_db
def test_check_unsuccessful_sent_attempt(
    feedback: Feedback,
    started_attempts_count: int,
    delay_mins: int
):

    feedback.started_attempts_count = started_attempts_count
    feedback.save()

    token = catch_bid(feedback_id=feedback.id)

    before_time = timezone.now() + timedelta(minutes=delay_mins)

    assert check_unsuccessful_sent_attempt(feedback_id=feedback.id, processing_token=token, error="Test Error")

    after_time = timezone.now() + timedelta(minutes=delay_mins)

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.PENDING
    assert feedback.next_retry_at <= after_time
    assert feedback.next_retry_at > before_time
    assert feedback.last_error == "Test Error"
    assert feedback.processing_token is None
    assert feedback.processing_expires_at is None
    assert feedback.started_attempts_count == started_attempts_count + 1