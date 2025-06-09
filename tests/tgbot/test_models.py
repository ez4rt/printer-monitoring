from django.test import TestCase
from tgbot.models import TelegramUser

class TelegramUserModelTest(TestCase):
    def setUp(self):
        self.user = TelegramUser.objects.create(
            chat_id=123456789,
            username='test_user',
            active_notify=True,
            admin=False
        )

    def test_user_creation(self):
        self.assertEqual(self.user.chat_id, 123456789)
        self.assertEqual(self.user.username, 'test_user')
        self.assertTrue(self.user.active_notify)
        self.assertFalse(self.user.admin)

    def test_str_method(self):
        self.assertEqual(str(self.user), 'Telegram User: test_user (Chat ID: 123456789)')

    def test_default_values(self):
        user_without_username = TelegramUser.objects.create(chat_id=987654321)
        self.assertIsNone(user_without_username.username)
        self.assertFalse(user_without_username.active_notify)
        self.assertFalse(user_without_username.admin)

    def test_unique_chat_id(self):
        with self.assertRaises(Exception):
            TelegramUser.objects.create(chat_id=123456789)

    def test_change_username(self):
        self.user.username = 'New Test User'
        self.assertEqual(self.user.username, 'New Test User')

    def test_telegram_users_meta(self):
        self.assertEqual(TelegramUser._meta.db_table, 'telegramuser')
        self.assertEqual(TelegramUser._meta.verbose_name, 'Пользователь бота')
        self.assertEqual(TelegramUser._meta.verbose_name_plural, 'Пользователи бота')
        self.assertEqual(TelegramUser._meta.db_table_comment,
                         'Таблица для хранения информации о пользователях Телеграмм-бота.')