from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_alter_user_business_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='activation_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Code à usage unique pour activer l'application coursier.",
                max_length=32,
                null=True,
                unique=True,
                verbose_name="Code d'activation mobile",
            ),
        ),
    ]
