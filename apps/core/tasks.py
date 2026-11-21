from celery import shared_task
from apps.core.models import Feedback, Contacts
from config import settings
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone
from django.db import transaction, OperationalError
import uuid
from smtplib import SMTPException

def catch_bid(
    feedback_id: int
):

    try:
        with transaction.atomic():

            feedback = Feedback.objects.select_for_update(nowait=True).get(id=feedback_id)
            if (feedback.status != Feedback.Status.PENDING 
                or (feedback.next_retry_at and timezone.now() < feedback.next_retry_at) 
                or feedback.started_attempts_count >= 5
            ):
                return None
            feedback.status = Feedback.Status.PROCESSING
            feedback.started_attempts_count += 1
            feedback.processing_expires_at = timezone.now() + timedelta(minutes=5)
            feedback.processing_token = uuid.uuid4()
            feedback.save()
            return feedback.processing_token

    except OperationalError as e:

            pgcode = getattr(e.__cause__, 'pgcode', None)

            if pgcode == '55P03':
                return None
            else:
                raise

    except Feedback.DoesNotExist:
        raise 

def mark_feedback_as_sent(
    feedback_id: int,
    processing_token: uuid.UUID
):

    with transaction.atomic():

        feedback = Feedback.objects.select_for_update(nowait=True).get(id=feedback_id)
        
        if (feedback.status != Feedback.Status.PROCESSING):
            return False
        
        if (feedback.processing_token != processing_token):
            return False
        
        feedback.status = Feedback.Status.SENT
        feedback.processing_token = None
        feedback.processing_expires_at = None
        feedback.save()
        
        return True

def set_feedback_status_next_retry(
    feedback: Feedback,
    error: str
):
    feedback.last_error = error

    if (feedback.started_attempts_count < 5 and feedback.started_attempts_count > 0):
        feedback.status = Feedback.Status.PENDING

        match feedback.started_attempts_count:
            case 1:
                feedback.next_retry_at = timezone.now() + timedelta(minutes=5)
            case 2:
                feedback.next_retry_at = timezone.now() + timedelta(minutes=15)
            case 3:
                feedback.next_retry_at = timezone.now() + timedelta(hours=1)
            case 4:
                feedback.next_retry_at = timezone.now() + timedelta(hours=6)
    else:
        
        feedback.status = Feedback.Status.FAILED
        feedback.next_retry_at = None

    feedback.processing_expires_at = None
    feedback.processing_token = None

    

def check_unsuccessful_sent_attempt(
    feedback_id: int,
    processing_token: uuid.UUID,
    error: str
):

    with transaction.atomic():

        feedback = Feedback.objects.select_for_update(nowait=True).get(id=feedback_id)

        if (feedback.processing_token != processing_token or feedback.status != Feedback.Status.PROCESSING):

            return False

        set_feedback_status_next_retry(feedback, error)

        feedback.save()

        return True
    
def task_recovery(
    feedback_id: int,
    error: str
):

    with transaction.atomic():

        feedback = Feedback.objects.select_for_update(nowait=True).get(id=feedback_id)

        if (feedback.status != Feedback.Status.PROCESSING):
            return False

        if (feedback.processing_expires_at is None or timezone.now() < feedback.processing_expires_at):
            return False

        set_feedback_status_next_retry(feedback, error)

        feedback.save()

        return True

@shared_task()
def send_feedback_notification_task(
    feedback_id
):

    try: 
        token = catch_bid(feedback_id=feedback_id)

        if token is None:
            return False

    except Feedback.DoesNotExist:

        return False

    try:

        feedback = Feedback.objects.get(id=feedback_id)

    except Feedback.DoesNotExist:
        return f"Заявка {feedback_id} не найдена в базе"

    contacts = Contacts.get_solo()

    admin_email = contacts.email or settings.DEFAULT_FROM_EMAIL

    subject_admin = f"Новая заявка №{feedback.id} от {feedback.last_name} {feedback.first_name}"
    message_admin = (
        f"Получена новая заявка с сайта!\n\n"
        f"ФИО: {feedback.last_name} {feedback.first_name} {feedback.middle_name or ''}\n"
        f"Телефон: {feedback.phone_number}\n"
        f"Email: {feedback.email or 'Не указан'}\n\n"
        f"Сообщение:\n{feedback.text or 'Без текста'}"
    )

    try:

        send_result = send_mail(
            subject=subject_admin,
            message=message_admin,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False
        )

        if (send_result == 0):
            check_unsuccessful_sent_attempt(
                feedback_id=feedback.id,
                processing_token=token,
                error="Send email error"
            )

            return False

        result = mark_feedback_as_sent(
            feedback_id=feedback_id,
            processing_token=token
        )

        if not result:
            return False

    except SMTPException:
        check_unsuccessful_sent_attempt(
            feedback_id=feedback.id,
            processing_token=token,
            error="Send email error"
        )
        return False

    if feedback.email:

        subject_client = f"Ваше обращение принято!"
        message_client = (
            f"Здравствуйте!\n\n"
            f"Спасибо за обращение. Мы получили ваше сообщение и свяжемся с вами в ближайшее время.\n\n"
            f"С уважением,\nКоманда Abis"
        )

        try: 
            send_mail(
                subject=subject_client,
                message=message_client,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[feedback.email],
                fail_silently=True
            )
        except Exception:
            pass

        return f"Письма по заявке #{feedback_id} успешно обработаны"

    

def find_stuck_feedback_ids():

    feedbacks_id = (Feedback.objects
                 .filter(status=Feedback.Status.PROCESSING)
                 .filter(processing_expires_at__lte=timezone.now())
                 .order_by('processing_expires_at', 'id')
                 .values_list("id" ,flat=True)[:100]
                )

    return list(feedbacks_id)

@shared_task(default_retry_delay=60)
def periodic_processing_task():

    stuck_tasks_ids = find_stuck_feedback_ids()

    succesfull_tasks_count = 0

    for task_id in stuck_tasks_ids:
        try:
            if (    
                task_recovery(
                    feedback_id=task_id,
                    error="Processing deadline exceeded"
                )
            ):
                succesfull_tasks_count += 1
        except OperationalError as e:
            pgcode = getattr(e.__cause__, 'pgcode', None) or getattr(e.__cause__, 'sqlstate', None)

            if pgcode == '55P03':
                continue
            else:
                raise
        except Feedback.DoesNotExist:
            continue


    return succesfull_tasks_count

def find_feedback_ids_for_retry():

    feedbacks = (Feedback.objects
                 .filter(status=Feedback.Status.PENDING)
                 .filter(next_retry_at__lte=timezone.now())
                 .filter(started_attempts_count__lt=5)
                 .order_by("next_retry_at", "id")
                 .values_list("id", flat=True)[:100]
                )    

    return list(feedbacks)

