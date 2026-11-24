from django.shortcuts import render
from django.views.generic import TemplateView
from . import models
from django.views.decorators.http import require_POST, require_GET
from . import forms
from django.shortcuts import render
from apps.core.tasks import send_feedback_notification_task
from redis.exceptions import ConnectionError
from kombu.exceptions import OperationalError
import logging

logger = logging.getLogger(__name__)


# Create your views here.
class MainView(TemplateView):
    template_name = 'base.html'

    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)

        context['product_group'] = models.ProductGroup.objects.exclude(image='')
        context['manufacturer'] = models.Manufacturer.objects.exclude(logo='')
        context['client'] = models.Client.objects.exclude(image='')
        context['form'] = forms.FeedbackForm()
        context['site_settings'] = models.SiteSettings.get_solo()
        context['contacts'] = models.Contacts.get_solo()
        context['slider'] = models.HeroSlider.objects.filter(is_active=True)

        return context

@require_POST
def submit_form(request):
    
    form = forms.FeedbackForm(request.POST)

    if form.is_valid():

        feedback = form.save()

        try:
        
            send_feedback_notification_task.delay(feedback.id)
        except (OperationalError, ConnectionError):

            logger.exception(f"Не удалось поставить задачу отправки уведомления в очередь (feedback_id={feedback.id})")
        finally:
            empty_form = forms.FeedbackForm()
    
            return render(
                request,
                'includes/feedback_form_partial.html',
                {
                    "form": empty_form,
                })
    
    return render(request, "includes/feedback_form_partial.html", {"form": form})