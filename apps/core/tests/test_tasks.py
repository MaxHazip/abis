import pytest
from apps.core.tasks import (
    catch_bid, 
    mark_feedback_as_sent, 
    check_unsuccessful_sent_attempt, 
    task_recovery,
    find_stuck_feedback_ids,
    periodic_processing_task,
    find_applications_to_resending
)
from apps.core.models import Feedback
from django.utils import timezone
from datetime import timedelta
import uuid
import threading
from django.db import transaction, close_old_connections, connections
import queue
from copy import copy
from django.db import OperationalError
from unittest.mock import patch, Mock

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
def create_feedbacks():

    feedback = Feedback(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    feedback1 = copy(feedback)
    feedback1.status = Feedback.Status.PROCESSING
    feedback1.processing_expires_at = timezone.now() - timedelta(minutes=60)
    feedback1.save()
    feedback1.refresh_from_db()

    feedback2 = copy(feedback)
    feedback2.status = Feedback.Status.PROCESSING
    feedback2.processing_expires_at = timezone.now() + timedelta(minutes=30)
    feedback2.phone_number = "+79991234567"
    feedback2.save()
    feedback2.refresh_from_db()

    feedback3 = copy(feedback)
    feedback3.status = Feedback.Status.PENDING
    feedback3.processing_expires_at = timezone.now() - timedelta(minutes=120)
    feedback3.phone_number = "+79992345678"
    feedback3.save()
    feedback3.refresh_from_db()

    feedback4 = copy(feedback)
    feedback4.status = Feedback.Status.PROCESSING
    feedback4.processing_expires_at = None
    feedback4.phone_number = "+79993456789"
    feedback4.save()
    feedback4.refresh_from_db()

    feedback5 = copy(feedback)
    feedback5.status = Feedback.Status.PROCESSING
    feedback5.processing_expires_at = timezone.now() - timedelta(minutes=90)
    feedback5.phone_number = "+79994567890"
    feedback5.save()
    feedback5.refresh_from_db()

    return [feedback1, feedback2, feedback3, feedback4, feedback5]

@pytest.fixture
def create_feedbacks_for_pereodics_tasks():

    feedback = Feedback(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    feedback1 = copy(feedback)
    feedback1.status = Feedback.Status.PROCESSING
    feedback1.processing_expires_at = timezone.now() - timedelta(minutes=10)
    feedback1.started_attempts_count = 1
    feedback1.processing_token = uuid.uuid4()
    feedback1.save()
    feedback1.refresh_from_db()

    feedback2 = copy(feedback)
    feedback2.status = Feedback.Status.PROCESSING
    feedback2.processing_expires_at = timezone.now() - timedelta(minutes=5)
    feedback2.phone_number = "+79991234567"
    feedback2.started_attempts_count = 5
    feedback2.processing_token = uuid.uuid4()
    feedback2.save()
    feedback2.refresh_from_db()

    feedback3 = copy(feedback)
    feedback3.status = Feedback.Status.PROCESSING
    feedback3.processing_expires_at = timezone.now() + timedelta(minutes=60)
    feedback3.phone_number = "+79992345678"
    feedback3.started_attempts_count = 1
    feedback3.processing_token = uuid.uuid4()
    feedback3.save()
    feedback3.refresh_from_db()

    return [feedback1, feedback2, feedback3]

@pytest.fixture
def pending_feedbacks():

    feedback = Feedback(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True
    )

    feedback1 = copy(feedback)
    feedback1.status = Feedback.Status.PENDING
    feedback1.next_retry_at = timezone.now() - timedelta(minutes=10)
    feedback1.started_attempts_count = 2
    feedback1.phone_number = "+79991234563"
    feedback1.save()
    feedback1.refresh_from_db()

    feedback2 = copy(feedback)
    feedback2.status = Feedback.Status.PROCESSING
    feedback2.processing_expires_at = timezone.now() + timedelta(minutes=30)
    feedback2.phone_number = "+79991234567"
    feedback2.save()
    feedback2.refresh_from_db()

    feedback3 = copy(feedback)
    feedback3.status = Feedback.Status.PENDING
    feedback3.next_retry_at = None
    feedback3.started_attempts_count = 5
    feedback3.phone_number = "+79391234567"
    feedback3.save()
    feedback3.refresh_from_db()

    feedback4 = copy(feedback)
    feedback4.status = Feedback.Status.PENDING
    feedback4.next_retry_at = timezone.now() - timedelta(minutes=10)
    feedback4.started_attempts_count = 5
    feedback4.phone_number = "+79391234567"
    feedback4.save()
    feedback4.refresh_from_db()

    feedback5 = copy(feedback)
    feedback5.status = Feedback.Status.PENDING
    feedback5.next_retry_at = timezone.now() + timedelta(minutes=60)
    feedback5.started_attempts_count = 3
    feedback5.phone_number = "+79591234567"
    feedback5.save()
    feedback5.refresh_from_db()

    feedback6 = copy(feedback)
    feedback6.status = Feedback.Status.PENDING
    feedback6.next_retry_at = timezone.now() - timedelta(minutes=90)
    feedback6.last_name = "Шишкин"
    feedback6.first_name = "Владимир"
    feedback6.started_attempts_count = 4
    feedback6.phone_number = "+79494567890"
    feedback6.save()
    feedback6.refresh_from_db()

    return [feedback1, feedback2, feedback3, feedback4, feedback5, feedback6]


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
    feedback: Feedback
):  
    feedback.next_retry_at = timezone.now() + timedelta(minutes=5)
    feedback.save()    

    init_feedback = copy(feedback)

    token = catch_bid(feedback_id=feedback.id)

    feedback.refresh_from_db()

    assert token is None
    assert feedback.status == init_feedback.status
    assert feedback.started_attempts_count == init_feedback.started_attempts_count
    assert feedback.next_retry_at == init_feedback.next_retry_at
    assert feedback.processing_token == init_feedback.processing_token
    assert feedback.processing_expires_at == init_feedback.processing_expires_at

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

@pytest.mark.django_db
def test_check_unsuccessful_sent_attempt_last_attempt(
    feedback: Feedback
):

    feedback.started_attempts_count = 4
    feedback.save()

    token = catch_bid(feedback_id=feedback.id)

    assert check_unsuccessful_sent_attempt(feedback_id=feedback.id, processing_token=token, error="Test Error")

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.FAILED
    assert feedback.next_retry_at is None
    assert feedback.last_error == "Test Error"
    assert feedback.processing_token is None
    assert feedback.processing_expires_at is None
    assert feedback.started_attempts_count == 5

@pytest.mark.django_db
def test_check_unsuccessful_sent_old_worker(
    feedback: Feedback
):

    feedback.status = Feedback.Status.PROCESSING
    
    token_b = uuid.uuid4()

    feedback.processing_token = token_b
    feedback.save()

    feedback.refresh_from_db()

    init_feedback = copy(feedback)

    token_a = uuid.uuid4()

    assert not check_unsuccessful_sent_attempt(feedback_id=feedback.id, processing_token=token_a, error="Test Error")

    feedback.refresh_from_db()

    assert feedback.status == init_feedback.status
    assert feedback.next_retry_at == init_feedback.next_retry_at
    assert feedback.last_error == init_feedback.last_error
    assert feedback.processing_token == init_feedback.processing_token
    assert feedback.processing_expires_at == init_feedback.processing_expires_at
    assert feedback.started_attempts_count == init_feedback.started_attempts_count

@pytest.mark.django_db
def test_task_recovery(
    feedback: Feedback
):

    feedback.status = Feedback.Status.PROCESSING
    feedback.processing_expires_at = timezone.now() - timedelta(minutes=10)
    feedback.started_attempts_count = 2
    feedback.processing_token = uuid.uuid4()

    feedback.save()

    before_time = timezone.now() + timedelta(minutes=15)

    assert task_recovery(feedback_id=feedback.id, error="Test Error")

    after_time = timezone.now() + timedelta(minutes=15)

    feedback.refresh_from_db()

    assert feedback.processing_expires_at is None
    assert feedback.status == Feedback.Status.PENDING
    assert feedback.next_retry_at > before_time
    assert feedback.next_retry_at <= after_time
    assert feedback.processing_token is None
    assert feedback.last_error == "Test Error"
    assert feedback.started_attempts_count == 2

@pytest.mark.django_db
def test_task_recovery_future_task(
    feedback:Feedback
):

    feedback.status = Feedback.Status.PROCESSING
    feedback.processing_expires_at = timezone.now() + timedelta(minutes=10)
    feedback.processing_token = uuid.uuid4()

    feedback.save()

    feedback.refresh_from_db()

    init_feedback = copy(feedback)

    assert not task_recovery(feedback_id=feedback.id, error="Test Error")

    feedback.refresh_from_db()

    assert feedback.started_attempts_count == 0
    assert feedback.processing_expires_at == init_feedback.processing_expires_at
    assert feedback.status == init_feedback.status
    assert feedback.next_retry_at == init_feedback.next_retry_at
    assert feedback.last_error == init_feedback.last_error
    assert feedback.processing_token == init_feedback.processing_token

@pytest.mark.django_db
def test_task_retry_no_more_attempts(
    feedback: Feedback
):

    feedback.started_attempts_count = 5
    feedback.processing_expires_at = timezone.now() - timedelta(minutes=5)
    feedback.status = Feedback.Status.PROCESSING
    feedback.processing_token = uuid.uuid4()

    feedback.save()

    assert task_recovery(feedback_id=feedback.id, error=("Test Error"))

    feedback.refresh_from_db()

    assert feedback.status == Feedback.Status.FAILED
    assert feedback.next_retry_at is None
    assert feedback.last_error == "Test Error"
    assert feedback.started_attempts_count == 5
    assert feedback.processing_expires_at is None
    assert feedback.processing_token is None

@pytest.mark.django_db
def test_task_retry_not_processing(
    feedback: Feedback
):

    feedback.processing_expires_at = timezone.now() - timedelta(minutes=10)
    
    feedback.save()

    init_feedback = copy(feedback)

    assert not task_recovery(feedback_id=feedback.id, error="Test Error")

    feedback.refresh_from_db()

    assert feedback.processing_expires_at == init_feedback.processing_expires_at
    assert feedback.status == init_feedback.status
    assert feedback.next_retry_at == init_feedback.next_retry_at
    assert feedback.last_error == init_feedback.last_error
    assert feedback.processing_token == init_feedback.processing_token
    assert feedback.started_attempts_count == 0

@pytest.mark.django_db
def test_task_retry_processing_expires_none(
    feedback: Feedback
):

    feedback.status = Feedback.Status.PROCESSING
    feedback.processing_expires_at = None
    feedback.processing_token = uuid.uuid4()

    feedback.save()

    init_feedback = copy(feedback)

    assert not task_recovery(feedback_id=feedback.id, error="Test Error")

    feedback.refresh_from_db()
    
    assert feedback.processing_expires_at == init_feedback.processing_expires_at
    assert feedback.status == init_feedback.status
    assert feedback.next_retry_at == init_feedback.next_retry_at
    assert feedback.last_error == init_feedback.last_error
    assert feedback.processing_token == init_feedback.processing_token
    assert feedback.started_attempts_count == 0

@pytest.mark.django_db
def test_find_tasks_for_retry(
    create_feedbacks: list[Feedback]
):

    created_tasks_ids = []

    for task in create_feedbacks:
        created_tasks_ids.append(task.id)


    tasks_ids = find_stuck_feedback_ids()

    assert tasks_ids == [created_tasks_ids[4], created_tasks_ids[0]]

@pytest.mark.django_db
def test_periodic_processing_task(
    create_feedbacks_for_pereodics_tasks: list[Feedback]
):

    init_third_task = copy(create_feedbacks_for_pereodics_tasks[2])

    created_tasks_ids = []

    for task in create_feedbacks_for_pereodics_tasks:
        created_tasks_ids.append(task.id)

    before_time = timezone.now() + timedelta(minutes=5)

    assert periodic_processing_task() == 2

    after_time = timezone.now() + timedelta(minutes=5)

    for task in create_feedbacks_for_pereodics_tasks:
        task.refresh_from_db()

        if (task.id == created_tasks_ids[0]):
            assert task.status == Feedback.Status.PENDING
            assert task.next_retry_at <= after_time
            assert task.next_retry_at > before_time
            assert task.last_error == "Processing deadline exceeded"
            assert task.processing_expires_at == None
            assert task.processing_token == None

        elif (task.id == created_tasks_ids[1]): 
            assert task.status == Feedback.Status.FAILED
            assert task.next_retry_at is None
            assert task.last_error == "Processing deadline exceeded"
            assert task.processing_expires_at == None
            assert task.processing_token == None

        elif (task.id == created_tasks_ids[2]): 
            assert task.status == Feedback.Status.PROCESSING
            assert task.processing_expires_at == init_third_task.processing_expires_at
            assert task.processing_token == init_third_task.processing_token

@pytest.mark.django_db
def test_periodic_processing_task_lock_exception():

    with patch(
        "apps.core.tasks.find_stuck_feedback_ids",
        return_value=[1, 2, 3]
    ):

        pg_error = Exception()
        pg_error.pgcode = "55P03"

        db_error = OperationalError("Ошибка блокировки")
        db_error.__cause__ = pg_error

        with patch(
            "apps.core.tasks.task_recovery",
            side_effect=[
                True, 
                db_error,
                True
            ]
        ) as mock_recovery:

            tasks_count = periodic_processing_task()

            assert tasks_count == 2
            assert mock_recovery.call_count == 3

@pytest.mark.django_db
def test_periodic_processing_task_doesnt_exists_exception():

    with patch(
        "apps.core.tasks.find_stuck_feedback_ids",
        return_value=[1, 2, 3]
    ):

        pg_error = Feedback.DoesNotExist

        with patch(
            "apps.core.tasks.task_recovery",
            side_effect=[
                True, 
                pg_error,
                True
            ]
        ) as mock_recovery:

            tasks_count = periodic_processing_task()

            assert tasks_count == 2
            assert mock_recovery.call_count == 3

@pytest.mark.django_db
def test_periodic_processing_task_other_exception():

    with patch(
        "apps.core.tasks.find_stuck_feedback_ids",
        return_value=[1, 2, 3]
    ):

        pg_error = OperationalError("Ошибка БД")

        with patch(
            "apps.core.tasks.task_recovery",
            side_effect=[
                True, 
                pg_error,
                False
            ]
        ) as mock_recovery:

            with pytest.raises(OperationalError, match="Ошибка БД"):
                periodic_processing_task()

            assert mock_recovery.call_count == 2

@pytest.mark.django_db
def test_find_applications_to_resending(
    pending_feedbacks: list[Feedback]
):

    assert find_applications_to_resending() == [pending_feedbacks[5].id, pending_feedbacks[0].id]