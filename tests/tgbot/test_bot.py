import telegram.ext
from django.test import TestCase
from telegram.ext import Application, CommandHandler
from unittest.mock import MagicMock, Mock, patch
from decouple import config
from tgbot.management.commands.bot import (start, help_command_main, end_input, start_notifications, stop_notifications,
                                           status, update_allowed_users, callback_update_user, printers, events,
                                           supplies, help_command, start_over, end, get_field_name,
                                           wrap_text, handle_text_input_printer, handle_text_input_supplies,
                                           handle_text_input_printer_events, all_printers, single_printer, all_events,
                                           single_printer_events, events_supplies, all_supplies, single_supplies,
                                           init_first_users, check_supplies_every_3days, check_supplies_every_7_days,
                                           check_supplies_every_2_weeks)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, JobQueue
from unittest.mock import AsyncMock
from tgbot.models import TelegramUser
from asgiref.sync import sync_to_async
import re
from tests.monitoring.test_models import BaseSetUpPrinterModelTest, SupplyDetailsModelTest, PrinterErrorModelTest
from datetime import timedelta


class TestGetFieldName(TestCase):
    def test_valid_fields(self):
        self.assertEqual(get_field_name('ip_address'), 'IP-адрес')
        self.assertEqual(get_field_name('stamp'), 'Марка')
        self.assertEqual(get_field_name('model'), 'Модель')
        self.assertEqual(get_field_name('serial_number'), 'Серийный номер')
        self.assertEqual(get_field_name('location'), 'Местоположение')

    def test_invalid_field(self):
        self.assertEqual(get_field_name('unknown_field'), 'unknown_field')

    def test_edge_cases(self):
        self.assertEqual(get_field_name(''), '')
        self.assertEqual(get_field_name(None), None)


class TestWrapText(TestCase):
    def test_wrap_text_basic(self):
        self.assertEqual(wrap_text("Hello, world!", 5), "Hello\n, wor\nld!")

    def test_wrap_text_exact_width(self):
        self.assertEqual(wrap_text("Hello", 5), "Hello")

    def test_wrap_text_longer_width(self):
        self.assertEqual(wrap_text("Hello", 10), "Hello")

    def test_wrap_text_empty_string(self):
        self.assertEqual(wrap_text("", 5), "")

    def test_wrap_text_non_string_input(self):
        self.assertEqual(wrap_text(12345, 2), "12\n34\n5")

    def test_wrap_text_special_characters(self):
        self.assertEqual(wrap_text("Привет, мир!", 6), "Привет\n, мир!")

    def test_wrap_text_unicode(self):
        self.assertEqual(wrap_text("😊😊😊😊😊😊", 3), "😊😊😊\n😊😊😊")


class StartTelegramApp(TestCase):
    def setUp(self):
        token = config('TELEGRAM_BOT_TOKEN')
        self.application = Application.builder().token(token).build()


class StartTelegramAppUnauthenticatedUser(StartTelegramApp):
    def setUp(self):
        super().setUp()
        self.update = Mock(spec=Update)
        self.context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        self.update.message.from_user.first_name = 'Иван'
        self.update.message.from_user.last_name = 'Иванов'
        self.update.effective_chat.id = 123456789
        self.update.effective_user.id = 123456789


class StartTelegramBotAuthenticatedUser(StartTelegramAppUnauthenticatedUser):
    def setUp(self):
        super().setUp()
        self.test_user = TelegramUser(
            chat_id=987654321,
            username='example_user',
            active_notify=False,
            admin=False
        )
        self.test_user.save()

        self.mock_context = AsyncMock()
        self.mock_context.job.chat_id = 12345
        self.mock_context.bot.send_message = AsyncMock()

        self.update.message.from_user.first_name = 'Александр'
        self.update.message.from_user.last_name = 'Смирнов'
        self.update.effective_chat.id = 987654321
        self.update.effective_user.id = 987654321
        self.update.message.chat_id = 987654321
        self.update.effective_chat.full_name = 'Александр Смирнов'
        self.update.message.reply_text = AsyncMock()


class CreateTelegramBotTests(StartTelegramApp):
    def test_add_command_handlers(self):
        self.application.add_handler(CommandHandler('start', start))
        self.application.add_handler(CommandHandler('help', help_command_main))
        self.application.add_handler(CommandHandler('exit', end_input))
        self.application.add_handler(CommandHandler('start_notify', start_notifications))
        self.application.add_handler(CommandHandler('stop_notify', stop_notifications))
        self.application.add_handler(CommandHandler('status', status))
        self.application.add_handler(CommandHandler('update_allowed_users', update_allowed_users))

        self.assertEqual(len(self.application.handlers[0]), 7)
        self.assertEqual(self.application.handlers[0][0].callback, start)
        self.assertEqual(self.application.handlers[0][1].callback, help_command_main)
        self.assertEqual(self.application.handlers[0][2].callback, end_input)
        self.assertEqual(self.application.handlers[0][3].callback, start_notifications)
        self.assertEqual(self.application.handlers[0][4].callback, stop_notifications)
        self.assertEqual(self.application.handlers[0][5].callback, status)
        self.assertEqual(self.application.handlers[0][6].callback, update_allowed_users)
        for i in range(7):
            self.assertIsInstance(self.application.handlers[0][i], CommandHandler)

    def test_add_conversation_handlers(self):
        START_ROUTES, END_ROUTES = range(2)
        ONE, TWO, THREE, FOUR = range(4)
        self.conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                START_ROUTES: [
                    CallbackQueryHandler(printers, pattern="^" + str(ONE) + "$"),
                    CallbackQueryHandler(events, pattern="^" + str(TWO) + "$"),
                    CallbackQueryHandler(supplies, pattern="^" + str(THREE) + "$"),
                    CallbackQueryHandler(help_command, pattern="^" + str(FOUR) + "$"),
                ],
                END_ROUTES: [
                    CallbackQueryHandler(start_over, pattern="^" + str(ONE) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(TWO) + "$"),
                ],
            },
            fallbacks=[CommandHandler("start", start)],
        )
        self.assertEqual(len(self.conv_handler.entry_points), 1)
        self.assertEqual(len(self.conv_handler.states[0]), 4)  # START_ROUTES
        self.assertEqual(len(self.conv_handler.states[1]), 2)  # END_ROUTES
        expected_patterns_start_routes = [
            re.compile('^0$'), re.compile('^1$'), re.compile('^2$'), re.compile('^3$'),
        ]
        actual_patterns = [handler.pattern for handler in self.conv_handler.states[0]]
        self.assertListEqual(expected_patterns_start_routes, actual_patterns)
        expected_patterns_end_routes = [
            re.compile('^0$'), re.compile('^1$'),
        ]
        actual_patterns = [handler.pattern for handler in self.conv_handler.states[1]]
        self.assertListEqual(expected_patterns_end_routes, actual_patterns)


    def test_run_polling(self):
        self.application.run_polling = MagicMock()
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        self.application.run_polling.assert_called_once_with(allowed_updates=Update.ALL_TYPES)


class TelegramBotCommandHandlerUnauthenticatedUserTest(StartTelegramAppUnauthenticatedUser):
    async def test_help_command(self):
        self.update.message.reply_text = AsyncMock()

        await help_command_main(self.update, self.context)

        expected_text = (
            '📜 <b>Справка по работе бота.</b> <i>Я умею:</i>\n\n'
            '1️⃣ <u>Отслеживать:</u>\n'
            '➤ состояние всех зарегистрированных принтеров и их текущий статус;\n'
            '➤ информацию об остатках расходных материалах принтеров;\n'
            '➤ данные о всех событий, связанных с принтерами.\n'
            '✅ Для взаимодействия со мной нажмите /start 🚀\n '
            'ℹ️ Подробная инструкция по взаимодействию с ботом представлена в разделе ПОМОЩЬ.\n'
            '⚠️Для корректной работы взаимодействия с ботом всегда закрывайте приложение.\n\n'
            '2️⃣ <u>Отправлять уведомления о важных событиях, связанных с принтерами.</u>\n'
            '✅ Чтобы получать уведомления о новых событиях нажмите на /start_notify 🔔\n'
            '⛔ Чтобы отказаться от уведомлений - /stop_notify 🔕 \n\n'
            '3️⃣ <u>Выводить Ваш текущий статус о работающих функциях бота.</u>\n'
            '✅ Чтобы получить статус нажмите на /status 👨🏻‍💻\n\n'
            '4️⃣ <u>Обновлять список разрешенных пользователей бота.</u>\n'
            '✅ Чтобы обновить список нажмите на /update_allowed_users 🔄\n'
            '❗ Доступно только администраторам 🛡️\n\n'
            '😊 Хорошей работы❗'
        )

        self.update.message.reply_text.assert_awaited_once_with(text=expected_text, parse_mode='HTML')

    async def test_status_command(self):
        self.update.message.reply_text = AsyncMock()

        await status(self.update, self.context)

        expected_text = (
            '👨🏻‍💻 <b>СТАТУС</b>\n\n'
            'Имя пользователя: Иван Иванов\n'
            'CHAT ID: 123456789\n'
            'Доступ: Запрещен 🚫\n'
            'ℹ️ Для получения доступа обратитесь к администратору.'
        )

        self.update.message.reply_text.assert_awaited_once_with(text=expected_text, parse_mode='HTML')

    async def test_start_command(self):
        self.context.bot.send_message = AsyncMock()

        await start(self.update, self.context)

        expected_text = "У вас нет доступа к этому боту."

        self.context.bot.send_message.assert_awaited_once_with(chat_id=self.update.effective_chat.id,
                                                               text=expected_text)

    async def test_end_command(self):
        self.context.bot.send_message = AsyncMock()

        await end_input(self.update, self.context)

        expected_text = "У вас нет доступа к этому боту."

        self.context.bot.send_message.assert_awaited_once_with(chat_id=self.update.effective_chat.id,
                                                               text=expected_text)

    async def test_start_notifications_command(self):
        self.context.bot.send_message = AsyncMock()

        await start_notifications(self.update, self.context)

        expected_text = "У вас нет доступа к этому боту."

        self.context.bot.send_message.assert_awaited_once_with(chat_id=self.update.effective_chat.id,
                                                               text=expected_text)

    async def test_stop_notifications_command(self):
        self.context.bot.send_message = AsyncMock()

        await stop_notifications(self.update, self.context)

        expected_text = "У вас нет доступа к этому боту."

        self.context.bot.send_message.assert_awaited_once_with(chat_id=self.update.effective_chat.id,
                                                               text=expected_text)

    async def test_update_allowed_users_command(self):
        self.context.bot.send_message = AsyncMock()

        await update_allowed_users(self.update, self.context)

        expected_text = "У вас нет доступа к этому боту."

        self.context.bot.send_message.assert_awaited_once_with(chat_id=self.update.effective_chat.id,
                                                               text=expected_text)


class TelegramBotEndInputTests(StartTelegramBotAuthenticatedUser):
    async def test_end_input_already_ended(self):
        await callback_update_user(self.mock_context)

        await end_input(self.update, self.context)

        self.update.message.reply_text.assert_called_once_with("Приложение уже выключено.")

    async def test_end_input_success(self):
        await callback_update_user(self.mock_context)
        await start(self.update, self.context)

        update = Mock(spec=Update)
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        update.message.from_user.first_name = 'Александр'
        update.message.from_user.last_name = 'Смирнов'
        update.effective_chat.id = 987654321
        update.effective_user.id = 987654321
        update.message.chat_id = 987654321
        update.effective_chat.full_name = 'Александр Смирнов'
        update.message.reply_text = AsyncMock()

        await end_input(update, context)
        update.message.reply_text.assert_called_once_with("👋 Буду ждать новых встреч!")


class TelegramBotStatusCommandTests(StartTelegramBotAuthenticatedUser):
    async def test_user_status(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await status(self.update, self.context)

        expected_text = (
            '👨🏻‍💻 <b>СТАТУС</b>\n\n'
            'Имя пользователя: Александр Смирнов\n'
            'CHAT ID: 987654321\n'
            'Доступ: Разрешен ✅\n'
            'Права доступа: Пользователь 👤\n'
            'Приложение: Выключено 🔴\n'
            'Уведомления: Выключены 🔴'
        )

        self.update.message.reply_text.assert_awaited_once_with(text=expected_text, parse_mode='HTML')

    async def test_status_admin(self):
        self.test_user.admin = True
        await sync_to_async(self.test_user.save)()
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.test_user.admin, user_db.admin)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        self.update.message.from_user.first_name = 'Админ'

        await status(self.update, self.context)

        expected_text_admin = (
            '👨🏻‍💻 <b>СТАТУС</b>\n\n'
            'Имя пользователя: Админ Смирнов\n'
            'CHAT ID: 987654321\n'
            'Доступ: Разрешен ✅\n'
            'Права доступа: Администратор 🛡️\n'
            'Приложение: Выключено 🔴\n'
            'Уведомления: Выключены 🔴'
        )

        self.update.message.reply_text.assert_awaited_once_with(text=expected_text_admin, parse_mode='HTML')


class TelegramBotStartNotifyCommandTests(StartTelegramBotAuthenticatedUser):
    async def test_start_notify(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.test_user.active_notify, user_db.active_notify)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        context = AsyncMock()
        await start_notifications(self.update, context)
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)
        self.assertEqual(user_db.active_notify, True)
        expected_text = (
            '🥳 Поздравляю! Теперь вы получаете уведомления о важных событиях 🔔'
        )
        context.bot.send_message.assert_awaited_once_with(chat_id=self.update.message.chat_id,
                                                          text=expected_text)

        context_again = AsyncMock()
        await start_notifications(self.update, context_again)
        expected_text_again = (
            'Уведомления уже запущены!'
        )
        context_again.bot.send_message.assert_awaited_once_with(chat_id=self.update.message.chat_id,
                                                          text=expected_text_again)


class TelegramBotSendNotifyTest(TestCase):
    def setUp(self):
        self.mock_context = AsyncMock()
        self.mock_context.job.chat_id = 12345

        self.mock_printer = MagicMock()
        self.mock_printer.model = "HP LaserJet"
        self.mock_printer.get_subnet_name.return_value = "Subnet1"
        self.mock_printer.location = "1, отдел - IT"

        self.mock_supply = MagicMock()
        self.mock_supply.supply = "Черный"
        self.mock_supply.remaining_supply_percentage = 5
        self.mock_supply.printer = self.mock_printer

        self.mock_supply_details = MagicMock()
        self.mock_supply_details.supply = "Черный"
        self.mock_supply_details.qty = 10

    @patch('monitoring.models.PrinterSupplyStatus.objects.select_related')
    @patch('monitoring.models.Printer.objects.select_related')
    async def test_check_every_3days(self, mock_select_printer, mock_select_printer_supply):
        mock_select_printer.return_value.filter.return_value = [self.mock_printer]
        mock_select_printer_supply.return_value.filter.return_value = [self.mock_supply]

        await check_supplies_every_3days(self.mock_context)

        self.mock_context.bot.send_message.assert_called_once_with(
            chat_id=12345,
            text='📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
                 'Принтер: HP LaserJet\n'
                 'Местоположение: Subnet1, 1, отдел - IT\n'
                 'Остаток Черный - 5%',
            parse_mode='HTML',
        )

    @patch('monitoring.models.PrinterSupplyStatus.objects.select_related')
    @patch('monitoring.models.Printer.objects.select_related')
    async def test_check_every_7days(self, mock_select_printer, mock_select_printer_supply):
        mock_select_printer.return_value.filter.return_value = [self.mock_printer]
        mock_select_printer_supply.return_value.filter.return_value = [self.mock_supply]

        await check_supplies_every_7_days(self.mock_context)

        self.mock_context.bot.send_message.assert_called_once_with(
            chat_id=12345,
            text='📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
                 'Принтер: HP LaserJet\n'
                 'Местоположение: Subnet1, 1, отдел - IT\n'
                 'Остаток Черный - 5%',
            parse_mode='HTML',
        )

    @patch('monitoring.models.SupplyDetails.objects.select_related')
    async def test_check_every_2week(self, mock_select_supply_details):
        mock_select_supply_details.return_value.filter.return_value = [self.mock_supply_details]

        await check_supplies_every_2_weeks(self.mock_context)

        self.mock_context.bot.send_message.assert_called_once_with(
            chat_id=12345,
            text='📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
                 '<i>Низкие остатки расходных материалов</i>\n'
                 'Черный - 10шт.\n',
            parse_mode='HTML',
        )


class HandleTextInputPrinterTest(BaseSetUpPrinterModelTest):
    async def test_handle_text_input_printer_invalid_id(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '999'


        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer(update, context)

        expected_text = (
            '⚠️ Принтер с ID=999 отсутствует в списке. '
            'Пожалуйста, введите корректный ID принтера или нажмите на /exit, чтобы завершить работу.'
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_printer_invalid_text(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '!223sd'


        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer(update, context)

        expected_text = (
            '⚠️ Пожалуйста, введите корректный ID принтера или нажмите на /exit, чтобы завершить работу.'
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_printer_valid(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = str(self.printer.id)

        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer(update, context)

        str_text = str(update.message.reply_text.call_args[1])
        pattern = r"✅ <b>Вы выбрали принтер с ID - (\d+)</b>"
        match = re.search(pattern, str_text)
        expected_printer_id = int(match.group(1))
        self.assertEqual(self.printer.id, expected_printer_id)
        self.assertIn(str(self.printer.ip_address), str_text)
        self.assertIn(self.printer.model.name, str_text)
        self.assertIn(self.printer.model.stamp.name, str_text)
        self.assertIn(self.printer.serial_number, str_text)
        self.assertIn(self.printer.location.department.name, str_text)
        self.assertIn(self.printer.location.cabinet.number, str_text)


class HandleTextInputSuppliesTest(SupplyDetailsModelTest):
    async def test_handle_text_input_supplies_invalid_id(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '999'

        with patch('monitoring.models.SupplyDetails.objects.get', return_value=self.supply_details):
            await handle_text_input_supplies(update, context)

        expected_text = (
            "⚠️ Расходный материал с ID=999 отсутствует в списке. Пожалуйста, введите корректный ID "
            "или нажмите на /exit, чтобы завершить работу."
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_supplies_invalid_text(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '!223sd'

        with patch('monitoring.models.SupplyDetails.objects.get', return_value=self.supply_details):
            await handle_text_input_supplies(update, context)

        expected_text = (
            "⚠️ Пожалуйста, введите корректный ID расходного материала или нажмите на /exit, чтобы завершить работу."
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_supplies_valid(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = str(self.supply_details.id)

        with patch('monitoring.models.SupplyDetails.objects.get', return_value=self.supply_details):
            await handle_text_input_supplies(update, context)

        str_text = str(update.message.reply_text.call_args[1])
        pattern = r"✅ <b>Вы выбрали расходный материал с номером - (\d+)</b>"
        match = re.search(pattern, str_text)
        expected_supply_id = int(match.group(1))
        self.assertEqual(self.supply_details.id, expected_supply_id)
        self.assertIn(self.supply_details.supply.name, str_text)
        self.assertIn(str(self.supply_details.qty), str_text)
        self.assertIn(str(self.supply_details.supply.price), str_text)


class HandleTextInputEventsTest(PrinterErrorModelTest):
    async def test_handle_text_input_printer_events_invalid_id(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '999'

        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer_events(update, context)

        expected_text = (
            "⚠️ Принтер с ID=999 отсутствует в списке. Пожалуйста, введите корректный ID принтера "
            "или нажмите на /exit, чтобы завершить работу."
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_printer_events_invalid_text(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = '!223sd'


        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer_events(update, context)

        expected_text = (
            '⚠️ Пожалуйста, введите корректный ID принтера или нажмите на /exit, чтобы завершить работу.'
        )
        update.message.reply_text.assert_awaited_once_with(expected_text)

    async def test_handle_text_input_printer_events_valid(self):
        update = AsyncMock()
        context = MagicMock()
        update.message.text = str(self.printer.id)

        with patch('monitoring.models.Printer.objects.get', return_value=self.printer):
            await handle_text_input_printer_events(update, context)

        str_text = str(update.message.reply_text.call_args[1])
        pattern = r"✅ <b>Вы выбрали события принтера с номером - (\d+)</b>"
        match = re.search(pattern, str_text)
        expected_printer_id = int(match.group(1))
        self.assertEqual(self.printer.id, expected_printer_id)
        self.assertIn(self.printer_error.description, str_text)
        self.assertIn(str(self.printer), str_text)

        expected_datetime = self.printer_error.event_date + timedelta(hours=7)
        expected_date = expected_datetime.strftime("%Y/%m/%d")
        expected_time = expected_datetime.strftime("%H:%M")
        self.assertIn(expected_date, str_text)
        self.assertIn(expected_time, str_text)


class TelegramBotStartCommandTests(StartTelegramBotAuthenticatedUser):
    def setUp(self):
        super().setUp()
        (self.PRINTERS, self.EVENTS, self.EVENTS_SUPPLIES, self.SUPPLIES, self.SINGLE_OBJECT,
         self.ALL_OBJECTS, self.HELP, self.EXIT, self.GO_BACK_START) = range(9)

    async def test_start_command(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await start(self.update, self.context)
        expected_text = "👋 Доброго времени суток!\n"\
                        "Меня зовут 🖨️🧑‍🔧 *Принтер Мастер: Телеграм Бот Мониторинга Принтеров*. Я помогу Вам получить необходимую "\
                        "информацию. \n\n"\
                        "Какую информацию Вы хотите получить❓"

        actual_text = str(self.update.message.reply_text.call_args[0][0])

        self.assertEqual(actual_text, expected_text)

        inline_keyboard_markup = self.update.message.reply_text.call_args[1]['reply_markup'].inline_keyboard

        self.assertEqual(inline_keyboard_markup[0][0].text, '🖨️ Принтеры')
        self.assertEqual(inline_keyboard_markup[1][0].text, '📅 События')
        self.assertEqual(inline_keyboard_markup[2][0].text, '️📦 Расходные материалы')
        self.assertEqual(inline_keyboard_markup[3][0].text, '🆘 Помощь')
        self.assertEqual(inline_keyboard_markup[3][1].text, '🔚 Выход')

        self.assertEqual(inline_keyboard_markup[0][0].callback_data, str(self.PRINTERS))
        self.assertEqual(inline_keyboard_markup[1][0].callback_data, str(self.EVENTS))
        self.assertEqual(inline_keyboard_markup[2][0].callback_data, str(self.SUPPLIES))
        self.assertEqual(inline_keyboard_markup[3][0].callback_data, str(self.HELP))
        self.assertEqual(inline_keyboard_markup[3][1].callback_data, str(self.EXIT))

    async def test_route_printers(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await start(self.update, self.context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        query.data = str(self.PRINTERS)
        await printers(self.update, self.context)

        query.edit_message_text.assert_called_once_with(
            text="🖨️ *ПРИНТЕРЫ*\n\n"
                 "🤔 Пожалуйста, выберите необходимую опцию.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🖨️🖨️🖨️ Все принтеры", callback_data=str(self.ALL_OBJECTS))],
                [InlineKeyboardButton("🖨️ Конкретный принтер", callback_data=str(self.SINGLE_OBJECT))],
                [InlineKeyboardButton("🔙 Назад", callback_data=str(self.GO_BACK_START)),
                 InlineKeyboardButton("🔚 Выход", callback_data=str(self.EXIT))]
            ])
        )

        query_back = AsyncMock()
        query_back.answer = AsyncMock()
        self.update.callback_query = query_back
        query_back.data = str(self.GO_BACK_START)
        await start_over(self.update, self.context)

        query_back.edit_message_text.assert_called_once_with(
            text="🏠 Вы вернулись к началу!\n"
                 "Меня всё еще зовут 🖨️🧑‍🔧 *Принтер Мастер: Телеграм Бот Мониторинга Принтеров*. Я помогу Вам получить "
                 "необходимую информацию.\n\n"
                 "Какую информацию Вы хотите получить❓",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🖨️ Принтеры", callback_data=str(self.PRINTERS))],
                [InlineKeyboardButton("📅 События", callback_data=str(self.EVENTS))],
                [InlineKeyboardButton("📦 Расходные материалы", callback_data=str(self.SUPPLIES))],
                [
                    InlineKeyboardButton("🆘 Помощь", callback_data=str(self.HELP)),
                    InlineKeyboardButton("🔚 Выход", callback_data=str(self.EXIT)),
                ],
            ])
        )

    async def test_route_events(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await start(self.update, self.context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        query.data = str(self.EVENTS)
        await events(self.update, self.context)

        query.edit_message_text.assert_called_once_with(
            text="📅 *СОБЫТИЯ*\n\n"
                 "🤔 Пожалуйста, выберите необходимую опцию.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅📅📅 Все события", callback_data=str(self.ALL_OBJECTS)), ],
                [InlineKeyboardButton("📅🖨️ События принтера", callback_data=str(self.SINGLE_OBJECT)), ],
                [InlineKeyboardButton("📦🔄 Замена расходных материалов", callback_data=str(self.EVENTS_SUPPLIES)), ],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=str(self.GO_BACK_START)),
                    InlineKeyboardButton("🔚 Выход", callback_data=str(self.EXIT)),
                ],
            ])
        )

    async def test_route_supplies(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await start(self.update, self.context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        query.data = str(self.SUPPLIES)
        await supplies(self.update, self.context)

        query.edit_message_text.assert_called_once_with(
            text="📦 *РАСХОДНЫЕ МАТЕРИАЛЫ*\n\n"
                 "🤔 Пожалуйста, выберите необходимую опцию.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦📦📦 Все расходные материалы", callback_data=str(self.ALL_OBJECTS)), ],
                [InlineKeyboardButton("📦 Конкретный расходный материал", callback_data=str(self.SINGLE_OBJECT)), ],
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=str(self.GO_BACK_START)),
                    InlineKeyboardButton("🔚 Выход", callback_data=str(self.EXIT)),
                ],
            ])
        )

    async def test_route_help(self):
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=987654321)

        self.assertEqual(self.update.effective_chat.id, user_db.chat_id)

        await start(self.update, self.context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        query.data = str(self.HELP)
        await help_command(self.update, self.context)

        query.edit_message_text.assert_called_once_with(
            text="📜 <b>СПРАВКА</b>\n\n"
                 "1️⃣ Раздел <i>Принтеры</i> показывает общую информацию о всех принтерах или детальную информацию о "
                 "конкретном принтере.\n\n"
                 "2️⃣ Раздел <i>События</i> показывает список событий, связанных с принтерами (ошибки печати, замена "
                 "расходных материалов, внесение изменений в систему мониторинга).\n"
                 "➤ При выборе <u>Все события</u> отображается 35 последних произошедщих событий;\n"
                 "➤ При выборе <u>События принтера</u> отображается 10 последних произошедщих событий конкретного "
                 "принтера;\n"
                 "➤ При выборе событий <u>Замена расходных материалов</u> отображается 20 последних замен расходных "
                 "материалов \n\n"
                 "3️⃣ Раздел <i>Расходные материалы</i> показывает информацию об остатках расходных материалах для всех"
                 " принтеров.\n\n"
                 "4️⃣ Для того, чтобы вернуться к предыдущему окну нажмите <i>Назад</i>\n\n"
                 "5️⃣ Для возврата к стартовому окну нажмите <i>Вернуться к началу</i>\n\n"
                 "6️⃣ Для завершения взаимодействия с ботом нажмите <i>Выход</i>\n\n"
                 "ℹ️ В случае некоректного отображения таблиц необходимо перевернуть мобильное устройство или нажать на "
                 "☰ над таблицей при работе с компьютера.\n\n"
                 "🔢 Так как Telegram ограничивает длину сообщений, на некоторых страницах используется навигация по "
                 "отображаемым таблицам (максимальное число строк в таблице = 20).\n"
                 "✅ Навигация осуществляется с помощью кнопок ⬅️ и ➡️\n\n"
                 "⚠️ Для корректной работы всегда закрывайте приложение\n\n"
                 "😊 Хорошей работы❗",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔙 Назад", callback_data=str(self.GO_BACK_START)),
                    InlineKeyboardButton("🔚 Выход", callback_data=str(self.EXIT)),
                ]
            ])
        )

    async def test_route_end(self):
        await callback_update_user(self.mock_context)
        await start(self.update, self.context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        query.data = str(self.EXIT)
        await end(self.update, self.context)

        query.edit_message_text.assert_called_once_with(
            text="👋 Буду ждать новых встреч!",
        )


class TelegramBotPagesTests(StartTelegramBotAuthenticatedUser):
    def setUp(self):
        super().setUp()
        (self.PRINTERS, self.EVENTS, self.EVENTS_SUPPLIES, self.SUPPLIES, self.SINGLE_OBJECT,
         self.ALL_OBJECTS, self.HELP, self.EXIT, self.GO_BACK_START) = range(9)

    async def test_all_printers_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await all_printers(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('Вы выбрали все принтеры', str_text)

    async def test_single_printer_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await single_printer(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('ПРИНТЕР', str_text)
        self.assertIn('Введите ID принтера', str_text)

    async def test_all_events_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await all_events(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('Вы выбрали все события', str_text)
        self.assertIn('Выберите дальнейшее действие.', str_text)

    async def test_single_printer_events_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await single_printer_events(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('СОБЫТИЯ ПРИНТЕРА', str_text)
        self.assertIn('Введите ID принтера, согласно списку или нажмите на /exit, чтобы завершить работу.', str_text)

    async def test_events_supplies_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await events_supplies(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('Вы выбрали события замены расходных материалов', str_text)
        self.assertIn('Принтер', str_text)
        self.assertIn('РМ', str_text)
        self.assertIn('Время замены', str_text)

    async def test_all_supplies_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await all_supplies(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('Вы выбрали все расходные материалы', str_text)
        self.assertIn('Название', str_text)
        self.assertIn('Кол-во', str_text)
        self.assertIn('Принтер', str_text)
        self.assertIn('Для удобного отображения таблицы переверните устройство', str_text)

    async def test_single_supplies_page(self):
        await callback_update_user(self.mock_context)

        query = AsyncMock()
        query.answer = AsyncMock()
        self.update.callback_query = query

        await single_supplies(self.update, self.context)

        str_text = query.edit_message_text.call_args[1]['text']
        self.assertIn('РАСХОДНЫЙ МАТЕРИАЛ', str_text)
        self.assertIn('нажмите на /exit, чтобы завершить работу.', str_text)
        self.assertIn('Для удобного отображения таблицы переверните устройство', str_text)


class InitFirstUsersNotCalled(StartTelegramAppUnauthenticatedUser):
    def setUp(self):
        super().setUp()
        mock_job_queue = Mock()
        mock_job = Mock()
        mock_job_queue.jobs.return_value = [mock_job]

        self.mock_context = Mock()
        self.mock_context.job_queue = mock_job_queue
        self.mock_context.bot.send_message = AsyncMock()

    async def test_not_allowed_users(self):
        await init_first_users(self.mock_context)
        self.mock_context.bot.send_message.assert_not_called()