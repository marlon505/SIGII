# dashboard_tecnico.py

from ui.dashboards.dashboard_base import DashboardBase
from PySide6.QtWidgets import QLabel

class DashboardTecnico(DashboardBase):
    def __init__(self):
        super().__init__()
        self.layout_principal.addWidget(QLabel("Cola de asignaciones"))