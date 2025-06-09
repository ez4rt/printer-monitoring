import subprocess
import re
from snmp import Engine, SNMPv2c
from snmp.manager.v2c import SNMPv2cManager
from ping3 import ping
import logging
import time
from django.utils import timezone
import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from functools import wraps
from automation.snmp_oid_map import (device_snmp_map, printer_stamp_snmp_set, printer_supplies_dict,
                                     printer_errors_snmp_dict)
from datetime import timedelta


logger_main = logging.getLogger('automation')


def scan_subnet(subnet) -> list:
    command = f"nmap -p 515,9100 {subnet} | grep 'report\|open'"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    nmap_output = output.decode('utf-8')

    ip_pattern = re.compile(r'Nmap scan report for (\d+\.\d+\.\d+\.\d+)')

    lines = nmap_output.splitlines()

    current_ip = None
    active_ips = list()

    for line in range(len(lines)):
        ip_match = ip_pattern.search(lines[line])
        if ip_match:
            current_ip = ip_match.group(1)
        else:
            if current_ip:
                active_ips.append(current_ip)
                current_ip = None
    return active_ips


def fetch_snmp_data_to_str(ip_printer: SNMPv2cManager, stamp: str, nm_oid: str) -> str:
    response = str(
        ip_printer.get(device_snmp_map[stamp][nm_oid],
                       wait=True, timeout=15.0, refreshPeriod=1.0))
    match = re.search(r"'(.*?)'", response)
    if match:
        return match.group(1)
    return 'Empty'


def fetch_snmp_data_to_int(ip_printer: SNMPv2cManager, stamp: str, nm_oid: str) -> int:
    response = str(
        ip_printer.get(device_snmp_map[stamp][nm_oid],
                       wait=True, timeout=15.0, refreshPeriod=1.0))
    match = re.search(r'\((\d+)\)', response)
    if match:
        return int(match.group(1))


def add_printer_parsing_snmp(ip_address: str) -> list:
    if ping(ip_address) is False:
        pass
    else:
        try:
            with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
                temp_value = None
                ip_printer = engine.Manager(ip_address)
                for oid in printer_stamp_snmp_set:
                    response = str(ip_printer.get(oid, wait=True, timeout=15.0, refreshPeriod=1.0))
                    match = re.search(r"'(.*?)'", response)
                    if match:
                        extracted_value = match.group(1)
                        words_in_value = extracted_value.split()
                        if words_in_value:
                            value = words_in_value[0]
                            if value == 'HP':
                                value = 'Hewlett-Packard'
                            stamp = value.lower()
                            if stamp in device_snmp_map:
                                if stamp == 'sindoh':
                                    model_value = words_in_value[1]
                                else:
                                    model_value = fetch_snmp_data_to_str(ip_printer, stamp, 'model')
                                serial_num_value = fetch_snmp_data_to_str(ip_printer, stamp, 'serial_num')
                                return [value, model_value, serial_num_value]
                            else:
                                temp_value = value[:16]
                                stamp = 'katusha'
                                model_value = fetch_snmp_data_to_str(ip_printer, stamp, 'model')
                                serial_num_value = fetch_snmp_data_to_str(ip_printer, stamp, 'serial_num')
                return [temp_value, model_value, serial_num_value]

        except Exception as e:
            logger_main.error(f"{ip_address}: {e} - Error in launching the SNMP engine in the add_printer_parsing_snmp"
                              f" function")

    return ['Printer', 'Model', 'Serial_Number']


def checking_activity(ip_address: str) -> bool:
    if ping(ip_address):
        return True
    return False


def printer_init_resource(printer):
    stamp = get_printer_stamp(printer)
    if stamp:
        try:
            with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
                ip_printer = engine.Manager(str(printer.ip_address.address))
                for nm_sup in printer_supplies_dict['supply']:
                    if nm_sup in device_snmp_map[stamp]:
                        extracted_value = fetch_snmp_data_to_str(ip_printer, stamp, nm_sup)
                        if stamp == 'hewlett-packard':
                            if nm_sup == 'black_cartridge':
                                if len(extracted_value) > 20:
                                    match = re.search(r"\b(?:C[EF]\d{3}[A-Z])\b", extracted_value)
                                    if match:
                                        extracted_value = match.group()
                                    else:
                                        extracted_value = extracted_value[:20]
                        if stamp == 'hewlett-packard-color':
                            values = extracted_value.split()
                            extracted_value = values[3]

                        supply = create_new_supply_item(nm_sup, extracted_value)
                        create_new_supply_details(supply)
                        nm_res_sup = 'resource_' + nm_sup
                        remaining_supply_percentage = fetch_snmp_data_to_int(ip_printer, stamp, nm_res_sup)
                        if remaining_supply_percentage:
                            if 'cartridge' in nm_sup:
                                add_supply_in_printer(printer, supply, remaining_supply_percentage, 3000)
                            else:
                                add_supply_in_printer(printer, supply, remaining_supply_percentage, 20000)

                printer.save()

        except Exception as e:
            logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the printer_init_resource "
                              f"function")


def create_new_supply_item(nm_oid: str, nm_supply: str):
    from monitoring.models import SupplyItem

    color_supply, type_supply = split_nm_supply(nm_oid)

    supply, created = SupplyItem.objects.get_or_create(
        name=nm_supply,
        defaults={
            'type': type_supply,
            'color': color_supply,
            'price': 0.00
        }
    )
    return supply


def split_nm_supply(nm_oid: str):
    parts = nm_oid.split('_', 1)

    color_supply = parts[0]
    type_supply = parts[1] if len(parts) > 1 else ''

    return color_supply, type_supply


def create_new_supply_details(supply):
    from monitoring.models import SupplyDetails

    supply, created = SupplyDetails.objects.get_or_create(
        supply=supply,
        defaults={
            'supply': supply,
            'qty': 0,
        }
    )

    return supply


def get_printer_stamp(printer):
    stamp = str(printer.model.stamp.name).lower()

    if stamp not in device_snmp_map:
        stamp = 'katusha'
    if 'M283fdn' in printer.model.name:
        stamp += '-color'
    if printer.model.name == 'FS-1028MFP':
        return

    return stamp


def add_supply_in_printer(printer, supply, remaining_supply_percentage, qty_page):
    from monitoring.models import PrinterSupplyStatus
    PrinterSupplyStatus.objects.create(
        printer=printer,
        supply=supply,
        remaining_supply_percentage=remaining_supply_percentage,
        consumption=qty_page,
    )


def update_printer_resource(printer_id):
    from monitoring.models import Printer

    printer = Printer.objects.get(pk=printer_id)
    if printer.is_active:
        stamp = get_printer_stamp(printer)

        if stamp:
            try:
                with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
                    ip_printer = engine.Manager(str(printer.ip_address.address))
                    for nm_supply_oid in printer_supplies_dict['supply']:
                        nm_res_supply_oid = 'resource_' + nm_supply_oid
                        if nm_res_supply_oid in device_snmp_map[stamp]:
                            extracted_value = fetch_snmp_data_to_int(ip_printer, stamp, nm_res_supply_oid)
                            if extracted_value:
                                printer_supply_status = get_printer_supply_status(printer, nm_supply_oid)
                                update_printer_supply_status(printer_supply_status, extracted_value)

                    printer.save()
            except Exception as e:
                logger_main.error(
                    f"{printer}: {e} - Error in launching the SNMP engine in the update_printer_resource function")


def get_printer_supply_status(printer, nm_supply_oid: str):
    from monitoring.models import PrinterSupplyStatus

    color_supply, type_supply = split_nm_supply(nm_supply_oid)

    query = PrinterSupplyStatus.objects.filter(
        printer=printer,
        supply__type=type_supply,
        supply__color=color_supply
    ).first()

    return query


def update_printer_supply_status(printer_supply_status, new_remaining_supply_percentage):
    current_value = printer_supply_status.remaining_supply_percentage
    new_consumption = None

    if current_value != new_remaining_supply_percentage:
        if current_value < new_remaining_supply_percentage:
            supply = printer_supply_status.supply
            printer = printer_supply_status.printer
            average_printer_supply_consumption = printer_supply_status.consumption

            update_qty_supply(supply)
            create_change_supply(printer, supply)
            new_consumption = calculate_average_printer_supply_consumption(printer, supply,
                                                                           average_printer_supply_consumption)

    printer_supply_status.remaining_supply_percentage = new_remaining_supply_percentage
    if new_consumption:
        printer_supply_status.consumption = new_consumption
    printer_supply_status.save()


def update_qty_supply(supply):
    from monitoring.models import SupplyDetails

    supply_details = SupplyDetails.objects.get(supply=supply)
    supply_details.qty -= 1
    supply_details.save()


def create_change_supply(printer, supply):
    from monitoring.models import ChangeSupply

    new_change_supply = ChangeSupply(
        printer=printer,
        supply=supply,
    )
    new_change_supply.save()


def calculate_average_printer_supply_consumption(printer, supply, average_printer_supply_consumption):
    from monitoring.models import ChangeSupply, ForecastStat

    last_two_change_supplies = ChangeSupply.objects.filter(printer=printer, supply=supply).order_by('-id')[:2]
    if len(last_two_change_supplies) == 2:
        current_stat = ForecastStat.objects.filter(printer=printer).last()

        recent_date = last_two_change_supplies[1].time_change.date()
        recent_stat = ForecastStat.objects.get(printer=printer, time_collect=recent_date)

        current_consumption = current_stat.copies_printing - recent_stat.copies_printing

        return (average_printer_supply_consumption + current_consumption) // 2


def save_printer_stats_to_database(printer, page_value: int, print_value: int, copies_value: int, scan_value: int):
    from monitoring.models import Statistics, DailyStat, MonthlyStat, ForecastStat

    last_record = Statistics.objects.filter(printer=printer).last()

    new_stat = Statistics(
        printer=printer,
        page=page_value,
        print=print_value,
        copies=copies_value,
        scan=scan_value,
    )
    new_stat.save()

    new_forecast_stat = ForecastStat(
        printer=printer,
        copies_printing=copies_value + print_value,
    )
    new_forecast_stat.save()

    if last_record:
        new_daily_stat = DailyStat(
            printer=printer,
            page=page_value - last_record.page,
            print=print_value - last_record.print,
            copies=copies_value - last_record.copies,
            scan=scan_value - last_record.scan,
        )
        new_daily_stat.save()

        last_record_monthly = MonthlyStat.objects.filter(printer=printer).last()
        if last_record_monthly:
            current_month = timezone.now().month
            last_record_month = last_record_monthly.time_collect.month
            if last_record_month == current_month:
                last_record_monthly.page += new_daily_stat.page
                last_record_monthly.print += new_daily_stat.print
                last_record_monthly.copies += new_daily_stat.copies
                last_record_monthly.scan += new_daily_stat.scan
                last_record_monthly.time_collect = timezone.now()
                last_record_monthly.save()
            else:
                new_monthly_stat = MonthlyStat(
                    printer=printer,
                    page=new_daily_stat.page,
                    print=new_daily_stat.print,
                    copies=new_daily_stat.copies,
                    scan=new_daily_stat.scan,
                )
                new_monthly_stat.save()

    else:
        new_daily_stat = DailyStat(
            printer=printer,
            page=0,
            print=0,
            copies=0,
            scan=0,
        )
        new_daily_stat.save()

        new_monthly_stat = MonthlyStat(
            printer=printer,
            page=0,
            print=0,
            copies=0,
            scan=0,
        )
        new_monthly_stat.save()


def parsing_snmp(func):
    @wraps(func)
    def wrapper(printer, *args, **kwargs):
        from monitoring.models import Statistics
        today = timezone.now().date()
        if printer.is_active:
            statistics_today = Statistics.objects.filter(printer=printer, time_collect__date=today)
            if not statistics_today.exists():
                page_value, print_value, copies_value, scan_value = func(printer, *args, **kwargs)
                printer_info_stats = {
                    'printer': printer,
                    'page_value': page_value,
                    'print_value': print_value,
                    'copies_value': copies_value,
                    'scan_value': scan_value,
                }
                save_printer_stats_to_database(**printer_info_stats)
        return func(printer, *args, **kwargs)
    return wrapper


@parsing_snmp
def parsing_snmp_katusha(printer):
    stamp = str(printer.model.stamp.name).lower()
    try:
        with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
            ip_printer = engine.Manager(str(printer.ip_address.address))
            print_value = fetch_snmp_data_to_int(ip_printer, stamp, 'print')
            copies_value = fetch_snmp_data_to_int(ip_printer, stamp, 'copies')
            scan_value = fetch_snmp_data_to_int(ip_printer, stamp, 'scan_apd')
            scan_value += fetch_snmp_data_to_int(ip_printer, stamp, 'scan_tablet')
            page_value = print_value + copies_value + scan_value
            return page_value, print_value, copies_value, scan_value
    except Exception as e:
        logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_katusha function")


@parsing_snmp
def parsing_snmp_avision(printer):
    stamp = str(printer.model.stamp.name).lower()
    try:
        with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
            ip_printer = engine.Manager(str(printer.ip_address.address))
            print_value = fetch_snmp_data_to_int(ip_printer, stamp, 'print')
            copies_value = fetch_snmp_data_to_int(ip_printer, stamp, 'copies_small')
            copies_value += fetch_snmp_data_to_int(ip_printer, stamp, 'copies_big')
            scan_value = fetch_snmp_data_to_int(ip_printer, stamp, 'scan_apd')
            scan_value += fetch_snmp_data_to_int(ip_printer, stamp, 'scan_tablet')
            page_value = print_value + copies_value + scan_value
            return page_value, print_value, copies_value, scan_value
    except Exception as e:
        logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_avision function")


@parsing_snmp
def parsing_snmp_hp(printer):
    stamp = str(printer.model.stamp.name).lower()
    if 'M283fdn' in printer.model.name:
        stamp += '-color'
    try:
        with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
            ip_printer = engine.Manager(str(printer.ip_address.address))
            print_value = fetch_snmp_data_to_int(ip_printer, stamp, 'print')
            if stamp == 'hewlett-packard-color':
                copies_value = 0
                scan_value = fetch_snmp_data_to_int(ip_printer, stamp, 'scan_apd')
                scan_value += fetch_snmp_data_to_int(ip_printer, stamp, 'scan_tablet')
                page_value = print_value + copies_value + scan_value
            else:
                page_value = print_value
                copies_value = 0
                scan_value = 0
            return page_value, print_value, copies_value, scan_value
    except Exception as e:
        logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_hp function.")


@parsing_snmp
def parsing_snmp_kyosera(printer):
    stamp = str(printer.model.stamp.name).lower()
    try:
        with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
            ip_printer = engine.Manager(str(printer.ip_address.address))
            print_value = fetch_snmp_data_to_int(ip_printer, stamp, 'print')
            copies_value = fetch_snmp_data_to_int(ip_printer, stamp, 'copies')
            if printer.model == 'FS-1028MFP':
                scan_value = fetch_snmp_data_to_int(ip_printer, stamp, 'scan-fs')
            else:
                scan_value = fetch_snmp_data_to_int(ip_printer, stamp, 'scan')
            page_value = print_value + copies_value + scan_value
            return page_value, print_value, copies_value, scan_value
    except Exception as e:
        logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_kyosera function")


@parsing_snmp
def parsing_snmp_sindoh(printer):
    stamp = str(printer.model.stamp.name).lower()
    try:
        with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
            ip_printer = engine.Manager(str(printer.ip_address.address))
            print_value = fetch_snmp_data_to_int(ip_printer, stamp, 'print_copies')
            copies_value = 0
            scan_value = 0
            page_value = print_value + copies_value + scan_value
            return page_value, print_value, copies_value, scan_value
    except Exception as e:
        logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_sindoh function")


def parsing_pantum(printer):
    from monitoring.models import Statistics

    def parsing_snmp_pantum(printer_pantum):
        stamp = str(printer.model.stamp.name).lower()
        try:
            with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
                ip_printer = engine.Manager(str(printer_pantum.ip_address.address))
                print_val = fetch_snmp_data_to_int(ip_printer, stamp, 'print')
                return print_val
        except Exception as e:
            logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the parsing_snmp_pantum "
                              f"function")

    def web_scraping_pantum(ip_address: str) -> tuple:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        try:
            driver.get(f"http://{ip_address}/index.html")
            wait = WebDriverWait(driver, 60)
            element_device = wait.until(ec.presence_of_element_located((By.XPATH, '//*[@id="DEVICE"]')))
            element_device.click()
            time.sleep(5)
            value = wait.until(ec.visibility_of_element_located((By.XPATH, '//*[@id="form_main"]/div[1]/div[2]')))
            text_value = value.text
            page_val = int(text_value)
            time.sleep(5)
            element_copy = wait.until(ec.presence_of_element_located((By.XPATH, '//*[@id="COPYINFO"]')))
            element_copy.click()
            time.sleep(5)
            value = wait.until(ec.visibility_of_element_located((By.XPATH, '//*[@id="form_main"]/div[1]/div[2]')))
            text_value = value.text
            copies_val = int(text_value)

            return page_val, copies_val
        except selenium.common.exceptions.WebDriverException as e:
            if "ERR_CONNECTION_TIMED_OUT" in e.msg:
                logger_main.error(f"{printer}: Connection timed out - Error in launching the Selenium driver in the "
                                  f"web_scraping_pantum function")
            else:
                logger_main.error(f"{printer}: {e.msg} - Error in launching the Selenium driver in the "
                                  f"web_scraping_pantum function")

        driver.quit()

    try:
        if printer.is_active:
            today = timezone.now().date()
            statistics_today = Statistics.objects.filter(printer=printer, time_collect__date=today)
            if statistics_today.exists():
                pass
            else:
                print_value = parsing_snmp_pantum(printer)
                page_value, copies_value = web_scraping_pantum(str(printer.ip_address.address))

                if page_value is None:
                    raise ValueError(f"page_value cannot be None")
                if print_value is None:
                    raise ValueError(f"print_value cannot be None")
                if copies_value is None:
                    raise ValueError(f"copies_value cannot be None")

                scan_value = page_value - print_value - copies_value

                printer_info_stats = {
                    'printer': printer,
                    'page_value': page_value,
                    'print_value': print_value,
                    'copies_value': copies_value,
                    'scan_value': scan_value,
                }
                save_printer_stats_to_database(**printer_info_stats)

    except ValueError as e:
        logger_main.error(f"{printer}: {e} - Error in the parsing_pantum function")


def add_missing_statistics_to_db(printer):
    from monitoring.models import Statistics

    today = timezone.now().date()
    statistics_today = Statistics.objects.filter(printer=printer, time_collect__date=today)
    if not statistics_today.exists():
        yesterday = today - timedelta(days=1)
        statistics_yesterday = Statistics.objects.filter(printer=printer, time_collect__date=yesterday)
        if statistics_yesterday.exists():
            yesterday_stat = statistics_yesterday.first()
            page_val = yesterday_stat.page
            print_val = yesterday_stat.print
            copies_val = yesterday_stat.copies
            scan_val = yesterday_stat.scan
            save_printer_stats_to_database(printer, page_val, print_val, copies_val, scan_val)


def detect_device_errors(printer_id):
    from monitoring.models import Printer, PrinterError

    printer = Printer.objects.get(pk=printer_id)

    if printer.is_active:
        try:
            with Engine(SNMPv2c, defaultCommunity=b"public") as engine:
                ip_printer = engine.Manager(str(printer.ip_address.address))
                response = str(
                    ip_printer.get(printer_errors_snmp_dict['hrDeviceStatus'],
                                   wait=True, timeout=15.0, refreshPeriod=1.0))
                match = re.search(r'\((\d+)\)', response)
                if match:
                    device_status = int(match.group(1))
                    if device_status == 5:
                        response = str(
                            ip_printer.get(printer_errors_snmp_dict['hrPrinterDetectedErrorState'],
                                           wait=True, timeout=15.0, refreshPeriod=1.0))
                        match = re.search(r"'(.*?)'", response)
                        if match:
                            error = match.group(1)
                            if error != '\\x00':
                                new_error = PrinterError(
                                    printer=printer,
                                    description=error,
                                )
                                new_error.save()
                        else:
                            new_error = PrinterError(
                                printer=printer,
                                description=f'Unknown error - {response}',
                            )
                            new_error.save()

        except Exception as e:
            logger_main.error(f"{printer}: {e} - Error in launching the SNMP engine in the detect_device_errors "
                              f"function")

