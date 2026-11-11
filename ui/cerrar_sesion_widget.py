"""Pantalla de carga que se muestra durante 3 segundos al cerrar sesión."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QFrame, QWidget, QProgressBar


class CerrarSesionWidget(QWidget):
    """Widget de pantalla de carga para el cierre de sesión.

    Emite ``sesion_cerrada`` después de 3 segundos para que MainWindow
    navegue de vuelta al Login.
    """

    sesion_cerrada = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(u"fondoCerrarSesion")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()

    def _build_ui(self):
        layout_externo = QVBoxLayout(self)
        layout_externo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame()
        self.card.setObjectName(u"cerrarSesionCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setFixedWidth(380)

        card_layout = QVBoxLayout(self.card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(32, 32, 32, 32)

        self.label_titulo = QLabel("Cerrando sesión...")
        self.label_titulo.setObjectName(u"label_cerrando_sesion")
        self.label_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.label_titulo)

        self.label_subtitulo = QLabel("Guardando cambios y saliendo de forma segura...")
        self.label_subtitulo.setObjectName(u"label_cerrando_subtitulo")
        self.label_subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_subtitulo.setWordWrap(True)
        card_layout.addWidget(self.label_subtitulo)

        self.progress = QProgressBar()
        self.progress.setObjectName(u"progress_cerrando_sesion")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        card_layout.addWidget(self.progress)

        layout_externo.addWidget(self.card)

    def iniciar(self):
        """Arranca el temporizador de 3 segundos y luego emite sesion_cerrada."""
        QTimer.singleShot(3000, self.sesion_cerrada.emit)
