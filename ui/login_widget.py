# ui/login_widget.py
import json
from PySide6.QtWidgets import (
    QLineEdit, QWidget, QVBoxLayout, QPushButton, QLabel,
    QHBoxLayout, QFrame, QCheckBox, QMenu, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QSettings, QEvent
from PySide6.QtGui import QPainter
from mysql.connector import Error as MySQLError
from services import auth
from resources.helpers import cargar_imagen_fondo


class LoginWidget(QWidget):

    login_exitoso = Signal(str, dict)      # emite el rol y dict con datos: {"correo": ..., "carnet": ..., "rol": ...}
    ir_a_registrarse = Signal()
    ir_a_recuperar = Signal()

    def __init__(self):
        super().__init__()

        self.settings = QSettings("SIGII", "SistemaIncidencias")
        self._cuentas_guardadas = {}

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

        # --- Widgets dentro de la tarjeta ---
        self.titulo = QLabel("Inicia sesión en SIGII")
        self.titulo.setObjectName("loginTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.titulo)

        self.subtitulo = QLabel("Sistema de Gestión e Información de Incidencias")
        self.subtitulo.setObjectName("loginSubtitulo")
        self.subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitulo.setWordWrap(True)
        layout.addWidget(self.subtitulo)

        self.correo_input = QLineEdit()
        self.correo_input.setPlaceholderText("Correo")
        layout.addWidget(self.correo_input)

        self.contrasena_input = QLineEdit()
        self.contrasena_input.setPlaceholderText("Contraseña")
        self.contrasena_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.contrasena_input)

        fila_opciones = QHBoxLayout()
        self.recordarme = QCheckBox("Recordarme")
        self.olvide_contrasena_label = QLabel("<a href='#' style='color:#FFFFFF;'><b>¿Olvidaste tu contraseña?</b></a>")
        self.olvide_contrasena_label.setObjectName("linkLabel")
        fila_opciones.addWidget(self.recordarme)
        fila_opciones.addStretch()
        fila_opciones.addWidget(self.olvide_contrasena_label)
        layout.addLayout(fila_opciones)

        self.boton_iniciar_sesion = QPushButton("Iniciar sesión")
        self.boton_iniciar_sesion.setObjectName("botonPrincipal")
        layout.addWidget(self.boton_iniciar_sesion)

        self.registro_label = QLabel(
            "¿No tienes cuenta? <a href='#' style='color:#FFFFFF;'><b><u>Regístrate</u></b></a>"
        )
        self.registro_label.setObjectName("linkLabel")
        self.registro_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.registro_label)

        self._cargar_credenciales_guardadas()
        self.correo_input.installEventFilter(self)

        self.boton_iniciar_sesion.clicked.connect(self._on_click_login)
        self.registro_label.linkActivated.connect(lambda: self.ir_a_registrarse.emit())
        self.olvide_contrasena_label.linkActivated.connect(lambda: self.ir_a_recuperar.emit())

    def _cargar_credenciales_guardadas(self):
        """Carga las cuentas recordadas desde QSettings."""
        raw_cuentas = self.settings.value("cuentas_guardadas", "{}")
        try:
            if isinstance(raw_cuentas, str):
                self._cuentas_guardadas = json.loads(raw_cuentas)
            elif isinstance(raw_cuentas, dict):
                self._cuentas_guardadas = raw_cuentas
            else:
                self._cuentas_guardadas = {}
        except Exception:
            self._cuentas_guardadas = {}

        # Si el usuario tenía activado "Recordarme", rellenar el último correo y contraseña
        recordarme_activo = self.settings.value("recordarme", False, type=bool)
        self.recordarme.setChecked(recordarme_activo)

        if recordarme_activo:
            ultimo_correo = self.settings.value("ultimo_correo", "")
            if ultimo_correo and ultimo_correo in self._cuentas_guardadas:
                self.correo_input.setText(ultimo_correo)
                self.contrasena_input.setText(self._cuentas_guardadas[ultimo_correo])

    def eventFilter(self, watched, event):
        """Muestra una sola nube al enfocar el campo de correo."""
        if (
            watched is self.correo_input
            and event.type() == QEvent.Type.FocusIn
            and self._cuentas_guardadas
        ):
            self._mostrar_credenciales_guardadas()
        return super().eventFilter(watched, event)

    def _mostrar_credenciales_guardadas(self):
        """Abre, encima del correo, las credenciales recordadas."""
        if hasattr(self, "menu_credenciales") and self.menu_credenciales.isVisible():
            return

        self.menu_credenciales = QMenu(self)
        # El menú no toma el foco: así, al cerrarlo no vuelve a dispararse el
        # evento del campo y se evita el parpadeo.
        self.menu_credenciales.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_credenciales.setStyleSheet("""
            QMenu {
                background: white;
                color: #1F2937;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 9px 16px;
                border-radius: 5px;
            }
            QMenu::item:selected { background: #E5E7EB; }
        """)

        for correo in self._cuentas_guardadas:
            # Se usan puntos fijos: no se revela ni la contraseña ni su longitud.
            accion = self.menu_credenciales.addAction(
                f"{correo}    Contraseña: ••••••••"
            )
            accion.triggered.connect(
                lambda checked=False, cuenta=correo: self._usar_credenciales_guardadas(cuenta)
            )

        self.menu_credenciales.adjustSize()
        posicion = self.correo_input.mapToGlobal(self.correo_input.rect().topLeft())
        posicion.setY(posicion.y() - self.menu_credenciales.sizeHint().height() - 6)
        self.menu_credenciales.popup(posicion)

    def _usar_credenciales_guardadas(self, correo: str):
        """Completa ambos campos al escoger una credencial de la nube."""
        self.correo_input.setText(correo)
        self.contrasena_input.setText(self._cuentas_guardadas[correo])

    def _validar_campos(self) -> bool:
        if not self.correo_input.text() or not self.contrasena_input.text():
            self.correo_input.setProperty("error", True)
            self.correo_input.style().unpolish(self.correo_input)
            self.correo_input.style().polish(self.correo_input)
            self.contrasena_input.setProperty("error", True)
            self.contrasena_input.style().unpolish(self.contrasena_input)
            self.contrasena_input.style().polish(self.contrasena_input)
            QMessageBox.warning(self, "Datos incompletos", "Escribe tu correo y contraseña para iniciar sesión.")
            return False
        for campo in (self.correo_input, self.contrasena_input):
            campo.setProperty("error", False)
            campo.style().unpolish(campo)
            campo.style().polish(campo)
        return True

    def _on_click_login(self):
        if not self._validar_campos():
            return

        correo = self.correo_input.text().strip()
        contrasena = self.contrasena_input.text()
        try:
            resultado = auth.login(correo, contrasena)
        except MySQLError:
            QMessageBox.critical(
                self,
                "Error de conexión con la base de datos",
                "No se pudo validar la cuenta. Comprueba la conexión a la base de datos e inténtalo de nuevo.",
            )
            return

        if resultado["status"] == "ok":
            # Guardar credenciales si "Recordarme" está marcado
            if self.recordarme.isChecked():
                self._cuentas_guardadas[correo] = contrasena
                self.settings.setValue("cuentas_guardadas", json.dumps(self._cuentas_guardadas))
                self.settings.setValue("ultimo_correo", correo)
                self.settings.setValue("recordarme", True)
            else:
                self.settings.setValue("recordarme", False)
                self.settings.setValue("ultimo_correo", "")

            datos_usuario = {
                "correo": correo,
                "carnet": resultado.get("carnet"),
                "rol": resultado.get("rol"),
                "nombres": resultado.get("nombres"),
                "apellidos": resultado.get("apellidos"),
                "nombre_completo": resultado.get("nombre_completo")
            }
            self.login_exitoso.emit(resultado["rol"], datos_usuario)
        elif resultado["status"] == "pendiente":
            QMessageBox.information(self, "Cuenta pendiente", resultado.get("mensaje", "Tu cuenta está pendiente de aprobación."))
        elif resultado["status"] == "inactivo":
            QMessageBox.warning(self, "Cuenta inactiva", resultado.get("mensaje", "Esta cuenta está inactiva."))
        else:
            QMessageBox.warning(self, "No se pudo iniciar sesión", resultado.get("mensaje", "Correo o contraseña incorrectos."))

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self._imagen_fondo.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(0, 0, pixmap)
