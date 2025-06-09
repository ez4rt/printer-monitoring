from django.test import TestCase
from monitoring.models import Subnet, IPAddress, DailyStat
from monitoring.forms import (SubnetAdminForm, IPAddressAdminForm, PrintersReportForm, StatisticsReportForm,
                              DateRangeForm, DayReportForm, MonthReportForm, SuppliesReportForm)
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch


class SubnetAdminFormTest(TestCase):
    def setUp(self):
        self.subnet = Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

    def test_form_valid_data(self):
        form_data = {
            'name': 'Test Subnet New',
            'address': '192.168.2.0',
            'mask': 24,
        }
        form = SubnetAdminForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['scan_subnet'])

    def test_form_invalid_data(self):
        form_data = {
            'name': '',
            'address': '192.168.2.0',
            'mask': 24,
        }
        form = SubnetAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_form_unique_address(self):
        form_data = {
            'name': 'Test Subnet New',
            'address': self.subnet.address,
            'mask': 24,
        }
        form = SubnetAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('address', form.errors)

    def test_scan_subnet_field_label(self):
        form = SubnetAdminForm()
        self.assertEqual(form.fields['scan_subnet'].label, "Просканировать сеть автоматически?")

    def test_scan_subnet_field_help_text(self):
        form = SubnetAdminForm()
        self.assertEqual(form.fields['scan_subnet'].help_text,
                         "Выберите этот параметр, если хотите, чтобы система автоматически просканировала сеть для "
                         "обнаружения активных устройств.")


class IPAddressAdminFormTest(TestCase):
    def setUp(self):
        self.subnet = Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = IPAddress.objects.create(address='192.168.1.1', subnet=self.subnet)

    def test_form_valid_data(self):
        form_data = {
            'address': '192.168.1.2',
            'subnet': self.subnet,
        }
        form = IPAddressAdminForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['add_printer'])

    def test_form_invalid_without_address(self):
        form_data = {
            'address': '',
            'subnet': self.subnet,
        }
        form = IPAddressAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('address', form.errors)

    def test_form_invalid_without_subnet(self):
        form_data = {
            'address': '192.168.1.2',
            'subnet': '',
        }
        form = IPAddressAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('subnet', form.errors)

    def test_form_unique_address(self):
        form_data = {
            'address': self.ip_address.address,
            'subnet': self.subnet.address,
        }
        form = IPAddressAdminForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('address', form.errors)

    def test_form_field_label(self):
        form = SubnetAdminForm()
        self.assertEqual(form.fields['scan_subnet'].label, "Просканировать сеть автоматически?")

    def test_form_help_text(self):
        form = IPAddressAdminForm()
        self.assertEqual(form.fields['add_printer'].help_text,
                         "Выберите этот параметр, если хотите, чтобы система автоматически опросила принтер.")


class PrintersReportFormTest(TestCase):
    def test_form_has_correct_fields(self):
        form = PrintersReportForm()
        self.assertIn('area', form.fields)
        self.assertEqual(form.fields['area'].label, "Выберите расположение принтеров:")
        self.assertEqual(form.fields['area'].choices, PrintersReportForm.AREAS)

    def test_form_valid_data(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        form_data = {'area': 'abakan'}
        form = PrintersReportForm(data=form_data)
        self.assertIn('Абакан', str(form))

    def test_form_invalid_data(self):
        form_data = {'area': ''}
        form = PrintersReportForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('area', form.errors)

    def test_form_choices(self):
        form = PrintersReportForm()
        self.assertEqual(form.fields['area'].choices, PrintersReportForm.AREAS)


class StatisticsReportFormTest(TestCase):
    def test_form_valid_data(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        form_data = {
            'area': 'abakan',
            'option': 'print',
            'date_field': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        form = StatisticsReportForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_area(self):
        form_data = {
            'area': '',
            'option': 'print',
            'date_field': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        form = StatisticsReportForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('area', form.errors)

    def test_form_invalid_option(self):
        form_data = {
            'area': 'abakan',
            'option': 'abcde',
            'date_field': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        form = StatisticsReportForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('option', form.errors)

    def test_form_invalid_date(self):
        form_data = {
            'area': 'abakan',
            'option': 'print',
            'date_field': '',
        }
        form = StatisticsReportForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('date_field', form.errors)


class DateRangeFormTest(TestCase):
    def test_form_valid_data(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        form_data = {
            'area': 'abakan',
            'option': 'print',
            'date_start': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'date_end': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        form = DateRangeForm(form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_date_range(self):
        form_data = {
            'area': 'abakan',
            'option': 'print',
            'date_start': '',
            'date_end': '',
        }
        form = DateRangeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('date_start', form.errors)
        self.assertIn('date_end', form.errors)


class DayReportFormTest(TestCase):
    def setUp(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        self.form_data = {
            'area': 'abakan',
            'option': 'print',
            'date_start': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'date_end': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        self.form = DayReportForm(data=self.form_data)

    def test_form_is_valid(self):
        self.assertTrue(self.form.is_valid())
        self.assertEqual(self.form.cleaned_data['option'], 'print')

    def test_form_invalid(self):
        form = DayReportForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('option', form.errors)
        self.assertIn('area', form.errors)
        self.assertIn('date_start', form.errors)
        self.assertIn('date_end', form.errors)

    def test_options_displayed(self):
        expected_options = dict(DayReportForm.OPTIONS)
        form_options = dict(self.form.fields['option'].choices)
        self.assertEqual(expected_options, form_options)


class MonthReportFormTest(TestCase):
    def setUp(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        self.form_data = {
            'area': 'abakan',
            'option': 'scan',
            'date_start': (timezone.now() - timedelta(days=1)).strftime('%Y-%m'),
            'date_end': (timezone.now() - timedelta(days=1)).strftime('%Y-%m'),
        }
        self.form = MonthReportForm(data=self.form_data)

    def test_form_is_valid(self):
        self.assertTrue(self.form.is_valid())
        self.assertEqual(self.form.cleaned_data['option'], 'scan')

    def test_form_invalid(self):
        form = MonthReportForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('option', form.errors)
        self.assertIn('area', form.errors)
        self.assertIn('date_start', form.errors)
        self.assertIn('date_end', form.errors)

    def test_options_displayed(self):
        expected_options = dict(MonthReportForm.OPTIONS)
        form_options = dict(self.form.fields['option'].choices)
        self.assertEqual(expected_options, form_options)


class SuppliesReportFormTest(TestCase):
    def setUp(self):
        Subnet.objects.create(name='abakan', address='192.168.1.0', mask=24)
        self.form_data = {
            'area': 'abakan',
            'date_start': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'date_end': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        self.form = SuppliesReportForm(data=self.form_data)

    def test_form_is_valid(self):
        self.assertTrue(self.form.is_valid())

    def test_form_invalid(self):
        form = SuppliesReportForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('area', form.errors)
        self.assertIn('date_start', form.errors)
        self.assertIn('date_end', form.errors)
