from django.utils import timezone
from django.db import models


class Subnet(models.Model):
    name = models.CharField(max_length=100, verbose_name='Наименование подсети', help_text='Обязательное поле.')
    address = models.GenericIPAddressField(unique=True, default='0.0.0.0', verbose_name='Адрес',
                                           help_text='Обязательное поле.')
    mask = models.IntegerField(verbose_name='Маска', help_text='Обязательное поле. Необходимо вводить префикс.')

    class Meta:
        db_table = 'subnet'
        verbose_name = 'Подсеть'
        verbose_name_plural = 'Подсети'
        db_table_comment = 'Таблица для хранения информации о подсетях.'

    def __str__(self):
        return self.name


class IPAddress(models.Model):
    address = models.GenericIPAddressField(unique=True, default='0.0.0.0', verbose_name='Адрес',
                                           help_text='Обязательное поле.')
    subnet = models.ForeignKey('Subnet', on_delete=models.CASCADE, verbose_name='Подсеть',
                               help_text='Обязательное поле.')

    class Meta:
        db_table = 'ip_address'
        unique_together = ('address',)
        verbose_name = 'IP-адрес'
        verbose_name_plural = 'IP-адреса'
        db_table_comment = 'Таблица для хранения информации о IP-адресах.'

    def __str__(self):
        return self.address


class Cabinet(models.Model):
    number = models.CharField(max_length=20, blank=False, verbose_name='Номер', help_text='Обязательное поле.')

    class Meta:
        db_table = 'cabinet'
        verbose_name = 'Кабинет'
        verbose_name_plural = 'Кабинеты'
        db_table_comment = 'Таблица для хранения информации о кабинетах.'

    def __str__(self):
        return self.number


class Department(models.Model):
    name = models.CharField(max_length=30, blank=False, verbose_name='Наименование отдела',
                            help_text='Обязательное поле.')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'department'
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        db_table_comment = 'Таблица для хранения информации об отделах.'


class Location(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name='Наименование отдела',
                                   help_text='Обязательное поле.')
    cabinet = models.ForeignKey(Cabinet, on_delete=models.CASCADE, verbose_name='Номер кабинета', null=True,
                                blank=True)

    class Meta:
        db_table = 'location'
        verbose_name = 'Расположение'
        verbose_name_plural = 'Расположение'
        db_table_comment = 'Таблица для хранения информации о расположении.'

    def __str__(self):
        return f'Отдел: {self.department}' if not self.cabinet else f'Кабинет: {self.cabinet}, Отдел: {self.department}'


class PrinterStamp(models.Model):
    name = models.CharField(max_length=30, blank=False, verbose_name='Производитель принтера',
                            help_text='Обязательное поле.')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'printer_stamp'
        verbose_name = 'Производитель принтера'
        verbose_name_plural = 'Производители принтеров'
        db_table_comment = 'Таблица для хранения информации о производителях принтеров.'


class PrinterModel(models.Model):
    stamp = models.ForeignKey('PrinterStamp', on_delete=models.CASCADE, verbose_name='Марка принтера',
                              help_text='Обязательное поле.')
    name = models.CharField(max_length=30, blank=False, verbose_name='Модель принтера', help_text='Обязательное поле.')

    def __str__(self):
        return f"{self.stamp} {self.name}"

    class Meta:
        db_table = 'printer_model'
        verbose_name = 'Модель принтера'
        verbose_name_plural = 'Модели принтеров'
        db_table_comment = 'Таблица для хранения информации о моделях принтеров.'


class SupplyItem(models.Model):
    TYPE_SUPPLY = (
        ('drum_unit', 'фотобарабан'),
        ('cartridge', 'картридж'),
    )
    COLOR_SUPPLY = (
        ('black', 'черный'),
        ('cyan', 'голубой'),
        ('magenta', 'пурпурный'),
        ('yellow', 'желтый')
    )

    name = models.CharField(max_length=40, verbose_name='Наименование расходного материала',
                            help_text='Обязательное поле.')
    type = models.CharField(max_length=20, choices=TYPE_SUPPLY, default='cartridge', verbose_name='Тип',
                            help_text='Обязательное поле.')
    color = models.CharField(max_length=10, choices=COLOR_SUPPLY, default='black', verbose_name='Цвет',
                             help_text='Обязательное поле.')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за единицу, руб.',
                                help_text='Обязательное поле.')

    class Meta:
        db_table = 'supply_item'
        verbose_name = 'Расходный материал'
        verbose_name_plural = 'Расходные материалы'
        db_table_comment = 'Таблица для хранения информации о расходных материалах.'

    def __str__(self):
        return f"{self.get_color_name().capitalize()} {self.get_type_name()} {self.name}"

    def get_type_name(self):
        return dict(self.TYPE_SUPPLY).get(self.type, self.type)

    def get_color_name(self):
        return dict(self.COLOR_SUPPLY).get(self.color, self.color)


class InventoryNumber(models.Model):
    number = models.CharField(max_length=20, unique=True, verbose_name='Инвентарный номер')

    def __str__(self):
        return self.number

    class Meta:
        db_table = 'inventory_number'
        verbose_name = 'Инвентарный номер'
        verbose_name_plural = 'Инвентарные номера'
        db_table_comment = 'Таблица для хранения информации об инвентарных номерах.'


class Printer(models.Model):
    ip_address = models.OneToOneField(IPAddress, null=True, on_delete=models.SET_NULL, verbose_name='IP-адрес',
                                      help_text='Обязательное поле.')
    model = models.ForeignKey(PrinterModel, on_delete=models.CASCADE, verbose_name='Наименование принтера',
                             help_text='Обязательное поле.')
    supplies = models.ManyToManyField('SupplyItem', through='PrinterSupplyStatus', related_name='printer')
    serial_number = models.CharField(max_length=20, blank=False, verbose_name='Серийный номер',
                                     help_text='Обязательное поле.')
    inventory_number = models.ForeignKey(InventoryNumber, null=True, blank=True, on_delete=models.SET_NULL,
                                         verbose_name='Инвентарный номер')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name='Расположение', null=True, blank=True)
    date_of_commission = models.DateField(default=timezone.now, verbose_name='Дата ввода в эксплуатацию',
                                          help_text='Обязательное поле.')
    is_active = models.BooleanField(default=True, blank=False, verbose_name='Активность')
    is_archived = models.BooleanField(default=False, verbose_name='В архиве')
    comment = models.TextField(blank=True, null=True, verbose_name='Комментарий',
                               help_text='Поле для ввода дополнительной информации о принтере.')

    class Meta:
        db_table = 'printer'
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'
        db_table_comment = 'Таблица для хранения информации о принтерах.'

    def __str__(self):
        return f"{self.model} {self.ip_address}"

    def get_is_active(self):
        return 'Включен' if self.is_active else 'Выключен'

    def get_is_archived(self):
        return 'Архивирован' if self.is_archived else 'Активен'

    def get_subnet_name(self):
        from monitoring.views import get_area_name

        subnet = self.ip_address.subnet.name if self.ip_address and self.ip_address.subnet else None
        if subnet:
            return get_area_name(subnet)

    def archive(self):
        self.is_archived = True
        self.is_active = False
        if self.ip_address:
            ip_address_to_delete = self.ip_address
            self.ip_address = None
            self.save()
            ip_address_to_delete.delete()
        else:
            self.save()

    def restore(self):
        if self.is_archived:
            self.is_archived = False
            self.save()

    get_subnet_name.short_description = 'Имя подсети'


class PrinterSupplyStatus(models.Model):
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, verbose_name='Принтер',
                                help_text='Обязательное поле.')
    supply = models.ForeignKey(SupplyItem, on_delete=models.CASCADE, verbose_name='Расходный материал',
                               help_text='Обязательное поле.')
    remaining_supply_percentage = models.IntegerField(blank=True, null=True, help_text='Обязательное поле.',
                                                      verbose_name='Остаток расходного материала, %')
    consumption = models.IntegerField(blank=True, null=True, help_text='Обязательное поле.',
                                      verbose_name='Cредний расход материала, кол-во страниц')

    class Meta:
        db_table = 'printer_supply_status'
        verbose_name = 'Статус расходного материала для принтера'
        verbose_name_plural = 'Статус расходного материала для принтера'
        db_table_comment = 'Таблица для хранения информации о статусе расходных материалов для принтеров'

    def __str__(self):
        return f"{self.printer} {self.supply} - {self.remaining_supply_percentage}%"


class SupplyDetails(models.Model):
    supply = models.ForeignKey(SupplyItem, on_delete=models.CASCADE, help_text='Обязательное поле.',
                               verbose_name='Расходный материал')
    qty = models.IntegerField(verbose_name='Количество', help_text='Обязательное поле.')

    class Meta:
        db_table = 'supply_details'
        verbose_name = 'Остаток расходного материала на складе'
        verbose_name_plural = 'Остатки расходных материалов на складе'
        db_table_comment = 'Таблица для хранения информации об остатках расходных материалов на складе'

    def __str__(self):
        return f'{self.supply} {self.qty}'


class BaseStat(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE)
    page = models.IntegerField(blank=False)
    print = models.IntegerField(blank=False)
    copies = models.IntegerField(blank=True, null=True)
    scan = models.IntegerField(blank=True, null=True)
    time_collect = models.DateTimeField(blank=False, default=timezone.now)

    class Meta:
        abstract = True


class Statistics(BaseStat):
    class Meta:
        db_table = 'statistics'
        verbose_name = 'Статистика'
        verbose_name_plural = 'Статистика'
        db_table_comment = 'Таблица для хранения информации о статистике использования принтеров.'


class DailyStat(BaseStat):
    class Meta:
        db_table = 'daily_statistics'
        verbose_name = 'Ежедневная статистика'
        verbose_name_plural = 'Ежедневная статистика'
        db_table_comment = 'Таблица для хранения информации о ежедневной статистике использования принтеров.'

    def formatted_time_collect(self):
        return self.time_collect.strftime('%d-%m-%Y')


class MonthlyStat(BaseStat):
    class Meta:
        db_table = 'monthly_statistics'
        verbose_name = 'Ежемесячная статистика'
        verbose_name_plural = 'Ежемесячная статистика'
        db_table_comment = 'Таблица для хранения информации о ежемесячной статистике использования принтеров.'

    def formatted_time_collect(self):
        return self.time_collect.strftime('%m-%Y')


class ChangeSupply(models.Model):
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, verbose_name='Принтер',
                                help_text='Обязательное поле.')
    supply = models.ForeignKey(SupplyItem, on_delete=models.CASCADE, verbose_name='Расходный материал',
                               help_text='Обязательное поле.')
    time_change = models.DateTimeField(blank=False, default=timezone.now)

    class Meta:
        db_table = 'change_supply'
        verbose_name = 'Замена расходных материалов'
        verbose_name_plural = 'Замена расходных материалов'
        db_table_comment = 'Таблица для хранения информации о событиях замены расходных материалов.'

    def __str__(self):
        return f"Замена {self.supply} в {self.printer}"

    def formatted_time_change(self):
        return self.time_change.strftime('%d-%m-%Y')


class ForecastStat(models.Model):
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, verbose_name='Принтер',
                                help_text='Обязательное поле.')
    copies_printing = models.IntegerField()
    time_collect = models.DateField(default=timezone.now)

    class Meta:
        db_table = 'forecast_statistics'
        db_table_comment = 'Таблица для хранения информации о статистике для подготовки прогноза.'


class Forecast(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE)
    qty_pages = models.IntegerField()
    daily_pages = models.IntegerField()
    forecast_date = models.DateField()

    class Meta:
        db_table = 'forecast'
        db_table_comment = 'Таблица для хранения информации о прогнозе печати.'


class ForecastChangeSupplies(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE)
    supply = models.ForeignKey('SupplyItem', on_delete=models.CASCADE)
    forecast_date = models.DateField()

    class Meta:
        db_table = 'forecast_change_supplies'
        db_table_comment = 'Таблица для хранения информации о прогнозе замены расходных материалов.'


class MaintenanceCosts(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE)
    paper_cost = models.FloatField()
    supplies_cost = models.FloatField()

    class Meta:
        db_table = 'maintenance_costs'
        db_table_comment = 'Таблица для хранения информации о прогнозе затрат.'


class PrinterError(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE)
    event_date = models.DateTimeField(default=timezone.now)
    description = models.TextField()

    class Meta:
        db_table = 'printer_error'
        verbose_name = 'Ошибка принтера'
        verbose_name_plural = 'Ошибки принтеров'
        db_table_comment = 'Таблица для хранения информации о cобытиях ошибка принтера.'

    def __str__(self):
        return f"{self.printer} - {self.description}"

