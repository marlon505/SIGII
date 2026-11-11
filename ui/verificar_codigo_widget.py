# ui/verificar_codigo_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from services import auth
from resources.helpers import cargar_imagen_fondo


class VerificarCodigoWidget(QWidget):

    ir_a_login = Signal()  # Señal para indicar que se debe volver al login

    def __init__(self):
        super().__init__()
        self.correo = None

        self.setObjectName("fondoLogin_recuperar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._imagen_fondo = cargar_imagen_fondo("recinto_2.jpeg")

        self._construir_ui()

    def set_correo(self, correo: str):
        self.correo = correo
        self.label_correo.setText(f"Código enviado a:\n{correo}")
        self.input_codigo.clear()
        self.input_nueva.clear()
        self.input_confirmar.clear()

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

        # --- Widgets dentro de la tarjeta ---
        self.label_titulo = QLabel("Restablecer contraseña")
        self.label_titulo.setObjectName("loginTitulo")
        self.label_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label_titulo)

        self.label_correo = QLabel()
        self.label_correo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_correo.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px; font-weight: bold;")
        layout.addWidget(self.label_correo)

        self.input_codigo = QLineEdit()
        self.input_codigo.setMaxLength(6)
        self.input_codigo.setPlaceholderText("Código de 6 dígitos")
        layout.addWidget(self.input_codigo)

        self.input_nueva = QLineEdit()
        self.input_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_nueva.setPlaceholderText("Nueva contraseña")
        layout.addWidget(self.input_nueva)

        self.input_confirmar = QLineEdit()
        self.input_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_confirmar.setPlaceholderText("Confirmar contraseña")
        layout.addWidget(self.input_confirmar)

        self.boton_confirmar = QPushButton("Cambiar contraseña")
        self.boton_confirmar.setObjectName("botonPrincipal")
        self.boton_confirmar.clicked.connect(self.on_confirmar_click)
        layout.addWidget(self.boton_confirmar)

        self.boton_regresar = QPushButton("← Regresar a Login")
        self.boton_regresar.clicked.connect(lambda: self.ir_a_login.emit())
        layout.addWidget(self.boton_regresar)

    def on_confirmar_click(self):
        codigo_ingresado = self.input_codigo.text().strip()
        nueva = self.input_nueva.text()
        confirmar = self.input_confirmar.text()

        if not codigo_ingresado or len(codigo_ingresado) != 6:
            QMessageBox.warning(self, "Error", "Ingresa el código de 6 dígitos.")
            return

        if len(nueva) < 8:
            QMessageBox.warning(self, "Error", "La contraseña debe tener al menos 8 caracteres.")
            return

        if nueva != confirmar:
            QMessageBox.warning(self, "Error", "Las contraseñas no coinciden.")
            return

        if not self.correo:
            QMessageBox.critical(self, "Error", "No se especificó un correo.")
            return

        try:
            resultado = auth.obtener_codigo_reset(self.correo)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al consultar el código en la base de datos:\n{e}")
            return

        if resultado is None:
            QMessageBox.critical(self, "Error", "No hay código activo para este correo. Solicita uno nuevo.")
            return

        id_codigo = resultado["id_codigo"]
        codigo_hash = resultado["codigo_hash"]
        expira = resultado["fecha_expiracion"]

        if not auth.codigo_es_valido(codigo_ingresado, codigo_hash, expira):
            QMessageBox.critical(self, "Error", "Código inválido o expirado.")
            return

        try:
            # auth.actualizar_contrasena aplica el hash internamente
            actualizado = auth.actualizar_contrasena(self.correo, nueva)
            auth.invalidar_codigo_reset(id_codigo)
            if not actualizado:
                QMessageBox.information(
                    self, "Aviso",
                    "Código verificado con éxito, pero este correo no pertenece a un usuario activo."
                )
            else:
                QMessageBox.information(self, "Éxito", "Contraseña actualizada correctamente. Inicia sesión.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar la contraseña:\n{e}")
            return

        self.ir_a_login.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self._imagen_fondo.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(0, 0, pixmap)