from django.contrib import admin

from .models import InboundEmail


@admin.register(InboundEmail)
class InboundEmailAdmin(admin.ModelAdmin):
    list_display = ("from_email", "subject", "user", "tag", "mailbox_hash", "created_at")
    list_filter = ("user", "tag", "created_at")
    search_fields = ("from_email", "from_name", "subject", "message_id", "mailbox_hash")
    ordering = ("-created_at",)
    readonly_fields = (
        "id", "user", "message_id", "from_email", "from_name", "to", "cc", "bcc",
        "subject", "text_body", "html_body", "stripped_reply",
        "tag", "mailbox_hash", "headers", "date", "raw_payload", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
