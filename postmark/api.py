from rest_framework import mixins, serializers, viewsets

from .models import InboundEmail


class InboundEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = InboundEmail
        fields = [
            "id",
            "message_id",
            "from_email",
            "from_name",
            "to",
            "cc",
            "bcc",
            "subject",
            "text_body",
            "html_body",
            "stripped_reply",
            "tag",
            "mailbox_hash",
            "date",
            "created_at",
        ]
        read_only_fields = fields


class InboxViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Authenticated user's inbox.

    list   – GET    /api/inbox/       → emails routed to the current user
    detail – GET    /api/inbox/{id}/  → single email (must belong to user)
    delete – DELETE /api/inbox/{id}/  → delete an email from user's inbox
    """

    serializer_class = InboundEmailSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return InboundEmail.objects.filter(user=self.request.user)
