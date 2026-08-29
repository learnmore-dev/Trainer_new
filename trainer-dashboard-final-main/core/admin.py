from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from django import forms

# Customize Django Admin Header
admin.site.site_header = "My Trainers Admin"
admin.site.site_title = "Trainers Admin Portal"
admin.site.index_title = "Welcome to the Admin Dashboard"

# Custom UserAdmin
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password', 'role')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'role', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )

    # IMPORTANT: Correct Media class
    class Media:
        css = {
            'all': ('core/admin.css',)
        }

# Register the User model
admin.site.register(User, CustomUserAdmin)