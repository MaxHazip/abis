from celery import shared_task
from apps.core.models import Feedback, Contacts
from config import settings
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone
from django.db import transaction, OperationalError
import uuid

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_feedback_notification_task(
    self,
    feedback_id
):

    try:

        feedback = Feedback.objects.get(pk=feedback_id)

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
        send_mail(
            subject=subject_admin,
            message=message_admin,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc)

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

