import pytest
from apps.core.tasks import (
    catch_bid, 
    mark_feedback_as_sent, 
    check_unsuccessful_sent_attempt, 
    task_recovery,
    find_stuck_feedback_ids,
    periodic_processing_task,
    find_feedback_ids_for_retry,
    send_feedback_notification_task,
    periodic_retry_dispatch_task,
    logger
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
from unittest.mock import patch, call
from smtplib import SMTPException
from redis.exceptions import ConnectionError
from django.test import TestCase
from kombu.exceptions import OperationalError as KombuOperationalError
from celery.exceptions import SoftTimeLimitExceeded

@pytest.fixture
def feedback():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True,
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

@pytest.fixture
def sent_feedback():

    feedback = Feedback.objects.create(
        last_name="Луков",
        first_name="Михаил",
        phone_number="+79233243254",
        privacy=True,
        status=Feedback.Status.SENT,
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

    assert find_feedback_ids_for_retry() == [pending_feedbacks[5].id, pending_feedbacks[0].id]

@pytest.mark.django_db
def test_send_feedback_notification_task_catch(
    sent_feedback: Feedback
):

    init_feedback = copy(sent_feedback)
    
    with patch(
        "apps.core.tasks.send_mail"
    ) as mock_send_mail:

        assert not send_feedback_notification_task(sent_feedback.id)

        mock_send_mail.assert_not_called()

        assert sent_feedback.status == init_feedback.status
        assert sent_feedback.started_attempts_count == init_feedback.started_attempts_count
        assert sent_feedback.processing_token == init_feedback.processing_token

@pytest.mark.django_db
def test_send_feedback_notification_task_success_sent(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    with patch(
        "apps.core.tasks.send_mail",
        return_value=1
    ) as mock_send_mail:

        assert send_feedback_notification_task(feedback_id=feedback.id)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.SENT
        assert feedback.started_attempts_count == 1
        assert feedback.processing_expires_at is None
        assert feedback.processing_token is None
        assert mock_send_mail.call_count == 2

@pytest.mark.django_db
def test_send_feedback_notification_task_mark_false(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    with patch(
        "apps.core.tasks.mark_feedback_as_sent",
        return_value=False
    ):
        with patch(
            "apps.core.tasks.send_mail",
            return_value=1
        ) as mock_send_mail:

            assert not send_feedback_notification_task(feedback_id=feedback.id)

            feedback.refresh_from_db()

            assert feedback.status == Feedback.Status.PROCESSING
            assert feedback.started_attempts_count == 1
            assert mock_send_mail.call_count == 1

@pytest.mark.django_db
def test_send_feedback_notification_task_smtp_error(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    smtp_error = SMTPException("SMTP connection failed")

    with patch(
        "apps.core.tasks.send_mail",
        side_effect=smtp_error
    ) as mock_send_mail:

        before_time = timezone.now() + timedelta(minutes=5)
        
        assert not send_feedback_notification_task(feedback_id=feedback.id)

        after_time = timezone.now() + timedelta(minutes=5)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.PENDING
        assert feedback.started_attempts_count == 1
        assert feedback.next_retry_at > before_time
        assert feedback.next_retry_at <= after_time
        assert feedback.processing_token is None
        assert feedback.processing_expires_at is None
        assert feedback.last_error == "SMTP connection failed"
        assert mock_send_mail.call_count == 1

@pytest.mark.django_db
def test_send_feedback_notification_task_zero_emails(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    with patch(
        "apps.core.tasks.send_mail",
        return_value=0
    ) as mock_send_mail:

        before_time = timezone.now() + timedelta(minutes=5)
        
        assert not send_feedback_notification_task(feedback_id=feedback.id)

        after_time = timezone.now() + timedelta(minutes=5)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.PENDING
        assert feedback.started_attempts_count == 1
        assert feedback.next_retry_at > before_time
        assert feedback.next_retry_at <= after_time
        assert feedback.processing_token is None
        assert feedback.processing_expires_at is None
        assert feedback.last_error == "Send email error"
        assert mock_send_mail.call_count == 1

@pytest.mark.django_db
def test_send_feedback_notification_task_timeout_error(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    timeout_error = TimeoutError("A connection attempt failed because the connected party did not properly respond after a period of time...")

    with patch(
        "apps.core.tasks.send_mail",
        side_effect=timeout_error
    ) as mock_send_mail:

        before_time = timezone.now() + timedelta(minutes=5)
        
        assert not send_feedback_notification_task(feedback_id=feedback.id)

        after_time = timezone.now() + timedelta(minutes=5)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.PENDING
        assert feedback.started_attempts_count == 1
        assert feedback.next_retry_at > before_time
        assert feedback.next_retry_at <= after_time
        assert feedback.processing_token is None
        assert feedback.processing_expires_at is None
        assert feedback.last_error == "A connection attempt failed because the connected party did not properly respond after a period of time..."
        assert mock_send_mail.call_count == 1

@pytest.mark.django_db
def test_send_feedback_notification_task_op_error(
    feedback: Feedback
):

    feedback.email = "dsamkaaw@example.com"
    feedback.save()

    with patch(
        "apps.core.tasks.send_mail",
        return_value=1
    ) as mock_send_mail:

        op_error = OperationalError("Database unavailable")

        with patch(
            "apps.core.tasks.mark_feedback_as_sent",
            side_effect=op_error
        ):

            with patch(
                "apps.core.tasks.check_unsuccessful_sent_attempt"
            ) as mock_check_unsuccessful_sent_attempt:

                with pytest.raises(OperationalError, match="Database unavailable"):
                    send_feedback_notification_task(feedback_id=feedback.id)

                mock_check_unsuccessful_sent_attempt.assert_not_called()
                mock_send_mail.assert_called_once()

@pytest.mark.django_db
def test_periodic_retry_dispatch_task():

    with patch(
        "apps.core.tasks.find_feedback_ids_for_retry",
        return_value=[10, 20, 30]
    ) as mock_find_ids:

        with patch(
            "apps.core.tasks.send_feedback_notification_task.delay",
        ) as mock_sent_feedback:

            assert periodic_retry_dispatch_task() == 3

            assert mock_sent_feedback.call_count == 3

            expected_calls = [
                call(10),
                call(20),
                call(30)
            ]

            assert mock_sent_feedback.call_args_list == expected_calls

@pytest.mark.django_db
def test_periodic_retry_dispatch_task_connection_error():

    with patch(
        "apps.core.tasks.find_feedback_ids_for_retry",
        return_value=[10, 20, 30]
    ) as mock_find_ids:

        redis_connection_error = ConnectionError("Redis connection Error")

        with patch(
            "apps.core.tasks.send_feedback_notification_task.delay",
            side_effect=[
                True,
                redis_connection_error,
                False
            ]
        ) as mock_sent_feedback:

            with pytest.raises(ConnectionError, match="Redis connection Error"):
                periodic_retry_dispatch_task()

            assert mock_sent_feedback.call_count == 2
            assert mock_sent_feedback.call_args_list == [
                call(10),
                call(20)
            ]

@pytest.mark.django_db
def test_whole_send(
    feedback: Feedback
):

    feedback.email = "test@example.com"
    feedback.save()

    smtp_error = SMTPException("Ошибка SMTP")

    with patch(
        "apps.core.tasks.send_mail",
        side_effect=[smtp_error]
    ) as email_mock:

        before_time = timezone.now() + timedelta(minutes=5)
    
        assert not send_feedback_notification_task(feedback_id=feedback.id)

        after_time = timezone.now() + timedelta(minutes=5)

        feedback.refresh_from_db()

        assert feedback.next_retry_at > before_time
        assert feedback.next_retry_at <= after_time
        assert feedback.status == Feedback.Status.PENDING
        assert feedback.started_attempts_count == 1
        assert email_mock.call_count == 1


    assert find_feedback_ids_for_retry() == []

    feedback.next_retry_at = timezone.now() - timedelta(minutes=10)
    feedback.save()

    with patch(
        "apps.core.tasks.send_mail",
        return_value=1
    ) as email_mock:

        feedback_ids = find_feedback_ids_for_retry()

        assert feedback_ids == [feedback.id]

        for feedback_id in feedback_ids:
            send_feedback_notification_task(feedback_id=feedback_id)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.SENT
        assert feedback.started_attempts_count == 2
        assert feedback.processing_expires_at is None
        assert feedback.processing_token is None
        assert email_mock.call_count == 2

    assert find_feedback_ids_for_retry() == []

@pytest.mark.django_db
def test_feedback_retry_limit(
    feedback: Feedback
):

    feedback.email = "test@example.com"
    feedback.save()

    smtp_error = SMTPException("Ошибка SMTP")

    retry_delays = [
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=60),
        timedelta(minutes=360),
        None
    ]

    for attempt, delay in enumerate(retry_delays, start=1):

        with patch(
            "apps.core.tasks.send_mail",
            side_effect=[smtp_error]
        ) as email_mock:

            if (attempt != 1):
                assert find_feedback_ids_for_retry() == []
                
            feedback.next_retry_at = timezone.now() - timedelta(minutes=10)
            feedback.save()

            before_time = 0
            after_time = 0

            feedback_ids = find_feedback_ids_for_retry()

            assert feedback_ids == [feedback.id]

            for feedback_id in feedback_ids:

                if delay is not None: before_time = timezone.now() + delay

                send_feedback_notification_task(feedback_id=feedback_id)

                if delay is not None: after_time = timezone.now() + delay


            feedback.refresh_from_db()

            if (attempt < 5):

                assert feedback.status == Feedback.Status.PENDING
                assert feedback.started_attempts_count == attempt
                assert email_mock.call_count == 1
                assert feedback.next_retry_at > before_time
                assert feedback.next_retry_at <= after_time

            if (attempt == 5):

                assert feedback.status == Feedback.Status.FAILED
                assert feedback.started_attempts_count == 5
                assert feedback.processing_token is None
                assert feedback.processing_expires_at is None
                assert feedback.next_retry_at is None
                assert email_mock.call_count == 1


    with patch(
        "apps.core.tasks.send_mail",
        side_effect=[smtp_error]
    ) as email_mock: 
    
        assert not send_feedback_notification_task(feedback_id=feedback.id)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.FAILED
        assert feedback.started_attempts_count == 5
        assert feedback.processing_token is None
        assert feedback.processing_expires_at is None
        assert feedback.next_retry_at is None
        assert email_mock.call_count == 0

    assert find_feedback_ids_for_retry() == []

@pytest.mark.django_db
def test_feedback_is_ready(
    feedback: Feedback
):

    assert feedback.status == Feedback.Status.PENDING
    assert feedback.next_retry_at is not None
    assert feedback.started_attempts_count == 0
    assert find_feedback_ids_for_retry() == [feedback.id]

class PageTests(TestCase):

    def test_submit_form(self):

        with patch(
            "apps.core.views.send_feedback_notification_task.delay",
            side_effect=KombuOperationalError("Ошибка redis")
        ) as mock_delay:
        
            feedback = {
                "last_name": "Луков",
                "first_name": "Михаил",
                "phone_number": "+79233243254",
                "privacy": True,
            }

            with self.captureOnCommitCallbacks(execute=True) as callback:

                response = self.client.post("/feedback/", data=feedback)

            self.assertEqual(len(callback), 1)

            self.assertEqual(Feedback.objects.count(), 1)

            self.assertEqual(response.status_code, 200)

            feedback_from_db = Feedback.objects.get(
                phone_number=feedback["phone_number"]
            )

            self.assertEqual(feedback_from_db.status, Feedback.Status.PENDING)
            self.assertEqual(feedback_from_db.started_attempts_count, 0)
            self.assertIsNone(feedback_from_db.processing_token)
            self.assertIsNone(feedback_from_db.processing_expires_at)
            self.assertEqual(feedback_from_db.last_name, feedback["last_name"])
            self.assertEqual(feedback_from_db.first_name, feedback["first_name"])
            feedback_ids = find_feedback_ids_for_retry()
            self.assertIn(feedback_from_db.id, feedback_ids)
            mock_delay.assert_called_once_with(feedback_from_db.id)

@pytest.mark.django_db(transaction=True)
def test_feedback_dispatch_after_commit(
    client
):
    with patch(
        "apps.core.views.send_feedback_notification_task.delay",
        
    ) as mock_delay:
        
        with transaction.atomic():
            feedback = {
                "last_name": "Луков",
                "first_name": "Михаил",
                "phone_number": "+79233243254",
                "privacy": True,
            }

            
            client.post("/feedback/", data=feedback)
            assert Feedback.objects.count() == 1
            mock_delay.assert_not_called()

        feedback_db = Feedback.objects.get(phone_number=feedback["phone_number"])
        mock_delay.assert_called_once_with(feedback_db.id)

@pytest.mark.django_db(transaction=True)
def test_feedback_dispatch_after_rollback(
    client
):

    with patch(
        "apps.core.views.send_feedback_notification_task.delay",
    ) as mock_delay:
        
        with pytest.raises(RuntimeError):
            
            feedback = {
                "last_name": "Луков",
                "first_name": "Михаил",
                "phone_number": "+79233243254",
                "privacy": True,
            }

            with transaction.atomic():
            
                client.post("/feedback/", data=feedback)
                assert Feedback.objects.count() == 1
                mock_delay.assert_not_called()
                raise RuntimeError()
            
        assert Feedback.objects.count() == 0
        mock_delay.assert_not_called()

@pytest.mark.django_db
def test_send_feedback_notification_task_soft_time_limit(
    feedback: Feedback
):


    
    with patch(
        "apps.core.tasks.send_mail",
        side_effect=SoftTimeLimitExceeded("Задача задерживается")
    ) as mock_mail:

        before_time = timezone.now() + timedelta(minutes=5)

        assert not send_feedback_notification_task(feedback_id=feedback.id)

        after_time = timezone.now() + timedelta(minutes=5)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.PENDING
        assert feedback.started_attempts_count == 1
        assert feedback.next_retry_at > before_time
        assert feedback.next_retry_at <= after_time
        assert feedback.processing_expires_at is None
        assert feedback.processing_token is None
        assert feedback.last_error == "SoftTimeLimitExceeded('Задача задерживается',)"
        mock_mail.assert_called_once()

@pytest.mark.django_db
def test_send_feedback_notification_task_client_email_error(
    caplog,
    feedback: Feedback
):

    feedback.email = "test@example.com"
    feedback.save()

    with patch(
        "apps.core.tasks.send_mail",
        side_effect=[
            1,
            SMTPException("Client email error")
        ]
    ) as mock_email:

        send_feedback_notification_task(feedback_id=feedback.id)

        feedback.refresh_from_db()

        assert feedback.status == Feedback.Status.SENT
        assert feedback.started_attempts_count == 1
        assert feedback.processing_token is None
        assert feedback.processing_expires_at is None
        assert mock_email.call_count == 2
        assert feedback.next_retry_at is None
        assert "Client email error" in caplog.text

