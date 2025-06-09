from celery import shared_task
from celery.utils.log import get_task_logger
import psycopg2
import datetime
from automation.data_extractor import (scan_subnet, add_printer_parsing_snmp, checking_activity,
                                       update_printer_resource, parsing_snmp_katusha, parsing_snmp_avision,
                                       parsing_snmp_hp, parsing_pantum, parsing_snmp_kyosera, parsing_snmp_sindoh,
                                       add_missing_statistics_to_db, detect_device_errors)
from django.core.exceptions import ObjectDoesNotExist
from celery.schedules import crontab
from celery.schedules import timedelta
from django.utils import timezone
import logging
from automation.clear_logs import LogsFileManager


custom_logger = logging.getLogger('automation')

task_schedule = {
    "scan-subnets-regular": {
        "task": "monitoring.tasks.scan_subnets_regular",
        "schedule": crontab(minute='0', hour='7,11,15,18'),
    },
    "checking-printer-activity-regular": {
        "task": "monitoring.tasks.checking_activity_regular",
        "schedule": crontab(minute='*/5', hour='7-19'),
    },
    "delete-expired-sessions-every-2-hour": {
        'task': 'monitoring.tasks.delete_expired_sessions',
        'schedule': crontab(minute="0", hour='*/2'),
    },
    "update-printers-resources-regular": {
        'task': 'monitoring.tasks.update_printer_resource_regular',
        'schedule': crontab(minute="*/2", hour='7-19'),
    },
    "parsing-katushas-page-counts-regular": {
        "task": "monitoring.tasks.parsing_katushas_page_counts",
        "schedule": crontab(minute='0,30', hour='10,13,16'),
    },
    "parsing-avisions-page-counts-regular": {
        "task": "monitoring.tasks.parsing_avisions_page_counts",
        "schedule": crontab(minute='1,31', hour='10,13,16'),
    },
    "parsing-hps-page-counts-regular": {
        "task": "monitoring.tasks.parsing_hps_page_counts",
        "schedule": crontab(minute='2,32', hour='10,13,16'),
    },
    "parsing-pantums-page-counts-regular": {
        "task": "monitoring.tasks.parsing_pantums_page_counts",
        "schedule": crontab(minute='5,35,45', hour='10,11,13,15,16'),
    },
    "parsing-sindohs-page-counts-regular": {
        "task": "monitoring.tasks.parsing_sindohs_page_counts",
        "schedule": crontab(minute='3,33', hour='10,13,16'),
    },
    "parsing-kyoseras-page-counts-regular": {
        "task": "monitoring.tasks.parsing_kyoseras_page_counts",
        "schedule": crontab(minute='4,34', hour='10,13,16'),
    },
    "add-missing-statistics-to-db-regular": {
        "task": "monitoring.tasks.add_missing_statistics_to_db_regular",
        "schedule": crontab(minute='0', hour='19'),
    },
    "detect-device-errors-regular": {
        "task": "monitoring.tasks.detect_device_errors_regular",
        "schedule": crontab(minute="*/5", hour='7-19'),
    },
    "clear-logs-files-every-2-weeks": {
        "task": "monitoring.tasks.clear_logs_files_regular",
        "schedule": crontab(minute="0", hour="0", day_of_week='0', day_of_month='1-31/14'),
    }
}


@shared_task
def delete_expired_sessions():
    from django.contrib.sessions.models import Session
    Session.objects.filter(expire_date__lt=timezone.now()).delete()


@shared_task
def scan_subnets_regular():
    from monitoring.models import IPAddress, Subnet, Printer
    from monitoring.admin import add_printer, create_printer

    subnets = Subnet.objects.all()
    for subnet in subnets:
        ips = scan_subnet(f"{subnet.address}/{subnet.mask}")
        for ip in ips:
            try:
                existing_ip = IPAddress.objects.get(address=ip)
            except ObjectDoesNotExist:
                new_ip = create_new_ip_address(ip, subnet)
                printer_info = add_printer_parsing_snmp(str(ip))
                try:
                    update_existing_printer(printer_info, new_ip)
                except ObjectDoesNotExist:
                    printer = create_printer(printer_info, new_ip)
                    custom_logger.info(f"Printer {printer} has been added successfully")
            else:
                try:
                    existing_printer = Printer.objects.get(ip_address=existing_ip)
                except ObjectDoesNotExist:
                    printer = add_printer(existing_ip)
                    printer.ip_address = existing_ip
                    printer.save()
                    custom_logger.info(f"Printer {printer} has been added successfully")


def create_new_ip_address(ip, subnet):
    from monitoring.models import IPAddress

    new_ip = IPAddress(address=ip, subnet=subnet)
    new_ip.save()

    custom_logger.info(f"IP address {ip} has been added successfully")

    return new_ip


def update_existing_printer(printer_info, ip):
    from monitoring.models import Printer

    existing_printer = Printer.objects.get(model__stamp__name=printer_info[0],
                                           model__name=printer_info[1],
                                           serial_number=printer_info[2])
    existing_printer.ip_address = ip
    existing_printer.is_archived = False
    existing_printer.is_active = True
    existing_printer.save()


@shared_task
def checking_activity_regular():
    from monitoring.models import Printer

    printers = Printer.objects.all()
    for printer in printers:
        activity_printer = checking_activity(str(printer.ip_address))
        if printer.is_active != activity_printer:
            printer.is_active = activity_printer
            printer.save()
            custom_logger.info(f"Printer {printer} activity has been changed to {activity_printer}")


@shared_task
def async_update_printer_resource(printer_id):
    update_printer_resource(printer_id)


@shared_task
def update_printer_resource_regular():
    from monitoring.models import Printer

    printer_ids = Printer.objects.values('id')
    for printer_id in printer_ids:
        async_update_printer_resource.delay(printer_id['id'])


@shared_task
def parsing_katushas_page_counts():
    from monitoring.models import Printer

    katushas = Printer.objects.filter(model__stamp__name='Katusha', is_active=True)
    for katusha in katushas:
        parsing_snmp_katusha(katusha)


@shared_task
def parsing_avisions_page_counts():
    from monitoring.models import Printer

    avisions = Printer.objects.filter(model__stamp__name='Avision', is_active=True)
    for avision in avisions:
        parsing_snmp_avision(avision)


@shared_task
def parsing_hps_page_counts():
    from monitoring.models import Printer

    hps = Printer.objects.filter(model__stamp__name='Hewlett-Packard', is_active=True)
    for hp in hps:
        parsing_snmp_hp(hp)


@shared_task
def parsing_kyoseras_page_counts():
    from monitoring.models import Printer

    kyoseras = Printer.objects.filter(model__stamp__name__iexact='kyocera', is_active=True)
    for kyosera in kyoseras:
        parsing_snmp_kyosera(kyosera)


@shared_task
def parsing_pantums_page_counts():
    from monitoring.models import Printer

    pantums = Printer.objects.filter(model__stamp__name='Pantum', is_active=True)
    for pantum in pantums:
        parsing_pantum(pantum)


@shared_task
def parsing_sindohs_page_counts():
    from monitoring.models import Printer

    sindohs = Printer.objects.filter(model__stamp__name='SINDOH', is_active=True)
    for sindoh in sindohs:
        parsing_snmp_sindoh(sindoh)


@shared_task
def add_missing_statistics_to_db_regular():
    from monitoring.models import Printer

    printers = Printer.objects.all()
    for printer in printers:
        add_missing_statistics_to_db(printer)


@shared_task
def async_detect_device_errors(printer_id):
    detect_device_errors(printer_id)


@shared_task
def detect_device_errors_regular():
    from monitoring.models import Printer

    printer_ids = Printer.objects.values('id')
    for printer_id in printer_ids:
        async_detect_device_errors.delay(printer_id['id'])


@shared_task
def clear_logs_files_regular():
    from core.settings import LOGS_DIR

    file_manager = LogsFileManager(LOGS_DIR)
    file_manager.check_size()
