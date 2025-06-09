from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import asyncio
from decouple import config
from easy_async_tg_notify import Notifier
from tgbot.models import TelegramUser
from asgiref.sync import sync_to_async
from monitoring.models import Printer, PrinterError, PrinterSupplyStatus
from automation.data_extractor import printer_init_resource
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed


logger_user_actions = logging.getLogger('user_actions')


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    logger_user_actions.info(f'User {user.username} logged in')


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    logger_user_actions.info(f'User {user.username} logged out')


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', 'Unknown user')
    logger_user_actions.warning(
        f'An unsuccessful login attempt for the user {username} from the IP address {request.META.get("REMOTE_ADDR")}'
    )


@receiver(user_logged_in)
def logout_previous_user(sender, request, user, **kwargs):
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.id):
            session.delete()


@receiver(pre_save, sender=Printer)
def check_ip_address(sender, instance, **kwargs):
    if instance.ip_address is not None:
        if Printer.objects.filter(ip_address=instance.ip_address).exclude(id=instance.id).exists():
            raise ValueError('IP-адрес уже используется другим принтером.')


@receiver(post_save, sender=Printer)
def printer_created(sender, instance, created, **kwargs):
    if created:
        printer_init_resource(instance)


token = config('TELEGRAM_BOT_TOKEN')


async def send_msg(msg_text: str):
    async with Notifier(token) as notifier:
        users_ids = await sync_to_async(lambda: list(
            TelegramUser.objects.values_list('chat_id', flat=True).filter(active_notify=True)))()
        await notifier.send_text(msg_text, users_ids)


@receiver(post_save, sender=PrinterSupplyStatus)
def notify_low_cart(sender, instance, created, **kwargs):

    low_supplies = list()

    if instance.remaining_supply_percentage == 1:
        low_supplies.append(f' закончился {instance.supply}')

    if low_supplies:
        message = ((
            f'📢 <b>УВЕДОМЛЕНИЕ</b>\n\nВ принтере {instance.printer.model}') +
                   "\n".join(low_supplies) + "\n" + (f'Местоположение: '
                                                     f'{instance.printer.get_subnet_name()},'
                                                     f'{instance.printer.location}\n'
        ))
        asyncio.run(send_msg(message))


@receiver(post_save, sender=PrinterError)
def notify_error(sender, instance, created, **kwargs):

    message = (
        f'📢 <b>УВЕДОМЛЕНИЕ</b>\n\n'
        f'В принтере {instance.printer.model} возникла ошибка {instance.description}\n '
        f'Местоположение: {instance.printer.get_subnet_name()}, {instance.printer.location}\n'
    )
    if created:
        asyncio.run(send_msg(message))
