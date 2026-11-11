from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0003_alter_oauthuser_nickname'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='oauthuser',
            constraint=models.UniqueConstraint(
                fields=('type', 'openid'),
                name='uniq_oauth_type_openid'),
        ),
    ]
