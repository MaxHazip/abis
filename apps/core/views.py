from django.shortcuts import render
from django.views.generic import TemplateView
from . import models
from django.views.decorators.http import require_POST, require_GET
from . import forms
from django.shortcuts import render


# Create your views here.
class MainView(TemplateView):
    template_name = 'base.html'

    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)

        context['product_group'] = models.ProductGroup.objects.all()
        context['manufacturer'] = models.Manufacturer.objects.all()
        context['service'] = models.Service.objects.select_related('service_type').all()
        context['media'] = models.Media.objects.all()
        context['product'] = models.Product.objects.select_related(
            'manufacturer',
            'product_group'
        ).prefetch_related('media').all()
        context['client'] = models.Client.objects.all()
        context['form'] = forms.FeedbackForm()
        context['site_settings'] = models.SiteSettings.objects.first()
        context['contacts'] = models.Contacts.objects.first()
        context['slider'] = models.HeroSlider.objects.filter(is_active=True)

        return context
    
    def main_page_view(request):
    # ... ваш существующий код для слайдеров и групп товаров ...
        context = {
            'site_settings': site_settings,
            'slider': slider,
            'product_group': product_group,
            'manufacturers': Manufacturer.objects.exclude(logo=''), # Передаем логотипы
        }
        return render(request, 'base.html', context)

@require_POST
def submit_form(request):
    
    form = forms.FeedbackForm(request.POST)

    if form.is_valid():

        form.save()

        empty_form = forms.FeedbackForm()

        return render(
            request,
            'includes/feedback_form_partial.html',
            {
                "form": empty_form,
                'feedback_text': "Спасибо! Заявка успешно отправлена, мы свяжемся с вами."
            })
    
    return render(request, "includes/feedback_form_partial.html", {"form": form, 'feedback_text': ""})