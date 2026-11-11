# dashboard_maestro.py

from ui.dashboards.dashboard_base import DashboardBase
from PySide6.QtWidgets import QLabel

class DashboardMaestro(DashboardBase):
    def __init__(self):
        super().__init__()
        self.layout_principal.addWidget(QLabel("Mis reportes"))