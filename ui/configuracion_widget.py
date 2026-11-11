# ui/configuracion_widget.py
# -*- coding: utf-8 -*-
"""Pantalla de configuración para el Administrador (Cuenta y Modo de Visión).

Responsabilidad:
    - Mostrar los datos de perfil propios del administrador autenticado.
    - Permitir el cambio seguro de contraseña con validación de contraseña actual y mínimo 8 caracteres.
    - Selector para alternar al modo de visión (Maestro o Técnico) en solo observación.
    - Cero consultas SQL directas: delega al service layer.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from resources.colors import Colors
from services import incidencia_service as cuenta_service


class ConfiguracionWidget(QWidget):
    """Pantalla de ajustes del Administrador."""

    volver_solicitado = Signal()
    cambiar_modo_vista = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("configuracionWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.usuario_correo: Optional[str] = None
        self.usuario_carnet: Optional[str] = None

        self._construir_ui()

    def _construir_ui(self):
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # ── Barra superior corporativa (Rojo Administrador) ──
        barra_superior = QFrame()
        barra_superior.setObjectName("barraSuperiorAdminModulo")
        barra_superior.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        barra_superior.setStyleSheet(
            f"background-color: {Colors.ROJO_ADMIN}; padding: 10px 16px;"
        )

        layout_barra = QHBoxLayout(barra_superior)
        layout_barra.setContentsMargins(16, 8, 16, 8)
        layout_barra.setSpacing(12)

        titulo = QLabel("Configuración del Administrador")
        titulo.setStyleSheet(
            f"color: {Colors.BLANCO}; font-size: 18px; font-weight: bold;"
        )
        layout_barra.addWidget(titulo)
        layout_barra.addStretch()

        self.boton_volver = QPushButton("← Regresar")
        self.boton_volver.setStyleSheet(
            f"background-color: {Colors.BLANCO}; color: {Colors.ROJO_ADMIN}; "
            f"border: 1px solid {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 6px 14px; font-weight: bold;"
        )
        self.boton_volver.clicked.connect(self.volver_solicitado.emit)
        layout_barra.addWidget(self.boton_volver)

        layout_raiz.addWidget(barra_superior)

        # ── Área con Scroll ──
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        contenido = QWidget()
        contenido.setObjectName("contenidoConfiguracion")
        layout_contenido = QVBoxLayout(contenido)
        layout_contenido.setContentsMargins(32, 24, 32, 24)
        layout_contenido.setSpacing(20)

        # 1. Bloque: Información de la Cuenta
        layout_contenido.addWidget(self._crear_bloque_perfil())

        # 2. Bloque: Cambio de Contraseña
        layout_contenido.addWidget(self._crear_bloque_contrasena())

        # 3. Bloque: Modo de Visión
        layout_contenido.addWidget(self._crear_bloque_modo_vision())

        layout_contenido.addStretch()
        scroll.setWidget(contenido)
        layout_raiz.addWidget(scroll)

    def _crear_bloque_perfil(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        lbl_seccion = QLabel("Datos de la Cuenta")
        lbl_seccion.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_seccion)

        # Fila de datos
        fila_datos = QHBoxLayout()
        fila_datos.setSpacing(24)

        self.lbl_carnet = self._crear_campo_perfil(fila_datos, "Carnet:", "-")
        self.lbl_nombre = self._crear_campo_perfil(fila_datos, "Nombre:", "-")
        self.lbl_correo = self._crear_campo_perfil(fila_datos, "Correo institucional:", "-")
        self.lbl_rol = self._crear_campo_perfil(fila_datos, "Rol asignado:", "Administrador")

        fila_datos.addStretch()
        layout.addLayout(fila_datos)
        return frame

    @staticmethod
    def _crear_campo_perfil(layout_padre: QHBoxLayout, etiqueta: str, valor_inicial: str) -> QLabel:
        vbox = QVBoxLayout()
        vbox.setSpacing(3)
        lbl_eti = QLabel(etiqueta)
        lbl_eti.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        lbl_val = QLabel(valor_inicial)
        lbl_val.setStyleSheet("color: #1F2937; font-size: 14px; font-weight: bold;")
        vbox.addWidget(lbl_eti)
        vbox.addWidget(lbl_val)
        layout_padre.addLayout(vbox)
        return lbl_val

    def _crear_bloque_contrasena(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        lbl_seccion = QLabel("Cambio de Contraseña")
        lbl_seccion.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_seccion)

        lbl_desc = QLabel(
            "Para mayor seguridad, la nueva contraseña debe contener al menos 8 caracteres."
        )
        lbl_desc.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Campos
        fila_campos = QHBoxLayout()
        fila_campos.setSpacing(16)

        self.input_actual = QLineEdit()
        self.input_actual.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_actual.setPlaceholderText("Contraseña actual...")
        self._estilizar_input(self.input_actual)
        fila_campos.addLayout(self._envolver_input("Contraseña actual:", self.input_actual))

        self.input_nueva = QLineEdit()
        self.input_nueva.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_nueva.setPlaceholderText("Mínimo 8 caracteres...")
        self._estilizar_input(self.input_nueva)
        fila_campos.addLayout(self._envolver_input("Nueva contraseña:", self.input_nueva))

        self.input_confirmar = QLineEdit()
        self.input_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_confirmar.setPlaceholderText("Repetir nueva contraseña...")
        self._estilizar_input(self.input_confirmar)
        fila_campos.addLayout(self._envolver_input("Confirmar contraseña:", self.input_confirmar))

        layout.addLayout(fila_campos)

        # Botón Guardar
        fila_btn = QHBoxLayout()
        fila_btn.addStretch()

        btn_cambiar = QPushButton("Actualizar Contraseña")
        btn_cambiar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; "
            f"border-radius: 6px; padding: 8px 18px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }}"
        )
        btn_cambiar.clicked.connect(self._on_cambiar_contrasena)
        fila_btn.addWidget(btn_cambiar)

        layout.addLayout(fila_btn)
        return frame

    def _crear_bloque_modo_vision(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        lbl_seccion = QLabel("Modo de Visión (Solo Observación)")
        lbl_seccion.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_seccion)

        lbl_desc = QLabel(
            "Permite explorar y auditar el sistema visualizando el panel como Maestro o Técnico. "
            "Todas las acciones operativas de escritura (tomar tareas, modificar incidencias o registrar reportes) "
            "están bloqueadas en este modo para proteger la integridad de los datos."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {Colors.GRIS}; font-size: 13px; line-height: 1.4;")
        layout.addWidget(lbl_desc)

        fila_controles = QHBoxLayout()
        fila_controles.setSpacing(12)

        self.combo_vista = QComboBox()
        self.combo_vista.setObjectName("comboModoVision")
        self.combo_vista.addItems(["Seleccionar rol de visión...", "Maestro", "Técnico"])
        self.combo_vista.setStyleSheet(
            "QComboBox { border: 1px solid #D1D5DB; border-radius: 6px; padding: 7px 14px; "
            "font-size: 13px; color: #1F2937; background-color: #FFFFFF; min-width: 220px; } "
            "QComboBox:focus { border-color: #DC2626; }"
        )
        fila_controles.addWidget(self.combo_vista)

        btn_activar_vista = QPushButton("Cambiar Vista")
        btn_activar_vista.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.AZUL}; color: {Colors.BLANCO}; "
            f"border-radius: 6px; padding: 8px 18px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #1D4ED8; }}"
        )
        btn_activar_vista.clicked.connect(self._on_activar_vista)
        fila_controles.addWidget(btn_activar_vista)
        fila_controles.addStretch()

        layout.addLayout(fila_controles)
        return frame

    @staticmethod
    def _estilizar_input(input_widget: QLineEdit):
        input_widget.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 7px 12px; "
            "font-size: 13px; color: #1F2937; background-color: #FFFFFF; } "
            "QLineEdit:focus { border-color: #DC2626; }"
        )

    @staticmethod
    def _envolver_input(etiqueta: str, widget: QWidget) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel(etiqueta)
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        vbox.addWidget(lbl)
        vbox.addWidget(widget)
        return vbox

    # ------------------------------------------------------------------
    # Carga y Acciones
    # ------------------------------------------------------------------
    def set_usuario(self, correo: str, carnet: Optional[str] = None):
        """Asigna el usuario administrador activo y consulta sus datos."""
        self.usuario_correo = correo
        self.usuario_carnet = carnet
        self.cargar_datos()

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()

    def cargar_datos(self):
        """Consulta el perfil del administrador autenticado."""
        identificador = self.usuario_carnet or self.usuario_correo
        if not identificador:
            return
        perfil = cuenta_service.obtener_perfil_administrador(identificador)
        if perfil:
            carnet = perfil.get("carnet", "-")
            nombre_completo = f"{perfil.get('nombres', '')} {perfil.get('apellidos', '')}".strip()
            correo = perfil.get("correo", "-")

            self.lbl_carnet.setText(carnet)
            self.lbl_nombre.setText(nombre_completo)
            self.lbl_correo.setText(correo)
            self.usuario_carnet = carnet
            self.usuario_correo = correo

    def _on_cambiar_contrasena(self):
        actual = self.input_actual.text().strip()
        nueva = self.input_nueva.text().strip()
        confirmar = self.input_confirmar.text().strip()

        if not actual or not nueva or not confirmar:
            QMessageBox.warning(self, "Campos Requeridos", "Por favor completa todos los campos de contraseña.")
            return

        if len(nueva) < 8:
            QMessageBox.warning(self, "Contraseña Débil", "La nueva contraseña debe tener al menos 8 caracteres.")
            return

        if nueva != confirmar:
            QMessageBox.warning(self, "No Coinciden", "La nueva contraseña y su confirmación no coinciden.")
            return

        identificador = self.usuario_carnet or self.usuario_correo
        if not identificador:
            QMessageBox.critical(self, "Error de Sesión", "No se encontró el identificador del administrador.")
            return

        resultado = cuenta_service.cambiar_contrasena_administrador(
            carnet_o_correo=identificador,
            contrasena_actual=actual,
            contrasena_nueva=nueva,
        )

        if resultado.get("exito"):
            self.input_actual.clear()
            self.input_nueva.clear()
            self.input_confirmar.clear()
            QMessageBox.information(self, "Éxito", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "Error al Cambiar Contraseña", resultado.get("mensaje"))

    def _on_activar_vista(self):
        rol_seleccionado = self.combo_vista.currentText()
        if rol_seleccionado in ("Maestro", "Técnico"):
            self.cambiar_modo_vista.emit(rol_seleccionado)
            self.combo_vista.setCurrentIndex(0)
        else:
            QMessageBox.information(
                self,
                "Seleccionar Rol",
                "Por favor selecciona el rol al que deseas cambiar en Modo de Visión.",
            )

    def limpiar(self):
        """Limpia los campos y resetea el usuario al cerrar sesión."""
        self.input_actual.clear()
        self.input_nueva.clear()
        self.input_confirmar.clear()
        self.combo_vista.setCurrentIndex(0)
        self.lbl_carnet.setText("-")
        self.lbl_nombre.setText("-")
        self.lbl_correo.setText("-")
        self.usuario_correo = None
        self.usuario_carnet = None
