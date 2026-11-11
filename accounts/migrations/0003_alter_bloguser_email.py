from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_bloguser_options_remove_bloguser_created_time_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bloguser',
            name='email',
            field=models.EmailField(max_length=254, unique=True, verbose_name='email address'),
        ),
    ]
