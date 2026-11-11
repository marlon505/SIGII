# ui/registrarse_widget.py
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter

from services import auth
from resources.helpers import cargar_imagen_fondo


class RegistrarseWidget(QWidget):
    ir_a_login = Signal()

    def __init__(self):
        super().__init__()

        self.setObjectName("fondoLogin")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._imagen_fondo = cargar_imagen_fondo("recinto.jpeg")

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

        # --- Título y campos dentro de la tarjeta ---
        self.titulo = QLabel("Registrarse")
        self.titulo.setObjectName("loginTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.titulo)

        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Nombre completo (Ej: Juan Pérez)")
        layout.addWidget(self.nombre_input)

        self.correo_input = QLineEdit()
        self.correo_input.setPlaceholderText("Correo institucional")
        layout.addWidget(self.correo_input)

        self.contrasena_input = QLineEdit()
        self.contrasena_input.setPlaceholderText("Contraseña")
        self.contrasena_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.contrasena_input)

        self.confirmar_contrasena_input = QLineEdit()
        self.confirmar_contrasena_input.setPlaceholderText("Confirmar Contraseña")
        self.confirmar_contrasena_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.confirmar_contrasena_input)

        self.rol_combo = QComboBox()
        self.rol_combo.addItems(["Maestro", "Técnico", "Administrador"])
        layout.addWidget(self.rol_combo)

        self.boton_registrarse = QPushButton("Registrarse")
        self.boton_registrarse.setObjectName("botonPrincipal")
        layout.addWidget(self.boton_registrarse)

        self.btn_volver_login = QPushButton("Volver a Login")
        self.btn_volver_login.clicked.connect(self.ir_a_login.emit)
        layout.addWidget(self.btn_volver_login)

        self.boton_registrarse.clicked.connect(self._on_click_registrarse)

    def _validar_campos(self) -> bool:
        campos = [
            self.nombre_input,
            self.correo_input,
            self.contrasena_input,
            self.confirmar_contrasena_input,
        ]
        valido = True
        for campo in campos:
            if not campo.text().strip():
                campo.setProperty("error", True)
                campo.style().unpolish(campo)
                campo.style().polish(campo)
                valido = False
            else:
                campo.setProperty("error", False)
                campo.style().unpolish(campo)
                campo.style().polish(campo)
        return valido

    def _on_click_registrarse(self):
        if not self._validar_campos():
            QMessageBox.warning(self, "Campos requeridos", "Por favor completa todos los campos del formulario.")
            return

        if self.contrasena_input.text() != self.confirmar_contrasena_input.text():
            self.contrasena_input.setProperty("error", True)
            self.contrasena_input.style().unpolish(self.contrasena_input)
            self.contrasena_input.style().polish(self.contrasena_input)
            self.confirmar_contrasena_input.setProperty("error", True)
            self.confirmar_contrasena_input.style().unpolish(self.confirmar_contrasena_input)
            self.confirmar_contrasena_input.style().polish(self.confirmar_contrasena_input)
            QMessageBox.warning(self, "Contraseñas diferentes", "Las contraseñas no coinciden.")
            return

        nombre_completo = self.nombre_input.text().strip()
        partes = nombre_completo.split()
        if len(partes) >= 2:
            nombres = " ".join(partes[:-1])
            apellidos = partes[-1]
        elif len(partes) == 1:
            nombres = partes[0]
            apellidos = ""
        else:
            nombres = "Usuario"
            apellidos = "SIGII"

        rol_seleccionado = self.rol_combo.currentText()
        resultado = auth.registrarse(
            correo=self.correo_input.text().strip(),
            contrasena=self.contrasena_input.text(),
            rol=rol_seleccionado,
            nombres=nombres,
            apellidos=apellidos,
        )

        if resultado.get("exito"):
            mensaje_estado = (
                " La cuenta de administrador requiere aprobación antes de iniciar sesión."
                if resultado.get("estado_cuenta") == "Pendiente"
                else " Ya puedes iniciar sesión."
            )
            QMessageBox.information(self, "Éxito", f"{resultado.get('mensaje', 'Cuenta creada.')}{mensaje_estado}")
            self.nombre_input.clear()
            self.correo_input.clear()
            self.contrasena_input.clear()
            self.confirmar_contrasena_input.clear()
            self.ir_a_login.emit()
        else:
            QMessageBox.critical(self, "Error al registrarse", resultado.get("mensaje", "No se pudo crear la cuenta."))

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self._imagen_fondo.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, pixmap)
