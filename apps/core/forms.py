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
                    'placeholder': "Текст сообщения",
                    'class': "form_message"
                }
            ),
            'last_name': forms.TextInput(
                attrs={
                    'placeholder': "Фамилия",
                    'class': "form_last_name"
                }
            ),
            'first_name': forms.TextInput(
                attrs={
                    'placeholder': "Имя",
                    'class': "form_first_name"
                }
            ),
            'middle_name': forms.TextInput(
                attrs={
                    'placeholder': "Отчество",
                    'class': "form_middle_name"
                }
            ),
            'phone_number': forms.TextInput(
                attrs={
                    'placeholder': "Номер телефона",
                    'class': "form_phone"
                }
            ),
            'email': forms.TextInput(
                attrs={
                    'placeholder': "Адрес электронной почты",
                    'class': "form_email"
                }
            ),
            'privacy': forms.CheckboxInput(
                attrs={
                    'required':True,
                    'class': "form_privacy"
                }
            )
        }

        labels = {
            'last_name': "",
            'first_name': "", 
            'middle_name': "", 
            'phone_number': "",
            'email': "", 
            'text': "", 
            'privacy': 'Нажимая кнопку «Отправить», я даю свое согласие на обработку моих персональных данных'
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        allowed_chars = set('0123456789+() -')
        if not all(c in allowed_chars for c in phone):
            raise forms.ValidationError("Неверный формат номера телефона")     
        return phone