# Generated by Django 2.2 on 2019-05-13 12:16

import ateliersoude.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='picture',
            field=models.ImageField(default='', upload_to='organizations/', validators=[ateliersoude.utils.validate_image], verbose_name='Image'),
            preserve_default=False,
        ),
    ]
