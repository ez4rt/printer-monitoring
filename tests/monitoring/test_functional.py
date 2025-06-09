from django.test import TestCase, Client, TransactionTestCase
from monitoring import models
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from urllib.parse import urlparse
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.db.models import Max, Sum, Min
from datetime import datetime, timedelta
import os
import time
import pandas as pd
from selenium.webdriver.chrome.options import Options
from core.settings import BASE_DIR


class CreateDataForTestDatabase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])


class DataLoadTest(CreateDataForTestDatabase):
    def test_subnets_count(self):
        self.assertEqual(models.Subnet.objects.count(), len(self.subnets))

    def test_ip_addresses_count(self):
        self.assertEqual(models.IPAddress.objects.count(), len(self.ip_addresses))

    def test_cabinets_counts(self):
        self.assertEqual(models.Cabinet.objects.count(), len(self.cabinets))

    def test_departments_counts(self):
        self.assertEqual(models.Department.objects.count(), len(self.departments))

    def test_locations_counts(self):
        self.assertEqual(models.Location.objects.count(), len(self.locations))

    def test_stamps_counts(self):
        self.assertEqual(models.PrinterStamp.objects.count(), len(self.printer_stamps))

    def test_models_counts(self):
        self.assertEqual(models.PrinterModel.objects.count(), len(self.printer_models))

    def test_supply_items_counts(self):
        self.assertEqual(models.SupplyItem.objects.count(), len(self.supply_items))

    def test_inv_numbers_counts(self):
        self.assertEqual(models.InventoryNumber.objects.count(), len(self.inventory_numbers))

    def test_printers_count(self):
        self.assertEqual(models.Printer.objects.count(), len(self.printers))

    def test_printers_supplies_count(self):
        self.assertEqual(models.PrinterSupplyStatus.objects.count(), len(self.printers_supplies))

    def test_supply_details_count(self):
        self.assertEqual(models.SupplyDetails.objects.count(), len(self.supply_details))

    def test_statistics_count(self):
        self.assertEqual(models.Statistics.objects.count(), len(self.statistics))

    def test_daily_stats_count(self):
        self.assertEqual(models.DailyStat.objects.count(), len(self.daily_stats))

    def test_monthly_stats_count(self):
        self.assertEqual(models.MonthlyStat.objects.count(), len(self.monthly_stats))

    def test_change_supplies_count(self):
        self.assertEqual(models.ChangeSupply.objects.count(), len(self.change_supplies))

    def test_forecast_stats_count(self):
        self.assertEqual(models.ForecastStat.objects.count(), len(self.forecast_stats))

    def test_forecast_count(self):
        self.assertEqual(models.Forecast.objects.count(), len(self.forecast))

    def test_forecast_change_supplies_count(self):
        self.assertEqual(models.ForecastChangeSupplies.objects.count(), len(self.forecast_change_supplies))

    def test_maintenance_costs_count(self):
        self.assertEqual(models.MaintenanceCosts.objects.count(), len(self.maintenance_costs))

    def test_printer_errors_count(self):
        self.assertEqual(models.PrinterError.objects.count(), len(self.printer_errors))


class TestLoginFunctionality(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        cls.driver = webdriver.Chrome(options=options)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_login(self):
        user = User.objects.first()
        assert User.objects.filter(username='test_user').exists(), "Пользователь не найден"
        assert user.check_password('12345qwert'), "Пароль неверный"
        driver = self.driver
        driver.get(self.live_server_url)
        self.assertEqual(urlparse(self.driver.current_url).path, '/accounts/login/')

        username_input = driver.find_element(By.NAME, 'username')
        password_input = driver.find_element(By.NAME, 'password')
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        self.assertEqual(urlparse(self.driver.current_url).path, '/')
        assert "Мониторинг принтеров" in driver.page_source, "Заголовок страницы не найден"
        assert "test_user" in driver.page_source, "Имя пользователя не найдено"
        assert "Пользователь" in driver.page_source, "Права доступа пользователя не найдены"


class TestLogoutFunctionality(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_logout(self):
        driver = self.driver
        driver.get(self.live_server_url)

        username_input = driver.find_element(By.NAME, 'username')
        password_input = driver.find_element(By.NAME, 'password')
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        user_text = driver.find_element(By.XPATH, '/html/body/div[2]/div[3]/div/nav/div/ul/li[4]/a/div/span/strong')
        user_text.click()

        exit_button = driver.find_element(By.XPATH, '/html/body/div[2]/div[3]/div/nav/div/ul/li[4]/div/a[3]/span') # exit
        exit_button.click()

        self.assertEqual(urlparse(self.driver.current_url).path, '/accounts/logout/')
        assert "Вы вышли из системы" in driver.page_source, "Заголовок страницы не найден"
        assert "Нажмите сюда, чтобы перейти в окно авторизации" in driver.page_source, \
            "Текст с переходом на страницу входа не найден"


class TestChangePasswordFunctionality(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_change_password(self):
        driver = self.driver
        driver.get(self.live_server_url)

        username_input = driver.find_element(By.NAME, 'username')
        password_input = driver.find_element(By.NAME, 'password')
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        user_text = driver.find_element(By.XPATH, '/html/body/div[2]/div[3]/div/nav/div/ul/li[4]/a/div/span/strong')
        user_text.click()

        passwd_button = driver.find_element(By.XPATH,
                                                   '/html/body/div[2]/div[3]/div/nav/div/ul/li[4]/div/a[2]/span')
        passwd_button.click()

        self.assertEqual(urlparse(self.driver.current_url).path, '/accounts/password_change/')
        assert "Смена пароля" in driver.page_source, "Заголовок страницы не найден"
        old_password_input = driver.find_element(By.NAME, 'old_password')
        new_password1_input = driver.find_element(By.NAME, 'new_password1')
        new_password2_input = driver.find_element(By.NAME, 'new_password2')
        change_passwd_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        old_password_input.send_keys('12345qwert')
        new_password1_input.send_keys('!@#$%QWert')
        new_password2_input.send_keys('!@#$%QWert')
        change_passwd_button.click()

        user = User.objects.first()
        assert User.objects.filter(username='test_user').exists(), "Пользователь не найден"
        assert user.check_password('!@#$%QWert'), "Пароль неверный"
        self.assertEqual(urlparse(self.driver.current_url).path, '/accounts/password_change/done/')
        assert "Пароль успешно изменен" in driver.page_source, "Заголовок страницы не найден"
        assert "Вернуться на главную страницу" in driver.page_source, "Текст с переходом на страницу входа не найден"


class TestMainPageValues(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_values(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        element_total_pages = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[5]/div/div/div[1]/div/div/div/div/h4'))
        )
        actual_text_total_pages = element_total_pages.text

        last_records_stat = models.Statistics.objects.values('printer').annotate(last_time=Max('time_collect'))
        expected_total_pages = models.Statistics.objects.filter(
            time_collect__in=[record['last_time'] for record in last_records_stat]
        ).aggregate(total_page_sum=Sum('page'))

        self.assertEqual(actual_text_total_pages, str(expected_total_pages['total_page_sum']))

        element_daily_scan = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[5]/div/div/div[6]/div/div/div/div/div/h3'))
        )
        actual_text_daily_scan = element_daily_scan.text

        last_records_daily_stat = models.DailyStat.objects.values('printer').annotate(last_time=Max('time_collect'))
        expected_daily_scan = models.DailyStat.objects.filter(
            time_collect__in=[record['last_time'] for record in last_records_daily_stat]
        ).aggregate(total_scan_sum=Sum('scan'))

        self.assertEqual(actual_text_daily_scan, str(expected_daily_scan['total_scan_sum']))

        element_weekly_print = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[5]/div/div/div[8]/div/div[1]/div/div/h5'))
        )
        actual_text_weekly_print = element_weekly_print.text

        last_time_collect = models.DailyStat.objects.latest('time_collect').time_collect.date()
        first_time_collect_weekly_print = models.DailyStat.objects.latest(
            'time_collect').time_collect.date() - timedelta(days=6)
        start_datetime_week = datetime.strptime(first_time_collect_weekly_print.strftime('%Y-%m-%d'), '%Y-%m-%d')
        end_datetime = datetime.strptime(last_time_collect.strftime('%Y-%m-%d'), '%Y-%m-%d')
        start_datetime_week = start_datetime_week.replace(hour=0, minute=0)
        end_datetime = end_datetime.replace(hour=23, minute=59)

        expected_weekly_print = models.DailyStat.objects.filter(
            time_collect__range=(start_datetime_week, end_datetime)
        ).aggregate(total_print=Sum('print'))

        self.assertEqual(actual_text_weekly_print, str(expected_weekly_print['total_print']))

        element_monthly_pages = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[5]/div/div/div[11]/div/div[1]/div[1]/p')) # СТАТИСТИКА ЗА МЕСЯЦ (Общее количество страниц: 30000)
        )
        actual_text_monthly_pages = element_monthly_pages.text

        first_time_collect_weekly_print = models.DailyStat.objects.latest(
            'time_collect').time_collect.date() - timedelta(days=30)
        start_datetime_month = datetime.strptime(first_time_collect_weekly_print.strftime('%Y-%m-%d'), '%Y-%m-%d')
        start_datetime_month = start_datetime_month.replace(hour=0, minute=0)

        expected_monthly_pages = models.DailyStat.objects.filter(
            time_collect__range=(start_datetime_month, end_datetime)
        ).aggregate(total_page=Sum('page'))

        self.assertEqual(actual_text_monthly_pages,
                         f"Общее количество страниц: {expected_monthly_pages['total_page']}")

        assert 'Последние события' in self.driver.page_source, 'Текст Последние события не найдены'
        assert 'Принтеры' in self.driver.page_source, 'Текст Принтеры не найдены'

        expected_qty_printers = models.Printer.objects.all().count()
        expected_qty_printers_text = f'Отображается от 1 до 10 из {expected_qty_printers} записей'
        assert expected_qty_printers_text in self.driver.page_source, "Количество принтеров в таблице не совпадает"

        toner_residue_button = self.driver.find_element(
            By.XPATH,
            "/html/body/div[2]/div[5]/div/div/div[13]/div/div[2]/div/div/table/thead/tr/th[6]/p"
        )
        toner_residue_button.click()


class TestNavigationFromMainToSinglePrinter(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)
            cls.driver.set_window_size(1920, 1080)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_navigation_from_main_to_single_printer(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        li_printers_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[4]/div/ul/li[2]/a"))
        )
        li_printers_button.click()

        li_span_area_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div[2]/ul/li[2]/a"))
        )
        li_span_area_button.click()

        li_a_models_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div[2]/ul/li[2]/ul/li/a"))
        )
        li_a_models_button.click()

        li_a_printer_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH,
                                              "/html/body/div[2]/div[2]/div/div[1]/div[2]/ul/li[2]/ul/li/ul/li[1]/a"))
        )
        li_a_printer_button.click()

        first_printer = models.Printer.objects.first()

        self.assertEqual(urlparse(self.driver.current_url).path, f"/{first_printer.id}")


class TestNavigationFromMainToReports(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)
            cls.driver.set_window_size(1920, 1080)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_navigation_from_main_to_reports(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        li_printers_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[4]/div/ul/li[3]/a"))
        )
        li_printers_button.click()

        li_span_area_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div[3]/ul/li[2]/a"))
        )
        li_span_area_button.click()

        self.assertEqual(urlparse(self.driver.current_url).path, f"/reports")


class TestNavigationFromMainToEvents(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)
            cls.driver.set_window_size(1920, 1080)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_navigation_from_main_to_events(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        li_printers_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[4]/div/ul/li[3]/a"))
        )
        li_printers_button.click()

        li_span_area_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div[3]/ul/li[3]/a"))
        )
        li_span_area_button.click()

        self.assertEqual(urlparse(self.driver.current_url).path, f"/events")


class TestChangeTheme(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user', password='12345qwert')
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_change_theme(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        body_with_light_element = self.driver.find_element(By.TAG_NAME, 'body')
        theme_version_light = body_with_light_element.get_attribute('data-theme-version')
        self.assertEqual(theme_version_light, 'light')

        change_theme_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[2]/div[3]/div/nav/div/ul/li[1]/a"))
        )
        change_theme_button.click()

        body_with_dark_element = self.driver.find_element(By.TAG_NAME, 'body')
        theme_version_dark = body_with_dark_element.get_attribute('data-theme-version')
        self.assertEqual(theme_version_dark, 'dark')


class TestExportReport(StaticLiveServerTestCase, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open('tests/monitoring/test_data.json', 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            cls.subnets = data['subnets']
            cls.ip_addresses = data['ip_addresses']
            cls.cabinets = data['cabinets']
            cls.departments = data['departments']
            cls.locations = data['locations']
            cls.printer_stamps = data['printer_stamps']
            cls.printer_models = data['printer_models']
            cls.supply_items = data['supply_items']
            cls.inventory_numbers = data['inventory_numbers']
            cls.printers_supplies = data['printers_supplies']
            cls.supply_details = data['supply_details']
            cls.printers = data['printers']
            cls.statistics = data['statistics']
            cls.daily_stats = data['daily_stats']
            cls.monthly_stats = data['monthly_stats']
            cls.change_supplies = data['change_supplies']
            cls.forecast_stats = data['forecast_stats']
            cls.forecast = data['forecast']
            cls.forecast_change_supplies = data['forecast_change_supplies']
            cls.maintenance_costs = data['maintenance_costs']
            cls.printer_errors = data['printer_errors']
            cls.client = Client()
            cls.user = User.objects.create_user(username='test_user', password='12345qwert')
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            cls.driver = webdriver.Chrome(options=options)
            cls.driver.set_window_size(1920, 1080)

        cls.create_test_data()

    @classmethod
    def create_test_data(cls):
        models.Subnet.objects.bulk_create([models.Subnet(**subnet) for subnet in cls.subnets])
        models.IPAddress.objects.bulk_create([models.IPAddress(**ip) for ip in cls.ip_addresses])
        models.Cabinet.objects.bulk_create([models.Cabinet(**cabinet) for cabinet in cls.cabinets])
        models.Department.objects.bulk_create([models.Department(**department) for department in cls.departments])
        models.Location.objects.bulk_create([models.Location(**location) for location in cls.locations])
        models.PrinterStamp.objects.bulk_create([models.PrinterStamp(**stamp) for stamp in cls.printer_stamps])
        models.PrinterModel.objects.bulk_create([models.PrinterModel(**model) for model in cls.printer_models])
        models.SupplyItem.objects.bulk_create([models.SupplyItem(**supply_item) for supply_item in cls.supply_items])
        models.InventoryNumber.objects.bulk_create(
            [models.InventoryNumber(**in_num) for in_num in cls.inventory_numbers])
        models.Printer.objects.bulk_create([models.Printer(**printer) for printer in cls.printers])
        models.PrinterSupplyStatus.objects.bulk_create(
            [models.PrinterSupplyStatus(**printer_supply) for printer_supply in cls.printers_supplies])
        models.SupplyDetails.objects.bulk_create(
            [models.SupplyDetails(**sup_detail) for sup_detail in cls.supply_details])
        models.Statistics.objects.bulk_create([models.Statistics(**stat) for stat in cls.statistics])
        models.DailyStat.objects.bulk_create([models.DailyStat(**daily_stat) for daily_stat in cls.daily_stats])
        models.MonthlyStat.objects.bulk_create(
            [models.MonthlyStat(**monthly_stat) for monthly_stat in cls.monthly_stats])
        models.ChangeSupply.objects.bulk_create([models.ChangeSupply(**change) for change in cls.change_supplies])
        models.ForecastStat.objects.bulk_create([models.ForecastStat(**forecast) for forecast in cls.forecast_stats])
        models.Forecast.objects.bulk_create([models.Forecast(**forecast) for forecast in cls.forecast])
        models.ForecastChangeSupplies.objects.bulk_create(
            [models.ForecastChangeSupplies(**forecast_change) for forecast_change in cls.forecast_change_supplies])
        models.MaintenanceCosts.objects.bulk_create([models.MaintenanceCosts(**cost) for cost in cls.maintenance_costs])
        models.PrinterError.objects.bulk_create([models.PrinterError(**error) for error in cls.printer_errors])

    @classmethod
    def tearDown(cls):
        super().tearDownClass()
        cls.driver.quit()

    def test_export_report(self):
        self.driver.get(self.live_server_url)

        username_input = self.driver.find_element(By.NAME, 'username')
        password_input = self.driver.find_element(By.NAME, 'password')
        login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys('test_user')
        password_input.send_keys('12345qwert')
        login_button.click()

        self.driver.get(f"{self.live_server_url}/report/page/7days")

        upload_button = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div[3]/button"))
        )
        self.driver.execute_script("arguments[0].click();", upload_button)

        time.sleep(5)

        downloads_path = BASE_DIR

        file_name = "Отчёт общего количества страниц за последние 7 дней.xlsx"
        file_path = os.path.join(downloads_path, file_name)

        assert os.path.exists(file_path), 'Файл не был загружен'
        df = pd.read_excel(file_path)
        os.remove(file_path)

        actual_num_rows, actual_num_columns = df.shape

        printer_count = models.Printer.objects.count()
        expected_num_rows = printer_count + 1
        expected_num_columns = 10

        self.assertEqual(actual_num_rows, expected_num_rows)
        self.assertEqual(actual_num_columns, expected_num_columns)

