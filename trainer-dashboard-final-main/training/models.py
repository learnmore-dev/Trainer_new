from django.db import models
from django.conf import settings
from django.utils import timezone

# =========================
# Batch Model
# =========================
class Batch(models.Model):

    BATCH_TYPE_CHOICES = [
        ('training', 'Training / Class'),
        ('other',    'Other Activity'),
    ]

    name = models.CharField(max_length=100)
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    start_date = models.DateField()
    total_hours = models.PositiveIntegerField()
    total_students = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    batch_type = models.CharField(
        max_length=20,
        choices=BATCH_TYPE_CHOICES,
        default='training'
    )

    def __str__(self):
        return self.name

    @property
    def student_count(self):
        return self.total_students

    @property
    def used_hours(self):
        return sum(s.hours_taken for s in self.sessions.all())

    @property
    def remaining_hours(self):
        return max(0, self.total_hours - self.used_hours)

    @property
    def delay_hours(self):
        if self.is_completed:
            return 0
        return max(0, self.used_hours - self.total_hours)

    @property
    def status_label(self):
        if self.is_completed:
            return 'completed'
        if self.delay_hours > 0:
            return 'delay'
        return 'ontime'


# =========================
# Work Session Model
# =========================
class WorkSession(models.Model):
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_date = models.DateField(default=timezone.now)
    hours_taken = models.PositiveIntegerField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.batch.name} - {self.session_date}"


# =========================
# Attendance Model
# =========================
class Attendance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    total_time = models.DurationField(null=True, blank=True)
    login_lat = models.FloatField(null=True, blank=True)
    login_lon = models.FloatField(null=True, blank=True)
    logout_lat = models.FloatField(null=True, blank=True)
    logout_lon = models.FloatField(null=True, blank=True)
    login_address = models.TextField(blank=True)
    logout_address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_total_time(self):
        if self.login_time and self.logout_time:
            return self.logout_time - self.login_time
        return None

    def save(self, *args, **kwargs):
        if self.login_time and self.logout_time:
            self.total_time = self.calculate_total_time()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.login_time.date() if self.login_time else 'No login'}"


# =========================
# Trainer Attendance Model
# =========================
class TrainerAttendance(models.Model):

    DAY_STATUS_CHOICES = [
        ('present',  'Present'),
        ('half_day', 'Half Day'),
        ('leave',    'Leave'),
        ('pending',  'Pending'),
    ]

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    date = models.DateField()
    mark_in_time = models.DateTimeField(null=True, blank=True)
    mark_out_time = models.DateTimeField(null=True, blank=True)
    working_duration = models.DurationField(null=True, blank=True)
    photo_in = models.ImageField(upload_to="attendance/in/", null=True, blank=True)
    photo_out = models.ImageField(upload_to="attendance/out/", null=True, blank=True)
    latitude = models.CharField(max_length=50, null=True, blank=True)
    longitude = models.CharField(max_length=50, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    day_status = models.CharField(
        max_length=20,
        choices=DAY_STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['trainer', 'date']
        ordering = ['-date', '-mark_in_time']

    def __str__(self):
        return f"{self.trainer.username} - {self.date}"


# =========================
# Leave Model — UPDATED
# =========================

# ─── 2026 Optional Holiday List ───
OPTIONAL_HOLIDAYS_2026 = [
    ('2026-01-14', 'Makar Sankranti'),
    ('2026-02-15', 'Maha Shivratri'),
    ('2026-03-04', 'Holi'),
    ('2026-03-19', 'Ugadi'),
    ('2026-03-21', 'Eid-ul-Fitr'),
    ('2026-03-26', 'Ram Navami'),
    ('2026-08-28', 'Raksha Bandhan'),
    ('2026-09-04', 'Janmashtami'),
    ('2026-10-12', 'Diwali'),
    ('2026-10-20', 'Vijayadashami / Dusshera'),
    ('2026-12-25', 'Christmas'),
]

# ─── 2026 Mandatory Holiday List ───
MANDATORY_HOLIDAYS_2026 = [
    ('2026-01-26', 'Republic Day'),
    ('2026-05-01', 'Labour Day'),
    ('2026-08-15', 'Independence Day'),
    ('2026-10-02', 'Gandhi Jayanti'),
    ('2026-11-01', 'Karnataka Rajyotsava'),
]

OPTIONAL_HOLIDAY_LIMIT_PER_YEAR = 5
CASUAL_LEAVE_LIMIT_PER_MONTH    = 1


class Leave(models.Model):

    LEAVE_TYPE_CHOICES = [
        ('sick',              'Sick Leave'),
        ('casual',            'Casual Leave'),
        ('emergency',         'Emergency Leave'),
        ('weekoff',           'Week Off'),
        ('optional_holiday',  'Optional Holiday'),
        ('mandatory_holiday', 'Mandatory Holiday'),
        ('other',             'Other'),
    ]

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    trainer     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leaves'
    )
    leave_date   = models.DateField()
    leave_type   = models.CharField(max_length=30, choices=LEAVE_TYPE_CHOICES, default='casual')
    # For optional_holiday — store which festival was selected
    holiday_name = models.CharField(max_length=100, blank=True)
    reason       = models.TextField()
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note   = models.TextField(blank=True)
    applied_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_at']
        unique_together = ['trainer', 'leave_date']

    def __str__(self):
        return f"{self.trainer.username} - {self.leave_date} ({self.get_status_display()})"

    def get_leave_badge(self):
        """Returns emoji + label for dashboard display"""
        badges = {
            'sick':              ('🤒', 'Sick Leave',        '#e53e3e'),
            'casual':            ('🏖️', 'Casual Leave',      '#3182ce'),
            'emergency':         ('🚨', 'Emergency Leave',   '#dd6b20'),
            'weekoff':           ('📅', 'Week Off',          '#805ad5'),
            'optional_holiday':  ('🎉', 'Optional Holiday',  '#38a169'),
            'mandatory_holiday': ('🏛️', 'Mandatory Holiday', '#2c7a7b'),
            'other':             ('📝', 'Other Leave',       '#718096'),
        }
        return badges.get(self.leave_type, ('📝', self.get_leave_type_display(), '#718096'))