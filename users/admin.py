import datetime

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as OriginalGroup
from django.shortcuts import render
from django.utils import timezone
from knox.models import AuthToken
from knox.settings import knox_settings

from .models import Group, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


# pretend group admin is in this app
admin.site.unregister(OriginalGroup)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    pass


# ---------------------------------------------------------------------------
# Knox AuthToken admin – easy token creation with one-time raw token display
# ---------------------------------------------------------------------------

def _default_expiry():
    if knox_settings.TOKEN_TTL:
        return timezone.now() + knox_settings.TOKEN_TTL
    return None


class AuthTokenAddForm(forms.ModelForm):
    """
    Admin add-form that delegates to Knox's ``AuthToken.objects.create()``
    so the raw token is generated, hashed, and persisted in one step.

    The raw token is stashed on the returned instance as ``_raw_token``
    so ``response_add`` can display it exactly once.
    """

    expiry = forms.SplitDateTimeField(
        initial=_default_expiry,
        required=False,
        label="Expires at",
        help_text="Leave blank for a non-expiring token.",
    )

    class Meta:
        model = AuthToken
        fields = ("user", "expiry")

    def save(self, commit=True):
        expiry_dt = self.cleaned_data.get("expiry")
        if expiry_dt is None:
            expiry = None
        else:
            expiry = expiry_dt - timezone.now()
            if expiry <= datetime.timedelta(0):
                raise forms.ValidationError("Expiry must be in the future.")

        instance, raw_token = AuthToken.objects.create(
            user=self.cleaned_data["user"],
            expiry=expiry,
        )
        instance._raw_token = raw_token
        # satisfy save_related → form.save_m2m()
        self.save_m2m = lambda: None
        return instance


# Unregister the bare-bones admin that ships with Knox (if loaded)
if admin.site.is_registered(AuthToken):
    admin.site.unregister(AuthToken)


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("token_key", "user", "created", "expiry")
    list_filter = ("created", "expiry")
    search_fields = ("user__username", "user__email", "token_key")
    ordering = ("-created",)

    form = AuthTokenAddForm
    autocomplete_fields = ("user",)

    def has_change_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("user", "expiry")
        return ("digest", "token_key", "user", "created", "expiry")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ("digest", "token_key", "user", "created", "expiry")

    def response_add(self, request, obj, post_url_continue=None):
        raw_token = getattr(obj, "_raw_token", None)
        if raw_token:
            messages.success(
                request,
                "Token created. Copy it now — it will NOT be shown again.",
            )
            context = {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Token created",
                "raw_token": raw_token,
                "instance": obj,
                "user": obj.user,
                "expiry": obj.expiry,
            }
            return render(
                request,
                "admin/knox/authtoken/token_created.html",
                context,
            )
        return super().response_add(request, obj, post_url_continue)
