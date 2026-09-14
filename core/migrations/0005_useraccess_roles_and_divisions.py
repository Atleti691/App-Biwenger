from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0004_useraccess_temporary_access')]

    operations = [
        migrations.AddField(
            model_name='useraccess',
            name='role',
            field=models.CharField(
                choices=[('viewer', 'Solo consulta'), ('collaborator', 'Colaborador'), ('admin', 'Administrador')],
                default='viewer',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='useraccess',
            name='editable_divisions',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
