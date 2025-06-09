from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'
    verbose_name = 'Мониторинг'

    def ready(self):
        import monitoring.signals
        from automation.data_extractor import update_printer_supply_status
