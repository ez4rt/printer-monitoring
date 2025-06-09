from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(help_text='Обязательное поле.', unique=True, verbose_name='Chat ID')),
                ('username', models.CharField(blank=True, max_length=100, null=True, verbose_name='Имя')),
                ('active_notify', models.BooleanField(default=False, verbose_name='Активность уведомлений')),
                ('admin', models.BooleanField(default=False, verbose_name='Доступ администратора')),
                ('created_at', models.DateField(auto_now_add=True, verbose_name='Дата создания')),
            ],
            options={
                'verbose_name': 'Пользователь бота',
                'verbose_name_plural': 'Пользователи бота',
                'db_table': 'telegramuser',
                'db_table_comment': 'Таблица для хранения информации о пользователях Телеграмм-бота.',
            },
        ),
    ]
