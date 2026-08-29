from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('trainer', 'Trainer'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='trainer')

    # Unique employee ID — e.g. TRN-0001 for trainers, ADM-0001 for admins
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name='Employee ID',
        help_text='Auto-generated unique ID (e.g. TRN-0001)',
    )

    def is_trainer(self):
        return self.role == 'trainer'

    def is_admin(self):
        return self.role == 'admin'

    def save(self, *args, **kwargs):
        # Auto-generate employee_id on first save if not already set
        if not self.employee_id:
            super().save(*args, **kwargs)   # save first to get a PK
            prefix = 'ADM' if (self.is_superuser or self.role == 'admin') else 'TRN'
            self.employee_id = f"{prefix}-{self.pk:04d}"
            # Update only the employee_id column to avoid a full re-save loop
            User.objects.filter(pk=self.pk).update(employee_id=self.employee_id)
        else:
            super().save(*args, **kwargs)
