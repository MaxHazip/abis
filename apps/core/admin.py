from django.contrib import admin
from . import models
from django.utils.html import format_html
import os
from easy_thumbnails.files import get_thumbnailer

# Register your models here.
@admin.register(models.ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "logo_preview")
    search_fields = ("name",)

    def logo_preview(self, obj):
        if obj.image and os.path.exists(obj.image.path):
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />', 
                thumbnail.url
            )
        return "Нет логотипа"
    
    logo_preview.short_description = "Логотип"

@admin.register(models.ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(models.Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "logo_preview")
    search_fields = ("name",)

    def logo_preview(self, obj):
        if obj.image and os.path.exists(obj.image.path):
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />', 
                thumbnail.url
            )
        return "Нет логотипа"
    
    logo_preview.short_description = "Логотип"

@admin.register(models.Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "register", "logo_preview")
    list_filter = ("product_type", "register")
    search_fields = ("name", "website_link")

    def logo_preview(self, obj):
        if obj.logo and os.path.exists(obj.logo.path):
            thumbnail = get_thumbnailer(obj.logo).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />',
                thumbnail.url
            )
        return "Нет логотипа"
    
    logo_preview.short_description = "Логотип"

@admin.register(models.Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("id", "logo_preview")

    def logo_preview(self, obj):
        if obj.image and os.path.exists(obj.image.path):
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />', 
                thumbnail.url
            )
        return "Нет логотипа"
    
    logo_preview.short_description = "Логотип"

@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_group", "manufacturer")
    list_filter = ("product_group", "manufacturer")
    search_fields = ("name",)

@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type")
    list_filter = ("service_type",)
    search_fields = ("name",)

@admin.register(models.Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "middle_name", "phone_number", "email", "privacy" , "created_at")
    list_filter = ("created_at",)
    search_fields = ("last_name", "first_name", "middle_name" , "phone_number", "email")
    readonly_fields = ("last_name", "first_name", "middle_name", "phone_number", "email", "text", "privacy" , "created_at")
    date_hierarchy = "created_at"

@admin.register(models.SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name", "logo_preview", "seo_title")

    def logo_preview(self, obj):
        if obj.logo_header and os.path.exists(obj.logo_header.path):
            thumbnail = get_thumbnailer(obj.logo_header).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />', 
                thumbnail.url
            )
        return "Нет логотипа"
    
    logo_preview.short_description = "Логотип"

@admin.register(models.Contacts)
class ContactsAdmin(admin.ModelAdmin):
    list_display = ("address", "main_phone", "second_phone", "email", "work_hours")

@admin.register(models.HeroSlider)
class HeroSliderAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "logo_preview", "position", "is_active")

    def logo_preview(self, obj):
        if obj.image and os.path.exists(obj.image.path):
            thumbnail = get_thumbnailer(obj.image).get_thumbnail({"size": (50,50), "crop": True})
            return format_html(
                '<img src="{}" />',
                thumbnail.url
            )
        return "Нет логотипа"