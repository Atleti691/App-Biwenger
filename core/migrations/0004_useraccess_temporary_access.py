from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0003_jornadaregistro_division_cambioregistro')]

    operations = [
        migrations.AddField(
            model_name='useraccess',
            name='is_viewer',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='useraccess',
            name='access_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
