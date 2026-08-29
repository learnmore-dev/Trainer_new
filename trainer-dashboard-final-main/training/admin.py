from django.contrib import admin
from django.utils.html import format_html, mark_safe
from .models import Batch, WorkSession, Attendance, TrainerAttendance, Leave

# ================== WorkSession Inline ==================
class WorkSessionInline(admin.TabularInline):
    model = WorkSession
    extra = 0
    can_delete = False
    show_change_link = True
    
    readonly_fields = (
        'trainer',
        'session_date',
        'hours_taken',
        'description',
    )

# ================== Batch Admin ==================
@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'trainer',
        'start_date',
        'total_hours',
        'student_count',
        'used_hours_display',
        'remaining_hours_display',
        'delay_hours_display',
        'status_badge',
    )
    
    list_filter = ('trainer', 'start_date')
    ordering = ('start_date',)
    search_fields = ('name', 'trainer__username')
    inlines = [WorkSessionInline]
    
    @admin.display(description="Used Hours")
    def used_hours_display(self, obj):
        return obj.used_hours
    
    @admin.display(description="Remaining Hours")
    def remaining_hours_display(self, obj):
        return max(0, obj.remaining_hours)
    
    @admin.display(description="Delay Hours")
    def delay_hours_display(self, obj):
        return obj.delay_hours
    
    @admin.display(description="Status")
    def status_badge(self, obj):
        # ✅ FIX: format_html() requires {} placeholder with a dynamic argument
        # For dynamic value (delay hours) → format_html() with {}
        # For fully static HTML → mark_safe()
        if obj.delay_hours > 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">🔴 DELAY ({} h)</span>',
                obj.delay_hours
            )
        return mark_safe('<span style="color: green; font-weight: bold;">🟢 ON TRACK</span>')


# ================== WorkSession Admin ==================
@admin.register(WorkSession)
class WorkSessionAdmin(admin.ModelAdmin):
    list_display = (
        'trainer',
        'batch',
        'session_date',
        'hours_taken',
        'description',
    )
    
    list_filter = ('batch', 'trainer', 'session_date')
    search_fields = ('trainer__username', 'batch__name', 'description')
    ordering = ('-session_date',)

# ================== Attendance Admin ==================
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'login_time',
        'logout_time',
        'login_address',
        'total_time_display',
    )
    
    list_filter = ('login_time', 'user')
    search_fields = ('user__username', 'login_address', 'logout_address')
    readonly_fields = ('total_time',)
    
    @admin.display(description='Total Time')
    def total_time_display(self, obj):
        if obj.total_time:
            seconds = obj.total_time.total_seconds()
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        return "N/A"

# ================== Trainer Attendance Admin ==================
@admin.register(TrainerAttendance)
class TrainerAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "trainer",
        "date",
        "mark_in_time",
        "mark_out_time",
        "working_duration_display",
        "photo_in_preview",
        "photo_out_preview",
    )
    
    readonly_fields = (
        "photo_in_preview",
        "photo_out_preview",
        "working_duration_display",
    )
    
    list_filter = ("date", "trainer")
    search_fields = ("trainer__username", "date")
    ordering = ("-date", "-mark_in_time")
    
    # ✅ Correct — {} placeholder with dynamic .url value
    def photo_in_preview(self, obj):
        if obj.photo_in:
            return format_html(
                '<img src="{}" width="80" height="80" style="border-radius:8px;" />',
                obj.photo_in.url
            )
        return mark_safe('<span style="color:#999;">No Photo</span>')
    
    photo_in_preview.short_description = "Photo In"
    
    def photo_out_preview(self, obj):
        if obj.photo_out:
            return format_html(
                '<img src="{}" width="80" height="80" style="border-radius:8px;" />',
                obj.photo_out.url
            )
        return mark_safe('<span style="color:#999;">No Photo</span>')
    
    photo_out_preview.short_description = "Photo Out"
    
    @admin.display(description="Working Duration")
    def working_duration_display(self, obj):
        if obj.working_duration:
            total_seconds = int(obj.working_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "--"


# ================== Leave Admin ==================
@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display  = ('trainer', 'leave_date', 'leave_type', 'reason_short', 'status', 'status_badge', 'applied_at')
    list_filter   = ('status', 'leave_type', 'leave_date')
    search_fields = ('trainer__username', 'trainer__first_name', 'reason')
    ordering      = ('-applied_at',)
    list_editable = ('status',)

    def reason_short(self, obj):
        return obj.reason[:60] + '...' if len(obj.reason) > 60 else obj.reason
    reason_short.short_description = 'Reason'

    def status_badge(self, obj):
        colors = {
            'pending':  ('orange', '⏳'),
            'approved': ('green',  '✅'),
            'rejected': ('red',    '❌'),
        }
        color, icon = colors.get(obj.status, ('#333', ''))
        return format_html(
            '<span style="color:{}; font-weight:bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Status'