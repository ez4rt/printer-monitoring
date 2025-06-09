from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist

from monitoring import models
from monitoring.forms import SubnetAdminForm, IPAddressAdminForm, PrinterAdminForm
from django.contrib import messages
from automation.data_extractor import scan_subnet, add_printer_parsing_snmp


admin.site.register(models.PrinterStamp)
admin.site.register(models.Cabinet)
admin.site.register(models.Department)
admin.site.register(models.InventoryNumber)


@admin.register(models.Subnet)
class SubnetAdmin(admin.ModelAdmin):
    form = SubnetAdminForm
    list_display = ('name', 'address')
    search_fields = ('name', 'address')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get('scan_subnet'):
            subnet_ip_address = form.cleaned_data['address']
            subnet_mask = form.cleaned_data['mask']
            ip_addresses = scan_subnet(f"{subnet_ip_address}/{subnet_mask}")
            for ip_address in ip_addresses:
                ip_address, created = models.IPAddress.objects.get_or_create(
                    address=ip_address,
                    defaults={
                        'address': ip_address,
                        'subnet': obj,
                    }
                )
                if created:
                    add_printer(ip_address)
                else:
                    printer = models.Printer.objects.filter(ip_address=ip_address)
                    if not printer:
                        add_printer(ip_address)


def add_printer(ip_address):
    printer_info = add_printer_parsing_snmp(str(ip_address))
    return create_printer(printer_info, ip_address)


def create_printer(printer_info, ip_address):
    printer_stamp = get_or_create_printer_stamp(printer_info[0])
    printer_model = get_or_create_printer_model(printer_stamp, printer_info[1])
    return get_or_create_printer(printer_model, printer_info[2], ip_address)


def get_or_create_printer(model, serial_number, ip_address):
    printer, created = models.Printer.objects.get_or_create(
        serial_number=serial_number,
        model=model,
        defaults={
            'ip_address': ip_address,
            'model': model,
            'serial_number': serial_number,
        }
    )
    return printer


def get_or_create_printer_stamp(stamp):
    printer_stamp, created = models.PrinterStamp.objects.get_or_create(
        name=stamp,
        defaults={
            'name': stamp,
        }
    )
    return printer_stamp


def get_or_create_printer_model(stamp, model):
    printer_model, created = models.PrinterModel.objects.get_or_create(
        name=model,
        defaults={
            'stamp': stamp,
            'name': model,
        }
    )
    return printer_model


def check_or_add_printer(printer_info, obj):
    try:
        check_printer(printer_info, obj)
    except ObjectDoesNotExist:
        create_printer(printer_info, obj)


def check_printer(printer_info, obj):
    existing_printer = models.Printer.objects.get(serial_number=printer_info[2])
    existing_printer.ip_address = obj
    existing_printer.is_archived = False
    existing_printer.is_active = True
    existing_printer.save()


@admin.register(models.IPAddress)
class IPAddressAdmin(admin.ModelAdmin):
    form = IPAddressAdminForm
    list_display = ('address', 'subnet',)
    search_fields = ('address', 'subnet__name',)
    list_filter = ('subnet__name',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get('add_printer'):
            printer_info = add_printer_parsing_snmp(str(obj))
            check_or_add_printer(printer_info, obj)


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('department', 'cabinet')
    search_fields = ('department__name', 'cabinet__number')


@admin.register(models.PrinterModel)
class StatisticsAdmin(admin.ModelAdmin):
    list_display = ('stamp', 'name')
    list_filter = ('stamp__name',)


@admin.register(models.SupplyDetails)
class SupplyDetailsAdmin(admin.ModelAdmin):
    list_display = ('supply', 'qty')


class PrinterSupplyStatusInline(admin.TabularInline):
    model = models.PrinterSupplyStatus
    extra = 1


@admin.register(models.Printer)
class PrinterAdmin(admin.ModelAdmin):
    inlines = [PrinterSupplyStatusInline]
    form = PrinterAdminForm
    list_display = ('model', 'serial_number', 'get_subnet_name', 'ip_address', 'location', 'is_active', 'is_archived')
    list_filter = ('model__stamp__name', 'model__name', 'ip_address__subnet__name', 'is_active',
                   'location__department__name')
    search_fields = ('model__stamp__name', 'model__name', 'serial_number', 'ip_address__address',
                     'location__cabinet__number')

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except ValueError as e:
            messages.error(request, str(e))
        if obj.pk and obj.is_archived:
            obj.restore()
        if 'turn_to_archive' in form.cleaned_data and form.cleaned_data['turn_to_archive']:
            obj.archive()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.is_archived:
            form.base_fields['ip_address'].help_text = ("Этот принтер в архиве. Изменение IP-адреса восстановит его.")
        return form


@admin.register(models.SupplyItem)
class SupplyTypeAdmin(admin.ModelAdmin):
    pass


