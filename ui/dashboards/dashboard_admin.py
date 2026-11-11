# dashboard_admin.py

from ui.dashboards.dashboard_base import DashboardBase
from PySide6.QtWidgets import QLabel

class DashboardAdmin(DashboardBase):
    def __init__(self):
        super().__init__()
        self.layout_principal.addWidget(QLabel("Incidencias resueltas este mes"))
        self.layout_principal.addWidget(QLabel("Tipos de problemas reportados"))
        self.layout_principal.addWidget(QLabel("Porcentaje de problemas este mes"))
        self.layout_principal.addWidget(QLabel("Dificultades encontradas"))