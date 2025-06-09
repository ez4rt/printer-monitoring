import asyncio
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, CallbackQuery
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    ApplicationBuilder,
    MessageHandler,
    filters
)
from asgiref.sync import sync_to_async
from prettytable import PrettyTable
from monitoring.models import Printer, Statistics, ChangeSupply, PrinterError, SupplyDetails, PrinterSupplyStatus
from django.contrib.admin.models import LogEntry
from monitoring.views import get_area_name, create_events
from datetime import timedelta
from django.db.models import Q
from functools import wraps
from decouple import config
from tgbot.models import TelegramUser
import signal
from easy_async_tg_notify import Notifier

token = config('TELEGRAM_BOT_TOKEN')

logging.basicConfig(
    format="%(levelname)s %(asctime)s %(name)s %(message)s",
    level=logging.INFO,
    filename='logs/tgbot.log'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger('tgbot')


(START_ROUTES, PRINTERS_ROUTES, INPUT_PRINTER_ROUTES, EVENTS_ROUTES, INPUT_EVENTS_ROUTES, SUPPLIES_ROUTES,
 INPUT_SUPPLIES_ROUTES, END_ROUTES) = range(8)

PRINTERS, EVENTS, EVENTS_SUPPLIES, SUPPLIES, SINGLE_OBJECT, ALL_OBJECTS, HELP, EXIT, GO_BACK_START = range(9)

ALLOWED_USERS = set(TelegramUser.objects.values_list('chat_id', flat=True))

active_sessions = set()
active_chats_notify = set()

TABLE_SIZE = 20
current_page = 0


def check_user(update):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        return False
    return True


def user_check_access(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not check_user(update):
            user = update.message.from_user

            logger.warning("Unauthorized acces attempt - user: %s %s, chat_id: %s.",
                           user.first_name, user.last_name, update.effective_chat.id)
            await context.bot.send_message(chat_id=update.effective_chat.id, text="У вас нет доступа к этому боту.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def get_field_name(nm_field:str) -> str:
    field_names_mapping = {
        'ip_address': 'IP-адрес',
        'stamp': 'Марка',
        'model': 'Модель',
        'serial_number': 'Серийный номер',
        'inventory_number': 'Инвентарный номер',
        'location': 'Местоположение',
        'department': 'Отдел',
        'date_of_commission': 'Дата ввода',
        'is_active': 'Активен',
        'is_archived': 'В архиве',
        'cartridge': 'Картридж',
        'drum_unit': 'Фотобарабан',
        'color': 'Цвет',
        'black': 'Черный',
        'cyan': 'Голубой',
        'magenta': 'Пурпурный',
        'yellow': 'Желтый',
        'comment': 'Комментарий',
        'name': 'Имя',
        'type': 'Тип',
        'price': 'Стоимость',
    }
    return field_names_mapping.get(nm_field, nm_field)


def wrap_text(text, width):
    text = str(text)
    return '\n'.join(text[i:i + width] for i in range(0, len(text), width))


async def handle_pagination(query: CallbackQuery, request: list, nm_page: str) -> dict:
    global current_page
    if query.data == f'prev_page_{nm_page}':
        current_page = max(0, current_page - 1)
    elif query.data == f'next_page_{nm_page}':
        current_page += 1
    else:
        current_page = 0

    total_pages = (len(request) + TABLE_SIZE - 1) // TABLE_SIZE
    start_index = current_page * TABLE_SIZE
    end_index = start_index + TABLE_SIZE
    qty_lines = request[start_index:end_index]

    keyboard = list()
    if total_pages > 1:
        if current_page == 0:
            keyboard = [[InlineKeyboardButton("➡️", callback_data=f'next_page_{nm_page}')]]
        elif current_page == total_pages - 1:
            keyboard = [[InlineKeyboardButton("⬅️", callback_data=f'prev_page_{nm_page}')]]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("⬅️", callback_data=f'prev_page_{nm_page}'),
                    InlineKeyboardButton("➡️", callback_data=f'next_page_{nm_page}')
                ]
            ]

    return_dict = {
        'total_pages': total_pages,
        'qty_lines': qty_lines,
        'keyboard': keyboard,
        'current_page': current_page,
    }

    return return_dict


@user_check_access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user

    chat_id = update.message.chat_id
    logger.info(ALLOWED_USERS)
    active_sessions.add(chat_id)

    logger.info("User %s %s started chatting", user.first_name, user.last_name)
    keyboard = [
        [InlineKeyboardButton("🖨️ Принтеры", callback_data=str(PRINTERS))],
        [InlineKeyboardButton("📅 События", callback_data=str(EVENTS))],
        [InlineKeyboardButton("️📦 Расходные материалы", callback_data=str(SUPPLIES))],
        [
            InlineKeyboardButton("🆘 Помощь", callback_data=str(HELP)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Доброго времени суток!\n"
        "Меня зовут 🖨️🧑‍🔧 *Принтер Мастер: Телеграм Бот Мониторинга Принтеров*. Я помогу Вам получить необходимую "
        "информацию. \n\n"
        "Какую информацию Вы хотите получить❓",
        parse_mode='Markdown',
        reply_markup=reply_markup)

    return START_ROUTES


async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🖨️ Принтеры", callback_data=str(PRINTERS))],
        [InlineKeyboardButton("📅 События", callback_data=str(EVENTS))],
        [InlineKeyboardButton("📦 Расходные материалы", callback_data=str(SUPPLIES))],
        [
            InlineKeyboardButton("🆘 Помощь", callback_data=str(HELP)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="🏠 Вы вернулись к началу!\n"
             "Меня всё еще зовут 🖨️🧑‍🔧 *Принтер Мастер: Телеграм Бот Мониторинга Принтеров*. Я помогу Вам получить "
             "необходимую информацию.\n\n"
             "Какую информацию Вы хотите получить❓",
        parse_mode='Markdown',
        reply_markup=reply_markup)
    return START_ROUTES


async def printers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🖨️🖨️🖨️ Все принтеры", callback_data=str(ALL_OBJECTS)), ],
        [InlineKeyboardButton("🖨️ Конкретный принтер", callback_data=str(SINGLE_OBJECT)), ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(GO_BACK_START)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="🖨️ *ПРИНТЕРЫ*\n\n"
             "🤔 Пожалуйста, выберите необходимую опцию.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return PRINTERS_ROUTES


async def all_printers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = update.callback_query.from_user

    logger.info("User %s %s requested information about all printers on page %s.",
                user.first_name, user.last_name, current_page + 1)

    printers_all = await sync_to_async(list)(
        Printer.objects.select_related('ip_address__subnet', 'model__stamp', 'location__cabinet', 'location__department').all()
    )
    info = await handle_pagination(query, printers_all, 'all_printers')
    info['keyboard'].append([InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START))])
    info['keyboard'].append(
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(PRINTERS)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['Принтер', 'Статус', 'Ip-адрес', 'Расположение']
    for printer in info['qty_lines']:
        table.add_row(
            [
                f'{printer.model}',
                '🟢' if printer.is_active else '🔴',
                printer.ip_address.address,
                f'{printer.get_subnet_name()}, {printer.location}',
            ]
        )

    message = (
            f"✅ <b>Вы выбрали все принтеры | [{len(printers_all)}]</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам с принтерами используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Выберите дальнейшее действие."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def single_printer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    printers_all = await sync_to_async(list)(
        Printer.objects.select_related('ip_address__subnet', 'model__stamp', 'location__cabinet',
                                       'location__department').all()
    )

    info = await handle_pagination(query, printers_all, 'single_printer_events')

    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['ID', 'Принтер', 'Расположение']
    for printer in info['qty_lines']:
        table.add_row(
            [
                printer.id,
                f'{printer.model}',
                f'{printer.get_subnet_name()}, {printer.location}',
            ]
        )

    message = (
            f"✅ <b>ПРИНТЕР</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам со списком принтеров используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Введите ID принтера, согласно списку или нажмите на /exit, чтобы завершить работу."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup,
    )
    return INPUT_PRINTER_ROUTES


async def handle_text_input_printer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_input = update.message.text

    printer_ids = await sync_to_async(list)(Printer.objects.values_list('id', flat=True))

    if user_input.isdigit():
        printer_id = int(user_input)
        if printer_id in printer_ids:
            await result_single_printer(update, context, printer_id)
        else:
            await update.message.reply_text(
                f"⚠️ Принтер с ID={printer_id} отсутствует в списке. Пожалуйста, введите корректный ID принтера "
                f"или нажмите на /exit, чтобы завершить работу.")
    else:
        await update.message.reply_text(
            "⚠️ Пожалуйста, введите корректный ID принтера или нажмите на /exit, чтобы завершить работу."
        )


async def result_single_printer(update: Update, context: ContextTypes.DEFAULT_TYPE, printer_id) -> int:
    user = update.message.from_user

    logger.info("User %s %s requested information about the printer with id=%s.",
                user.first_name, user.last_name, printer_id)

    keyboard = [
        [InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START)),],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(PRINTERS)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    printer = await sync_to_async(Printer.objects.select_related(
        'ip_address__subnet', 'model__stamp', 'location__cabinet', 'location__department', 'inventory_number'
    ).get)(id=printer_id)
    try:
        printer_stats = await sync_to_async(
            lambda: Statistics.objects.filter(printer_id=printer_id).latest('time_collect')
        )()
    except ObjectDoesNotExist:
        printer_stats = None

    table = PrettyTable()
    table.field_names = ['Название', 'Значение']

    table.add_row(['Район', get_area_name(printer.ip_address.subnet.name)])
    for field in printer._meta.fields:
        value = getattr(printer, field.name)
        if value is not None:
            if field.name != 'id' and field.name != 'location':
                if field.name == 'is_active':
                    value = '🟢' if value else '🔴'
                if field.name == 'is_archived':
                    value = '🟢' if value else '🔴'
                table.add_row([get_field_name(field.name), value])

            if field.name == 'location':
                table.add_row(['Кабинет', printer.location.cabinet])
                table.add_row(['Отдел', printer.location.department])


    printer_supplies = await sync_to_async(list)(
        PrinterSupplyStatus.objects.select_related('supply').filter(printer_id=printer_id)
    )

    for supply in printer_supplies:
        table.add_row([supply.supply, f'{supply.remaining_supply_percentage}%'])

    if printer_stats is not None:
        table.add_row(['Кол-во страниц', printer_stats.page])
        table.add_row(['Cтраниц печати', printer_stats.print])
        table.add_row(['Кол-во копий', printer_stats.copies])
        table.add_row(['Кол-во сканов', printer_stats.scan])

    await update.message.reply_text(
        text=f"✅ <b>Вы выбрали принтер с ID - {printer_id}</b>\n\n"
             f"<pre>{table}</pre>\n\n"
             f"🤔 Выберите дальнейшее действие.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📅📅📅 Все события", callback_data=str(ALL_OBJECTS)), ],
        [InlineKeyboardButton("📅🖨️ События принтера", callback_data=str(SINGLE_OBJECT)), ],
        [InlineKeyboardButton("📦🔄 Замена расходных материалов", callback_data=str(EVENTS_SUPPLIES)), ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(GO_BACK_START)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📅 *СОБЫТИЯ*\n\n"
             "🤔 Пожалуйста, выберите необходимую опцию.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return EVENTS_ROUTES


async def all_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.callback_query.from_user

    logger.info("User %s %s requested information about all the events on page %s.",
                user.first_name, user.last_name, current_page + 1)

    await query.answer()

    recent_changes_supplies = await sync_to_async(lambda: list(
        ChangeSupply.objects.select_related('printer__ip_address', 'supply', 'printer__model__stamp').order_by('-time_change')[:35]))()
    recent_errors = await sync_to_async(
        lambda: list(PrinterError.objects.select_related('printer__ip_address', 'printer__model__stamp').order_by('-event_date')[:35]))()
    recent_admin_log = await sync_to_async(lambda: LogEntry.objects.order_by('-action_time')[:35])()
    recent_events = await sync_to_async(create_events)(recent_changes_supplies, recent_errors, recent_admin_log)
    new_recent_events = recent_events[:35]

    global TABLE_SIZE
    TABLE_SIZE = 7

    info = await handle_pagination(query, new_recent_events, 'all_events')

    TABLE_SIZE = 20

    info['keyboard'].append([InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START))])
    info['keyboard'].append(
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(EVENTS)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['Время', 'Тип', 'Объект', 'Событие']
    for event in info['qty_lines']:
        table.add_row([wrap_text(event['action_time'], 11), wrap_text(event['type'], 10),
                       wrap_text(event['object_repr'], 25), wrap_text(event['description'], 25)])

    message = (
            f"✅ <b>Вы выбрали все события</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам с принтерами используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Выберите дальнейшее действие."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def single_printer_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    printers_all = await sync_to_async(list)(
        Printer.objects.select_related(
            'ip_address__subnet', 'model__stamp', 'location__cabinet', 'location__department').all()
    )

    info = await handle_pagination(query, printers_all, 'single_printer_events')

    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['ID', 'Принтер', 'Расположение']
    for printer in info['qty_lines']:
        table.add_row(
            [
                printer.id,
                f'{printer.model}',
                f'{printer.get_subnet_name()}, {printer.location}',
            ]
        )

    message = (
            f"✅ <b>СОБЫТИЯ ПРИНТЕРА</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам со списком принтеров используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Введите ID принтера, согласно списку или нажмите на /exit, чтобы завершить работу."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup,
    )
    return INPUT_EVENTS_ROUTES


async def handle_text_input_printer_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_input = update.message.text

    printer_ids = await sync_to_async(list)(Printer.objects.values_list('id', flat=True))

    if user_input.isdigit():
        printer_id = int(user_input)
        if printer_id in printer_ids:
            await result_single_printer_events(update, context, printer_id)
        else:
            await update.message.reply_text(
                f"⚠️ Принтер с ID={printer_id} отсутствует в списке. Пожалуйста, введите корректный ID принтера "
                f"или нажмите на /exit, чтобы завершить работу.")
    else:
        await update.message.reply_text("⚠️ Пожалуйста, введите корректный ID принтера или нажмите на /exit, чтобы "
                                        "завершить работу.")


async def result_single_printer_events(update: Update, context: ContextTypes.DEFAULT_TYPE, printer_id) -> int:
    user = update.message.from_user

    logger.info("User %s %s requested information about printer events with id=%s.",
                user.first_name, user.last_name, printer_id)

    keyboard = [
        [InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START)),],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(EVENTS)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    printer = await sync_to_async(Printer.objects.select_related('ip_address').get)(id=printer_id)

    recent_changes_supplies = await sync_to_async(lambda: list(
        ChangeSupply.objects.select_related('printer__ip_address', 'printer__model__stamp', 'supply')
        .filter(printer_id=printer_id).order_by('-time_change')[:10]))()

    recent_errors = await sync_to_async(lambda: list(
        PrinterError.objects.select_related('printer__ip_address__subnet', 'printer__model__stamp')
        .filter(printer_id=printer_id).order_by('-event_date')[:10]))()

    recent_admin_log = await sync_to_async(lambda: list(
        LogEntry.objects.filter(object_repr=printer).order_by('-action_time')[:10]))()

    recent_events = await sync_to_async(create_events)(recent_changes_supplies, recent_errors, recent_admin_log)
    new_recent_events = recent_events[:10]

    table = PrettyTable()
    table.field_names = ['Время', 'Тип', 'Событие']
    for event in new_recent_events:
        table.add_row([wrap_text(event['action_time'], 11), wrap_text(event['type'], 10),
                       wrap_text(event['description'], 17)])

    await update.message.reply_text(
        text=f"✅ <b>Вы выбрали события принтера с номером - {printer_id}</b>\n\n"
             f"🖨️ <b>{printer}</b>\n\n"
             f"<pre>{table}</pre>\n\n"
             f"🤔 Выберите дальнейшее действие.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def events_supplies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.callback_query.from_user

    logger.info("User %s %s requested information about the events of the replacement of supplies",
                user.first_name, user.last_name)

    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START)),
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(EVENTS)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    recent_changes_supplies = await sync_to_async(lambda: list(ChangeSupply.objects.select_related(
        'printer__ip_address', 'printer__model__stamp', 'supply').order_by('-time_change')[:20]))()
    table = PrettyTable()
    table.field_names = ['Принтер', 'РМ', 'Время замены',]
    for event in recent_changes_supplies:
        event.time_change += timedelta(hours=7)
        formatted_time = event.time_change.strftime('%Y/%m/%d %H:%M')
        table.add_row(
            [event.printer,
             wrap_text(f'{event.supply}', 10),
             wrap_text(formatted_time, 11)
             ]
        )

    await query.edit_message_text(
        text=f"✅ <b>Вы выбрали события замены расходных материалов</b>\n\n"
             f"<pre>{table}</pre>\n\n"
             f"ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей.\n\n"
             f"🤔 Выберите дальнейшее действие.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def supplies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📦📦📦 Все расходные материалы", callback_data=str(ALL_OBJECTS)), ],
        [InlineKeyboardButton("📦 Конкретный расходный материал", callback_data=str(SINGLE_OBJECT)), ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(GO_BACK_START)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="📦 *РАСХОДНЫЕ МАТЕРИАЛЫ*\n\n"
             "🤔 Пожалуйста, выберите необходимую опцию.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return SUPPLIES_ROUTES


async def all_supplies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.callback_query.from_user

    logger.info("User %s %s requested information about all supplies",
                user.first_name, user.last_name)
    await query.answer()

    supplies_query = await sync_to_async(list)(SupplyDetails.objects.select_related('supply').all().order_by('id'))
    printers_supplies = await sync_to_async(list)(
        PrinterSupplyStatus.objects.select_related('printer__ip_address__subnet', 'printer__model__stamp', 'supply').all()
    )

    info = await handle_pagination(query, supplies_query, 'all_supplies')

    info['keyboard'].append([InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START))])
    info['keyboard'].append(
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(SUPPLIES)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['Название', 'Тип', 'Кол-во', 'Стоимость', 'Принтер']
    for supply in info['qty_lines']:
        sup_for_printer = None
        for printer_supply in printers_supplies:
            if supply.supply.name == printer_supply.supply.name:
                sup_for_printer = f'{printer_supply.printer.model}'
        table.add_row(
            [
                supply.supply.name,
                supply.supply.type,
                supply.qty,
                supply.supply.price,
                sup_for_printer if sup_for_printer else 'Отсутствует',
            ]
        )

    message = (
            f"✅ <b>Вы выбрали все расходные материалы | [{len(supplies_query)}]</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам с расходными материалами используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Выберите дальнейшее действие."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def single_supplies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    supplies_query = await sync_to_async(list)(SupplyDetails.objects.select_related('supply').all().order_by('id'))

    info = await handle_pagination(query, supplies_query, 'single_supplies')

    reply_markup = InlineKeyboardMarkup(info['keyboard'])

    table = PrettyTable()
    table.field_names = ['ID', 'РМ']
    for supply in info['qty_lines']:
        table.add_row(
            [
                supply.supply_id,
                supply.supply,
            ]
        )

    message = (
            f"✅ <b>РАСХОДНЫЙ МАТЕРИАЛ</b>\n\n" +
            (f"<i>Страница {info['current_page'] + 1}</i>\n" if info['total_pages'] > 1 else '') +
            f"<pre>{table}</pre>\n\n" +
            "ℹ️ Для удобного отображения таблицы переверните устройство или нажмите на ☰ над таблицей." +
            (f"\n🔢 Для навигации по страницам с расходными материалами используйте кнопки ⬅️ и ➡️" if info['total_pages'] > 1 else '') +
            "\n\n🤔 Введите номер расходного материала, согласно списку или нажмите на /exit, чтобы завершить работу."
    )

    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return INPUT_SUPPLIES_ROUTES


async def handle_text_input_supplies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_input = update.message.text
    supply_ids = await sync_to_async(list)(SupplyDetails.objects.values_list('id', flat=True))

    if user_input.isdigit():
        supply_id = int(user_input)
        if supply_id in supply_ids:
            await result_single_supplies(update, context, supply_id)
        else:
            await update.message.reply_text(
                f"⚠️ Расходный материал с ID={supply_id} отсутствует в списке. Пожалуйста, введите корректный ID "
                f"или нажмите на /exit, чтобы завершить работу.")
    else:
        await update.message.reply_text("⚠️ Пожалуйста, введите корректный ID расходного материала или нажмите на "
                                        "/exit, чтобы завершить работу.")


async def result_single_supplies(update: Update, context: ContextTypes.DEFAULT_TYPE, supply_id) -> int:
    user = update.message.from_user

    logger.info("User %s %s requested information about the supply with id=%s.",
                user.first_name, user.last_name, supply_id)

    keyboard = [
        [InlineKeyboardButton("🏠 Вернуться к началу", callback_data=str(GO_BACK_START)),],
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(SUPPLIES)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    supply = await sync_to_async(SupplyDetails.objects.select_related('supply').get)(id=supply_id)

    table = PrettyTable()
    table.field_names = ['Название', 'Значение']

    for field in supply.supply._meta.fields:
        value = getattr(supply.supply, field.name)
        if field.name != 'id':
            if value is not None:
                table.add_row([get_field_name(field.name), get_field_name(value)])

    table.add_row(['Кол-во', supply.qty])

    printers_supplies = await sync_to_async(list)(
        PrinterSupplyStatus.objects.select_related(
            'printer__ip_address__subnet', 'printer__model__stamp', 'supply').all()
    )

    sup_for_printer = None
    for printer_supply in printers_supplies:
        if supply.supply.name == printer_supply.supply.name:
            sup_for_printer = f'{printer_supply.printer.model}'
    table.add_row(
        [
            'Принтер',
            sup_for_printer if sup_for_printer else 'Отсутствует',
        ]
    )

    await update.message.reply_text(
        text=f"✅ <b>Вы выбрали расходный материал с номером - {supply_id}</b>\n\n"
             f"<pre>{table}</pre>\n\n"
             f"🤔 Выберите дальнейшее действие",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return END_ROUTES


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("🔙 Назад", callback_data=str(GO_BACK_START)),
            InlineKeyboardButton("🔚 Выход", callback_data=str(EXIT)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
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
        reply_markup=reply_markup
    )
    return END_ROUTES


async def help_command_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user

    logger.info("User %s %s with chat_id=%s asked for help",
                user.first_name, user.last_name, update.effective_chat.id)

    await update.message.reply_text(
        text='📜 <b>Справка по работе бота.</b> <i>Я умею:</i>\n\n'
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
             '😊 Хорошей работы❗',
        parse_mode='HTML',
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user

    logger.info("User %s %s with chat_id=%s received his status",
                user.first_name, user.last_name, update.effective_chat.id)

    if not check_user(update):
        str_access = ("Доступ: Запрещен 🚫\n"
                      "ℹ️ Для получения доступа обратитесь к администратору.")
    else:
        str_access = "Доступ: Разрешен ✅\n"
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=update.effective_chat.id)
        if user_db.admin:
            str_access += "Права доступа: Администратор 🛡️\n"
        else:
            str_access += "Права доступа: Пользователь 👤\n"
        if user.id in active_sessions:
            str_access += (
                "Приложение: Запушено 🟢\n"
                "☑️ Рекомендую нажать на /exit, если в данный момент Вы не собираетесь использовать приложение.\n"
            )
        else:
            str_access += "Приложение: Выключено 🔴\n"
        if user.id in active_chats_notify:
            str_access += "Уведомления: Включены 🟢"
        else:
            str_access += "Уведомления: Выключены 🔴"

    await update.message.reply_text(
        text=f"👨🏻‍💻 <b>СТАТУС</b>\n\n"
             f"Имя пользователя: {user.first_name} {user.last_name}\n"
             f"CHAT ID: {update.effective_chat.id}\n" + str_access,
        parse_mode='HTML',
    )


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.callback_query.from_user

    logger.info("User %s %s has completed the chat",
                user.first_name, user.last_name)

    if user.id in active_sessions:
        active_sessions.remove(user.id)

    await query.answer()

    await query.edit_message_text(text="👋 Буду ждать новых встреч!")
    return ConversationHandler.END


@user_check_access
async def end_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user

    chat_id = update.message.chat_id
    if chat_id in active_sessions:
        active_sessions.remove(chat_id)

        logger.info("User %s %s has completed the chat",
                    user.first_name, user.last_name)

        await update.message.reply_text("👋 Буду ждать новых встреч!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Приложение уже выключено.")


async def check_supplies_every_3days(context: ContextTypes.DEFAULT_TYPE):
    low_supply_printers = await sync_to_async(list)(
        PrinterSupplyStatus.objects.select_related(
            'printer__ip_address__subnet', 'printer__model__stamp', 'supply'
        ).filter(
            supply__type='cartridge', remaining_supply_percentage__lt=10
        )
    )

    printer_ids = [status.printer.id for status in low_supply_printers]

    printers_with_low_supplies = await sync_to_async(list)(
        Printer.objects.select_related(
            'ip_address__subnet', 'model__stamp', 'location__cabinet', 'location__department'
        ).filter(id__in=printer_ids)
    )

    for printer in printers_with_low_supplies:
        message_text = (f'📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
                        f'Принтер: {printer.model}\n'
                        f'Местоположение: {printer.get_subnet_name()}, {printer.location}')
        for supply in low_supply_printers:
            if supply.printer == printer:
                message_text += f'\nОстаток {supply.supply} - {supply.remaining_supply_percentage}%'

        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=message_text,
            parse_mode='HTML',
        )


async def check_supplies_every_7_days(context: ContextTypes.DEFAULT_TYPE):
    low_supply_printers = await sync_to_async(list)(
        PrinterSupplyStatus.objects.select_related(
            'printer__ip_address__subnet', 'printer__model__stamp', 'supply'
        ).filter(
            supply__type='drum_unit', remaining_supply_percentage__lt=20
        )
    )

    printer_ids = [status.printer.id for status in low_supply_printers]

    printers_with_low_supplies = await sync_to_async(list)(
        Printer.objects.select_related(
            'ip_address__subnet', 'model__stamp', 'location__cabinet', 'location__department'
        ).filter(id__in=printer_ids)
    )

    for printer in printers_with_low_supplies:
        message_text = (f'📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
                        f'Принтер: {printer.model}\n'
                        f'Местоположение: {printer.get_subnet_name()}, {printer.location}')
        for supply in low_supply_printers:
            if supply.printer == printer:
                message_text += f'\nОстаток {supply.supply} - {supply.remaining_supply_percentage}%'

        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=message_text,
            parse_mode='HTML',
        )


async def check_supplies_every_2_weeks(context: ContextTypes.DEFAULT_TYPE):
    low_supplies_qty = await sync_to_async(list)(
        SupplyDetails.objects.select_related('supply').filter(qty__lt=20)
    )

    message_sup = ("📢 <b>УВЕДОМЛЕНИЕ</b>\n\n"
                   "<i>Низкие остатки расходных материалов</i>\n")
    for supply in low_supplies_qty:
        message_sup += f"{supply.supply} - {supply.qty}шт.\n"

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=message_sup,
        parse_mode='HTML',
    )


@user_check_access
async def start_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    logger.info("User %s %s has enabled notifications",
                user.first_name, user.last_name)

    chat_id = update.message.chat_id
    if chat_id in active_chats_notify:
        await context.bot.send_message(chat_id=chat_id, text='Уведомления уже запущены!')
        return None

    active_chats_notify.add(chat_id)
    user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=chat_id)
    user_db.active_notify = True
    await sync_to_async(user_db.save)()

    name = update.effective_chat.full_name
    await context.bot.send_message(
        chat_id=chat_id,
        text='🥳 Поздравляю! Теперь вы получаете уведомления о важных событиях 🔔'
    )

    context.job_queue.run_repeating(check_supplies_every_3days, interval=259200, first=5, data=name, chat_id=chat_id)
    context.job_queue.run_repeating(check_supplies_every_7_days, interval=604800, first=35, data=name, chat_id=chat_id)
    context.job_queue.run_repeating(check_supplies_every_2_weeks, interval=1209600, first=65, data=name, chat_id=chat_id)


@user_check_access
async def stop_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    logger.info("User %s %s turned off notifications",
                user.first_name, user.last_name)

    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(context, chat_id)
    if job_removed:
        user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=chat_id)
        user_db.active_notify = False
        await sync_to_async(user_db.save)()
    text = '🔕 Уведомления отключены!' if job_removed else '🚫 Уведомления уже отключены.'
    await context.bot.send_message(chat_id=chat_id, text=text)


def remove_job_if_exists(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    current_jobs = context.job_queue.jobs()
    if chat_id in active_chats_notify:
        for job in current_jobs:
            if job.chat_id == chat_id:
                job.schedule_removal()
        active_chats_notify.remove(chat_id)
        return bool(current_jobs)
    return bool(None)


@user_check_access
async def update_allowed_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_db = await sync_to_async(TelegramUser.objects.get)(chat_id=chat_id)
    if user_db.admin:
        logger.info("User %s %s updated the ALLOWED_USERS list",
                    user.first_name, user.last_name)
        name = update.effective_chat.full_name

        context.job_queue.run_once(callback_update_user, 0, data=name, chat_id=chat_id)
    else:
        logger.info("User %s %s tried to update the ALLOWED_USERS list",
                    user.first_name, user.last_name)
        await context.bot.send_message(chat_id=chat_id, text='У вас нет доступа к данной функции.')


async def callback_update_user(context: ContextTypes.DEFAULT_TYPE):
    global ALLOWED_USERS
    current_allowed_users = ALLOWED_USERS.copy()

    list_users = await sync_to_async(lambda: list(TelegramUser.objects.values_list('chat_id', flat=True)))()
    ALLOWED_USERS = set(list_users)
    new_users = ALLOWED_USERS - current_allowed_users

    if new_users:
        for user in ALLOWED_USERS:
            await context.bot.send_message(chat_id=user, text='Доступ к боту открыт ✅')
        await context.bot.send_message(chat_id=context.job.chat_id, text='Список пользователей обновлен 🔄')
    else:
        await context.bot.send_message(chat_id=context.job.chat_id, text='Новых пользователей не найдено!')


async def send_msg(msg_text: str, users_ids):
    async with Notifier(token) as notifier:
        await notifier.send_text(msg_text, users_ids)


@sync_to_async
def update_active_users():
    active_notify_users = TelegramUser.objects.filter(active_notify=True)
    if active_notify_users:
        list_users = list()
        list_ids = list()
        for user in active_notify_users:
            list_users.append(user.username)
            list_ids.append(user.chat_id)

        asyncio.run(send_msg("Уведомления отключены", list_ids))
        logging.info("Notifications are disabled: %s", list_users)
        active_notify_users.update(active_notify=False)


async def signal_handler(sig, frame):
    logging.info('A stop signal has been received. The application is shutting down')
    await update_active_users()
    asyncio.get_event_loop().stop()


async def init_first_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    global ALLOWED_USERS
    logging.info(f'context test {context}')
    current_jobs = context.job_queue.jobs()
    logging.info(f'jobs test {current_jobs}, {type(current_jobs)}')
    logging.info(ALLOWED_USERS)
    if not ALLOWED_USERS:
        users_chat_id = await sync_to_async(lambda: list(TelegramUser.objects.values_list('chat_id', flat=True)))()
        logging.info(users_chat_id)
        if users_chat_id:
            ALLOWED_USERS = set(users_chat_id)
            for job in current_jobs:
                job.schedule_removal()
                logging.info(f'Init first users ({users_chat_id}) success, Job ({job}) Delete')
                for chat_id in users_chat_id:
                    await context.bot.send_message(chat_id=chat_id, text='Доступ к боту открыт ✅')
    else:
        for job in current_jobs:
            job.schedule_removal()
            logging.info(f'Delete init_first_admin_users {job}')


class Command(BaseCommand):
    def handle(self, *args, **options):
        application = Application.builder().token(token).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                START_ROUTES: [
                    CallbackQueryHandler(printers, pattern="^" + str(PRINTERS) + "$"),
                    CallbackQueryHandler(events, pattern="^" + str(EVENTS) + "$"),
                    CallbackQueryHandler(supplies, pattern="^" + str(SUPPLIES) + "$"),
                    CallbackQueryHandler(help_command, pattern="^" + str(HELP) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                ],
                PRINTERS_ROUTES: [
                    CallbackQueryHandler(printers, pattern="^" + str(PRINTERS) + "$"),
                    CallbackQueryHandler(all_printers, pattern="^" + str(ALL_OBJECTS) + "$"),
                    CallbackQueryHandler(single_printer, pattern="^" + str(SINGLE_OBJECT) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(help_command, pattern="^" + str(HELP) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                ],
                INPUT_PRINTER_ROUTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input_printer),
                    CallbackQueryHandler(printers, pattern="^" + str(PRINTERS) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                    CallbackQueryHandler(single_printer, pattern='prev_page_single_printer'),
                    CallbackQueryHandler(single_printer, pattern='next_page_single_printer'),
                ],
                EVENTS_ROUTES: [
                    CallbackQueryHandler(printers, pattern="^" + str(EVENTS) + "$"),
                    CallbackQueryHandler(all_events, pattern="^" + str(ALL_OBJECTS) + "$"),
                    CallbackQueryHandler(single_printer_events, pattern="^" + str(SINGLE_OBJECT) + "$"),
                    CallbackQueryHandler(events_supplies, pattern="^" + str(EVENTS_SUPPLIES) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(help_command, pattern="^" + str(HELP) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                ],
                INPUT_EVENTS_ROUTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input_printer_events),
                    CallbackQueryHandler(events, pattern="^" + str(EVENTS) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                    CallbackQueryHandler(single_printer_events, pattern='prev_page_single_printer_events'),
                    CallbackQueryHandler(single_printer_events, pattern='next_page_single_printer_events'),
                ],
                SUPPLIES_ROUTES: [
                    CallbackQueryHandler(supplies, pattern="^" + str(SUPPLIES) + "$"),
                    CallbackQueryHandler(all_supplies, pattern="^" + str(ALL_OBJECTS) + "$"),
                    CallbackQueryHandler(single_supplies, pattern="^" + str(SINGLE_OBJECT) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(help_command, pattern="^" + str(HELP) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                ],
                INPUT_SUPPLIES_ROUTES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input_supplies),
                    CallbackQueryHandler(supplies, pattern="^" + str(SUPPLIES) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                    CallbackQueryHandler(single_supplies, pattern='prev_page_single_supplies'),
                    CallbackQueryHandler(single_supplies, pattern='next_page_single_supplies'),

                ],
                END_ROUTES: [
                    CallbackQueryHandler(printers, pattern="^" + str(PRINTERS) + "$"),
                    CallbackQueryHandler(events, pattern="^" + str(EVENTS) + "$"),
                    CallbackQueryHandler(supplies, pattern="^" + str(SUPPLIES) + "$"),
                    CallbackQueryHandler(start_over, pattern="^" + str(GO_BACK_START) + "$"),
                    CallbackQueryHandler(end, pattern="^" + str(EXIT) + "$"),
                    CallbackQueryHandler(all_printers, pattern='prev_page_all_printers'),
                    CallbackQueryHandler(all_printers, pattern='next_page_all_printers'),
                    CallbackQueryHandler(all_supplies, pattern='prev_page_all_supplies'),
                    CallbackQueryHandler(all_supplies, pattern='next_page_all_supplies'),
                    CallbackQueryHandler(all_events, pattern='prev_page_all_events'),
                    CallbackQueryHandler(all_events, pattern='next_page_all_events')
                ],
            },
            fallbacks=[CommandHandler("start", start)],
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('help', help_command_main))
        application.add_handler(CommandHandler('exit', end_input))
        application.add_handler(CommandHandler('start_notify', start_notifications))
        application.add_handler(CommandHandler('stop_notify', stop_notifications))
        application.add_handler(CommandHandler('status', status))
        application.add_handler(CommandHandler('update_allowed_users', update_allowed_users))

        job_queue = application.job_queue
        job_queue.run_repeating(init_first_users, interval=10, first=0)

        signal.signal(signal.SIGINT, lambda sig, frame: asyncio.create_task(signal_handler(sig, frame)))
        signal.signal(signal.SIGTERM, lambda sig, frame: asyncio.create_task(signal_handler(sig, frame)))

        application.run_polling(allowed_updates=Update.ALL_TYPES)
