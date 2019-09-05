from django.apps import AppConfig


class ReportsModule(AppConfig):
    name = 'corehq.apps.reports'

    def ready(self):
        from corehq.apps.reports import signals  # noqa
