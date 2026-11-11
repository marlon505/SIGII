"""
ui/widgets/modal_overlay.py

Objetivo:
    Simular un modal de estilo "web": oscurece el fondo del widget padre
    pero lo mantiene visible detrás, y centra una "tarjeta" de contenido
    encima. Vive dentro de la misma ventana (a diferencia de QDialog, que
    abre una ventana aparte del sistema operativo).

Responsabilidad:
    Únicamente presentacional. No conoce el contenido que va a envolver
    (formulario de incidencia, confirmación, etc.) — solo sabe mostrar
    cualquier QWidget como tarjeta flotante centrada.

Dependencias:
    PySide6.QtWidgets, PySide6.QtCore

Relación con otros módulos:
    Lo usará dashboard_maestro.py para mostrar RegistrarIncidenciaForm,
    y en el futuro cualquier otro dashboard que necesite un modal.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame
from PySide6.QtCore import Qt


class ModalOverlay(QWidget):
    """
    Capa semitransparente que cubre por completo al widget padre y
    centra un widget de contenido ("tarjeta") encima.
    """

    def __init__(self, contenido: QWidget, parent: QWidget, tamano: tuple[int, int] | None = None):
        super().__init__(parent)
        self._tamano_preferido = tamano or (520, 520)

        self.setObjectName("modalOverlay")

        # WA_StyledBackground es necesario para que un QWidget "normal"
        # respete background-color de QSS (mismo principio que ya usan
        # en styles/helpers.py para los QFrame de estado).
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            #modalOverlay {
                background-color: rgba(0, 0, 0, 120);
            }
            #modalCard {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        tarjeta = QFrame(self)
        tarjeta.setObjectName("modalCard")
        tarjeta.setAttribute(Qt.WA_StyledBackground, True)
        tarjeta.setFixedSize(*self._tamano_preferido)
        self.tarjeta = tarjeta

        layout_tarjeta = QVBoxLayout(tarjeta)
        layout_tarjeta.setContentsMargins(24, 24, 24, 24)
        layout_tarjeta.addWidget(contenido)

        layout_overlay = QVBoxLayout(self)
        layout_overlay.setAlignment(Qt.AlignCenter)
        layout_overlay.addWidget(tarjeta)

    def mostrar(self):
        """Ajusta el tamaño al padre, se coloca al frente y se muestra."""
        if self.parent():
            self.setGeometry(self.parent().rect())
            ancho = max(320, min(self._tamano_preferido[0], self.width() - 40))
            alto = max(320, min(self._tamano_preferido[1], self.height() - 40))
            self.tarjeta.setFixedSize(ancho, alto)
        self.raise_()
        self.show()

    def cerrar(self):
        self.hide()
        self.deleteLater()
