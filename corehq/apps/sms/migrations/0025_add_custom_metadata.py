# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-23 18:43
from __future__ import unicode_literals

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0024_add_is_two_way'),
    ]

    operations = [
        migrations.CreateModel(
            name='VertexBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.AddField(
            model_name='queuedsms',
            name='custom_metadata',
            field=jsonfield.fields.JSONField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='sms',
            name='custom_metadata',
            field=jsonfield.fields.JSONField(default=None, null=True),
        ),
    ]
