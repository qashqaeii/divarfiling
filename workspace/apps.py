from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workspace"

    def ready(self):
        import workspace.signals_support  # noqa: F401
        import workspace.signals_agency_activity  # noqa: F401
        import workspace.academy.models  # noqa: F401
