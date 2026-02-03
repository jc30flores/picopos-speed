from django.contrib import admin
from apps.core.models import FeatureFlag


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "is_enabled")
    search_fields = ("key", "label")
