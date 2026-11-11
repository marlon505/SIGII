# ui/recuperar_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from services import auth
from services.email_service import EmailWorker
from resources.helpers import cargar_imagen_fondo


class RecuperarWidget(QWidget):

    ir_a_login = Signal()
    codigo_enviado = Signal(str)   # emite el correo, para que MainWindow abra VerificarCodigoWidget

    def __init__(self):
        super().__init__()
        self.worker = None  # referencia obligatoria, evita que el QThread se destruya en pleno envío

        self.setObjectName("fondoLogin_recuperar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._imagen_fondo = cargar_imagen_fondo("recinto_2.jpeg")

        self._construir_ui()

    def _construir_ui(self):
        # Layout externo: centra la tarjeta en toda la pantalla
        layout_externo = QVBoxLayout(self)
        layout_externo.addStretch()

        fila_central = QHBoxLayout()
        fila_central.addStretch()

        # La tarjeta
        self.card = QFrame()
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card.setObjectName("loginCard")
        self.card.setFixedWidth(400)
        layout = QVBoxLayout(self.card)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 30, 30, 30)

        fila_central.addWidget(self.card)
        fila_central.addStretch()
        layout_externo.addLayout(fila_central)
        layout_externo.addStretch()

        # --- widgets dentro de `layout` (el de la tarjeta) ---
        self.label_titulo = QLabel("Recuperar contraseña")
        self.label_titulo.setObjectName("loginTitulo")
        self.label_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_titulo)

        self.input_correo = QLineEdit()
        self.input_correo.setPlaceholderText("Correo institucional")
        layout.addWidget(self.input_correo)

        self.boton_enviar = QPushButton("Enviar código de recuperación")
        self.boton_enviar.setObjectName("botonPrincipal")
        self.boton_enviar.clicked.connect(self.on_enviar_click)
        layout.addWidget(self.boton_enviar)

        self.boton_regresar = QPushButton("← Regresar a Login")
        self.boton_regresar.clicked.connect(lambda: self.ir_a_login.emit())
        layout.addWidget(self.boton_regresar)

    def on_enviar_click(self):
        correo = self.input_correo.text().strip()

        if not auth.correo_es_valido(correo):
            QMessageBox.warning(self, "Error", "Ingresa un correo con formato válido.")
            return

        self.boton_enviar.setEnabled(False)
        self.boton_enviar.setText("Enviando...")

        try:
            codigo = auth.guardar_codigo_reset(correo)
        except Exception as e:
            self.boton_enviar.setEnabled(True)
            self.boton_enviar.setText("Enviar código de recuperación")
            QMessageBox.critical(self, "Error al generar código", f"Ocurrió un error con la base de datos:\n{e}")
            return

        self.worker = EmailWorker(correo, codigo)
        self.worker.exito.connect(lambda: self._on_envio_exitoso(correo))
        self.worker.error.connect(self._on_envio_fallido)
        self.worker.start()

    def _on_envio_exitoso(self, correo: str):
        self.boton_enviar.setEnabled(True)
        self.boton_enviar.setText("Enviar código de recuperación")
        QMessageBox.information(
            self, "Código enviado",
            "Si el correo está registrado, recibirás un código en breve."
        )
        self.codigo_enviado.emit(correo)   # ← MainWindow decide qué pantalla mostrar

    def _on_envio_fallido(self, mensaje_error: str):
        self.boton_enviar.setEnabled(True)
        self.boton_enviar.setText("Enviar código de recuperación")
        QMessageBox.critical(self, "Error al enviar correo", mensaje_error)

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self._imagen_fondo.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(0, 0, pixmap)