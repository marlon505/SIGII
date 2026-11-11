from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

class DashboardBase(QWidget):
    cerrar_sesion = Signal()
    def __init__(self):
        super().__init__()
        self.layout_principal = QVBoxLayout(self)
        self._construir_secciones_comunes()

    def _construir_secciones_comunes(self):
        self.layout_principal.addWidget(QLabel("Laboratorios"))
        self.layout_principal.addWidget(QLabel("Computadoras"))
        self.layout_principal.addWidget(QLabel("Últimos reportes"))
        self.layout_principal.addWidget(QLabel("Últimas incidencias"))