from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "JamiiLite 5G"

    def ready(self):
        from .supabase import lock_down_public_tables

        post_migrate.connect(lock_down_public_tables, dispatch_uid="core.lock_down_public_tables")
