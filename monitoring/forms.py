from django import forms
from django.utils import timezone
from datetime import timedelta
from monitoring.models import MonthlyStat, DailyStat, Subnet, IPAddress, Printer
from monitoring.views import get_area_name


class SubnetAdminForm(forms.ModelForm):
    scan_subnet = forms.BooleanField(
        required=False,
        label="Просканировать сеть автоматически?",
        help_text="Выберите этот параметр, если хотите, чтобы система автоматически просканировала сеть для "
                  "обнаружения активных устройств.",
    )

    class Meta:
        model = Subnet
        fields = '__all__'


class IPAddressAdminForm(forms.ModelForm):
    add_printer = forms.BooleanField(
        required=False,
        label="Добавить принтер автоматически?",
        help_text="Выберите этот параметр, если хотите, чтобы система автоматически опросила принтер."
    )

    class Meta:
        model = IPAddress
        fields = '__all__'


class PrinterAdminForm(forms.ModelForm):
    turn_to_archive = forms.BooleanField(
        required=False,
        label="Перенести принтер в архив?",
        help_text="Выберите этот параметр, если необходимо перенести принтер в архив."
    )

    class Meta:
        model = Printer
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(PrinterAdminForm, self).__init__(*args, **kwargs)
        self.fields['is_archived'].widget = forms.HiddenInput()
        if self.instance and self.instance.is_archived:
            self.fields['turn_to_archive'].widget = forms.HiddenInput()


class PrintersReportForm(forms.Form):
    AREAS = [
        ('all', 'Все районы'),
    ]

    area = forms.ChoiceField(choices=AREAS, label="Выберите расположение принтеров:")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        subnets = Subnet.objects.all()
        updated_areas = self.AREAS.copy()
        for subnet in subnets:
            subnet_set = (subnet.name, get_area_name(subnet.name))
            updated_areas.append(subnet_set)
        self.fields['area'].choices = updated_areas

    def clean_area(self):
        area = self.cleaned_data.get('area')
        valid_choices = dict(self.fields['area'].choices).keys()
        if area not in valid_choices:
            raise forms.ValidationError('Выберите корректный вариант')
        return area


class StatisticsReportForm(PrintersReportForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            earliest_record = DailyStat.objects.earliest('time_collect')
            latest_record = DailyStat.objects.latest('time_collect')
            self.period_start = earliest_record.time_collect.strftime('%Y-%m-%d')
            self.period_end = latest_record.time_collect.strftime('%Y-%m-%d')
        except Exception as e:
            self.period_start = (timezone.now() - timezone.timedelta(days=3 * 365)).strftime('%Y-%m-%d')
            first_day_current_month = timezone.now().replace(day=1)
            self.period_end = (first_day_current_month - timedelta(days=1)).strftime('%Y-%m-%d')

        self.fields['date_field'].widget.attrs['min'] = self.period_start
        self.fields['date_field'].widget.attrs['max'] = self.period_end
        self.fields['date_field'].initial = self.period_end

    OPTIONS = [
        ('all', 'Все параметры'),
        ('page', 'Всего страниц'),
        ('print', 'Печать'),
        ('copies', 'Копирование'),
        ('scan', 'Сканирование'),
    ]
    option = forms.ChoiceField(
        choices=OPTIONS,
        label="Выберите необходимый параметр:"
    )
    date_field = forms.DateField(
        initial=None,
        label="Введите дату:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'date',
            'min': None,
            'max': None,
        }),
    )


class DateRangeForm(PrintersReportForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            earliest_record = DailyStat.objects.earliest('time_collect')
            latest_record = DailyStat.objects.latest('time_collect')
            self.period_start = earliest_record.time_collect.strftime('%Y-%m-%d')
            self.period_end = latest_record.time_collect.strftime('%Y-%m-%d')
        except Exception as e:
            self.period_start = (timezone.now() - timezone.timedelta(days=3 * 365)).strftime('%Y-%m-%d')
            first_day_current_month = timezone.now().replace(day=1)
            self.period_end = (first_day_current_month - timedelta(days=1)).strftime('%Y-%m-%d')

        self.fields['date_start'].widget.attrs['min'] = self.period_start
        self.fields['date_end'].widget.attrs['min'] = self.period_start
        self.fields['date_start'].widget.attrs['max'] = self.period_end
        self.fields['date_end'].widget.attrs['max'] = self.period_end

    date_start = forms.DateField(
        label="Введите дату начала периода:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'date',
            'min': None,
            'max': None,
            'id': 'date_start_day',
        }),
    )
    date_end = forms.DateField(
        label="Введите дату конца периода:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'date',
            'min': None,
            'max': None,
            'id': 'date_end_day',
        }),
    )


class DayReportForm(DateRangeForm):
    OPTIONS = [
        ('page', 'Всего страниц'),
        ('print', 'Печать'),
        ('copies', 'Копирование'),
        ('scan', 'Сканирование'),
    ]
    option = forms.ChoiceField(
        choices=OPTIONS,
        label="Выберите необходимый параметр:"
    )


class MonthReportForm(DayReportForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            earliest_record = MonthlyStat.objects.earliest('time_collect')
            latest_record = MonthlyStat.objects.latest('time_collect')
            self.period_start = (earliest_record.time_collect + timedelta(hours=7)).strftime('%Y-%m')
            self.period_end = latest_record.time_collect.strftime('%Y-%m')
        except Exception as e:
            self.period_start = (timezone.now() - timezone.timedelta(days=3 * 365)).strftime('%Y-%m')
            first_day_current_month = timezone.now().replace(day=1)
            self.period_end = (first_day_current_month - timedelta(days=1)).strftime('%Y-%m')

        self.fields['date_start'].widget.attrs['min'] = self.period_start
        self.fields['date_end'].widget.attrs['min'] = self.period_start
        self.fields['date_start'].widget.attrs['max'] = self.period_end
        self.fields['date_end'].widget.attrs['max'] = self.period_end

    date_start = forms.DateField(
        label="Введите начало периода:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'month',
            'min': None,
            'max': None,
            'id': 'date_start_month',
        }),
        input_formats=['%Y-%m'],
    )
    date_end = forms.DateField(
        label="Введите конец периода:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'month',
            'min': None,
            'max': None,
            'id': 'date_end_month',
        }),
        input_formats=['%Y-%m'],
    )


class SuppliesReportForm(DateRangeForm):
    date_start = forms.DateField(
        label="Введите дату начала поставок:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'date',
            'min': None,
            'max': None,
            'id': 'supplies_date_start',
        }),
    )
    date_end = forms.DateField(
        label="Введите дату конца поставок:",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'style': 'width: 220px; display: inline-block;',
            'type': 'date',
            'min': None,
            'max': None,
            'id': 'supplies_date_end',
        }),
    )


