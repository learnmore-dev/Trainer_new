from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='employee_id',
            field=models.CharField(
                blank=True,
                help_text='Auto-generated unique ID (e.g. TRN-0001)',
                max_length=20,
                null=True,
                unique=True,
                verbose_name='Employee ID',
            ),
        ),
    ]
