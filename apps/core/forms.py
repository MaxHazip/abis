from django import forms
from . import models

class FeedbackForm(forms.ModelForm):

    class Meta: 
        model = models.Feedback
        fields = [
            'last_name',
            'first_name', 
            'middle_name', 
            'phone_number',
            'email', 
            'text', 
            'privacy'
        ]
        widgets = {
            'text': forms.Textarea(
                attrs={
                    'rows':5,
                    'placeholder': "Текст сообщения"
                }
            ),
            'privacy': forms.CheckboxInput(
                attrs={
                    'required':True
                }
            )
        }

        labels = {
            'last_name': 'Фамилия',
            'first_name': 'Имя', 
            'middle_name': 'Отчество (При наличии)', 
            'phone_number': 'Номер телефона',
            'email': 'Адрес электронной почты', 
            'text': 'Текст сообщения', 
            'privacy': 'Согласие на обработку персональных данных'
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        allowed_chars = set('0123456789+() -')
        if not all(c in allowed_chars for c in phone):
            raise forms.ValidationError("Неверный формат номера телефона")
        
        return phone