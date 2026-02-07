from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as OriginalGroup

from .models import Group, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass


# pretend group admin is in this app
admin.site.unregister(OriginalGroup)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    pass
