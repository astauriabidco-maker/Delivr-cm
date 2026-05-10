from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_add_mobile_payment'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('delivery__isnull', False),
                    ('status', 'COMPLETED')
                ),
                fields=('delivery', 'user', 'transaction_type'),
                name='unique_completed_delivery_wallet_tx'
            ),
        ),
    ]
