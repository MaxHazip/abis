from django.db import models
from solo.models import SingletonModel

# Create your models here.
class Manufacturer(models.Model):

    class Product_type(models.TextChoices):
        PRODUCT_TYPE_SOFTWARE = 'S', "ПО"
        PRODUCT_TYPE_COMPONENTS = 'C', "Железо"

    name = models.CharField(
        max_length=50, 
        blank=False, 
        null=False, 
        verbose_name="Название производителя"
    )
    website_link = models.URLField(
        max_length=500,
        blank=True, 
        null=True,
        verbose_name="Ссылка на сайт"
    )
    product_type = models.CharField(
        max_length=1,
        choices=Product_type.choices,
        default=Product_type.PRODUCT_TYPE_SOFTWARE,
        blank=False, 
        null=False,
        verbose_name="Тип продукта"
    )
    register = models.BooleanField(
        default=False, 
        blank=False, 
        null=False,
        verbose_name="Присутствие в регистре"
    )
    logo = models.ImageField(
        blank=False, 
        null=False,
        verbose_name="Логотип",
        upload_to="manufacturers/"
        
    )
    
    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"
        ordering = ['name']

    def __str__(self):
        return self.name
    
class ProductGroup(models.Model):
    name = models.CharField(
        verbose_name="Название группы продуктов",
        null=False,
        blank=False,
        max_length=50
    )
    image = models.ImageField(
        verbose_name="Изображение товарной группы",
        null=True,
        blank=True,
        upload_to="product_groups/"
    )

    class Meta:
        verbose_name = "Товарная группа"
        verbose_name_plural = "Товарные группы"
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Media(models.Model):
    image = models.ImageField(upload_to="products/", verbose_name="Медиа")

    class Meta:
        verbose_name = "Медиа"
        verbose_name_plural = "Медиа"

    def __str__(self):
        return str(self.id)
    
class Product(models.Model):
    name = models.CharField(
        verbose_name="Название продукта",
        max_length=100,
        null=False,
        blank=False
    )
    product_group = models.ForeignKey(
        ProductGroup,
        verbose_name="Товарная группа",
        null=True,
        blank=False,
        on_delete=models.SET_NULL
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        verbose_name="Производитель",
        null=True,
        blank=False,
        on_delete=models.SET_NULL
    )
    media = models.ManyToManyField(
        Media, 
        verbose_name="Медиа товара", 
        blank=True
    )
    popularity = models.PositiveIntegerField(
        default=0,
        verbose_name="Популярность товара",
        null=False,
        blank=False
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['popularity', 'name']

    def __str__(self):
        return self.name
    
class ServiceType(models.Model):
    name = models.CharField(
        verbose_name="Тип услуги", 
        max_length=50, 
        null=False, 
        blank=False
    )

    class Meta:
        verbose_name = "Тип услуги"
        verbose_name_plural = "Типы услуг"
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Service(models.Model):

    name = models.CharField(
        verbose_name="Название услуги", 
        max_length=50, 
        null=False, 
        blank=False
    )
    service_type = models.ForeignKey(
        ServiceType, 
        verbose_name="Тип услуги",
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    description = models.TextField(
        verbose_name="Описание услуги",
        blank=False,
        null=False        
    )
    popularity = models.PositiveIntegerField(
        default=0,
        verbose_name="Популярность услуги",
        blank=False,
        null=False
    )

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ['popularity', 'name']

    def __str__(self):
        return self.name
    

class Client(models.Model):
    name = models.CharField(
        verbose_name="Название клиента", 
        max_length=50,
        null=False,
        blank=False
    )

    image = models.ImageField(
        upload_to="clients/",
        verbose_name="Логотип клиента"
    )

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Feedback(models.Model):
    last_name = models.CharField(
        verbose_name="Фамилия",
        max_length=70,
        null=False,
        blank=False
        )
    first_name = models.CharField(
        verbose_name="Имя",
        max_length=70,
        null=False,
        blank=False
    )
    middle_name = models.CharField(
        verbose_name="Отчество",
        max_length=70,
        null=True,
        blank=True
    )
    phone_number = models.CharField(
        verbose_name="Номер телефона",
        max_length=30,
        null=False,
        blank=False
    )
    email = models.EmailField(
        verbose_name="Почта",
        null=True,
        blank=True
    )
    text = models.TextField(
        verbose_name="Текст сообщения",
        null=True,
        blank=True
    )
    privacy = models.BooleanField(
        verbose_name="Подтверждение на обработку персональных данных",
        null=False,
        blank=False
    )
    created_at = models.DateTimeField(
        verbose_name="Время отправки",
        null=False,
        blank=False,
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Обратная связь клиента"
        verbose_name_plural = "Обратная связь"
        ordering = ['created_at']

    def __str__(self):
        return self.last_name
    
class SiteSettings(SingletonModel):
    site_name = models.CharField(
        verbose_name="Название сайта",
        max_length=100,
        default="Моя компания"
    )
    logo_header = models.FileField(
        upload_to="settings/",
        verbose_name="Логотип"
    )
    copyright_text = models.TextField(
        verbose_name="Текст копирайта", 
        default="© 2026 Все права защищены", 
        max_length=255
    
    )
    seo_title = models.CharField(
        verbose_name="Зоголовок в теге title",
        max_length=50,
        blank=True
    )
    seo_description = models.TextField(
        verbose_name="Главный SEO Description",
        blank=True
    )

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Общие настройки"
    
class Contacts(SingletonModel):
    address = models.CharField(
        verbose_name="Адрес офиса", 
        max_length=255
    )
    main_phone = models.CharField(
        verbose_name="Основной номер телефона", 
        max_length=30
    )
    second_phone = models.CharField(
        verbose_name="Дополнительный номер", 
        max_length=30
    )
    email = models.EmailField(
        verbose_name="Адрес электронной почты"
    )
    work_hours = models.CharField(
        verbose_name="Часы работы", 
        max_length=100
    )

    map_code = models.TextField(
        verbose_name="Код интерактивной карты",
        blank=True,
        null=True,
        help_text="Вствьте iframe или скрипт карты из конструктора карт"
    )

    class Meta:
        verbose_name = "Контакты компании"
        verbose_name_plural = "Контакты компании"

    def __str__(self):
        return "Контакты"

class HeroSlider(models.Model):
    title = models.CharField(
        max_length=50, 
        verbose_name="Заголовок на баннере",
        blank=True,
        null=True
    )
    subtitle = models.TextField(
        max_length=255,
        verbose_name="Описание",
        null=True,
        blank=True
    )
    image = models.ImageField(
        upload_to="slider",
        verbose_name="Фоновое изображение"
    )
    position = models.PositiveIntegerField(
        default=0,
        verbose_name="Поизиция в слайдере"
    )
    is_active = models.BooleanField(
        verbose_name="Активен",
        default=True
    )
    link = models.URLField(
        max_length=500,
        blank=True, 
        null=True,
        verbose_name="Ссылка на сайт"
    )

    class Meta:
        verbose_name = "Слайд на главной"
        verbose_name_plural = "Слайды на главной"
        ordering = ["position"]

    def __str__(self):
        if self.title:
            return self.title
        return "Нет названия"
        
        
