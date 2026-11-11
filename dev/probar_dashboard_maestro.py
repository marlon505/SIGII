import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PySide6.QtWidgets import QApplication

from ui.dashboards.dashboard_maestro_widget import DashboardMaestroWidget

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = DashboardMaestroWidget()
    ventana.resize(900, 700)
    ventana.show()
    sys.exit(app.exec())