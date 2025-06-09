from django.db import models


class TelegramUser(models.Model):
    chat_id = models.BigIntegerField(unique=True, verbose_name='Chat ID', help_text='Обязательное поле.')
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name='Имя')
    active_notify = models.BooleanField(default=False, blank=False, verbose_name='Активность уведомлений')
    admin = models.BooleanField(default=False, blank=False, verbose_name='Доступ администратора')
    created_at = models.DateField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return f'Telegram User: {self.username} (Chat ID: {self.chat_id})'

    class Meta:
        db_table = 'telegramuser'
        verbose_name = 'Пользователь бота'
        verbose_name_plural = 'Пользователи бота'
        db_table_comment = 'Таблица для хранения информации о пользователях Телеграмм-бота.'