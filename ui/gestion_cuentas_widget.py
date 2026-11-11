# ui/gestion_cuentas_widget.py
# -*- coding: utf-8 -*-
"""Pantalla de gestión de cuentas (Docentes, Técnicos y Administradores).

Responsabilidad:
    - Presentación de cuentas organizadas por rol en un QTabWidget.
    - Filtro por texto y estado.
    - Acciones contextuales: Aprobar, Rechazar, Activar/Desactivar.
    - Confirmación modal previa para acciones destructivas/críticas.
    - Sin consultas SQL: todo el acceso a datos se delega a services/incidencia_service.py.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from resources.colors import Colors
from services import incidencia_service as cuenta_service
from ui.modal_overlay import ModalOverlay


class _TarjetaConfirmacion(QWidget):
    """Tarjeta de confirmación estilizada para usar con ModalOverlay."""

    confirmado = Signal()
    cancelado = Signal()

    def __init__(
        self,
        titulo: str,
        mensaje: str,
        texto_confirmar: str = "Confirmar",
        color_boton: str = Colors.ROJO_ADMIN,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_titulo)

        lbl_mensaje = QLabel(mensaje)
        lbl_mensaje.setWordWrap(True)
        lbl_mensaje.setStyleSheet(f"font-size: 13px; color: {Colors.GRIS}; line-height: 1.4;")
        layout.addWidget(lbl_mensaje)

        layout.addStretch()

        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(10)
        fila_botones.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(
            f"background-color: #E5E7EB; color: #374151; border-radius: 6px; "
            f"padding: 7px 16px; font-weight: 600;"
        )
        btn_cancelar.clicked.connect(self.cancelado.emit)
        fila_botones.addWidget(btn_cancelar)

        btn_confirmar = QPushButton(texto_confirmar)
        btn_confirmar.setStyleSheet(
            f"background-color: {color_boton}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 7px 18px; font-weight: bold;"
        )
        btn_confirmar.clicked.connect(self.confirmado.emit)
        fila_botones.addWidget(btn_confirmar)

        layout.addLayout(fila_botones)




class _FormularioEditarUsuario(QWidget):
    """Formulario modal para editar los datos personales de un usuario (Maestro, Técnico o Administrador)."""

    guardado = Signal(dict)
    cancelado = Signal()

    def __init__(self, datos: dict, parent=None):
        super().__init__(parent)
        self.datos = datos or {}
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        carnet = self.datos.get("carnet", "")
        rol = self.datos.get("rol", "Usuario")
        lbl_titulo = QLabel(f"Editar {rol} ({carnet})")
        lbl_titulo.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_titulo)

        # Campos de solo lectura
        layout.addLayout(self._crear_campo_fijo("Carnet:", carnet))
        layout.addLayout(self._crear_campo_fijo("Rol asignado:", rol))

        # Campos editables
        self.input_nombres = QLineEdit(self.datos.get("nombres", ""))
        self.input_nombres.setMaxLength(60)
        self.input_nombres.setPlaceholderText("Nombres del usuario")
        layout.addLayout(self._crear_campo_editable("Nombres:", self.input_nombres))

        self.input_apellidos = QLineEdit(self.datos.get("apellidos", ""))
        self.input_apellidos.setMaxLength(60)
        self.input_apellidos.setPlaceholderText("Apellidos del usuario")
        layout.addLayout(self._crear_campo_editable("Apellidos:", self.input_apellidos))

        self.input_correo = QLineEdit(self.datos.get("correo", ""))
        self.input_correo.setMaxLength(100)
        self.input_correo.setPlaceholderText("ejemplo@unan.edu.ni")
        layout.addLayout(self._crear_campo_editable("Correo Institucional:", self.input_correo))

        self.input_telefono = QLineEdit(self.datos.get("telefono") or "")
        self.input_telefono.setMaxLength(15)
        self.input_telefono.setPlaceholderText("Teléfono de contacto (opcional)")
        layout.addLayout(self._crear_campo_editable("Teléfono:", self.input_telefono))

        layout.addStretch()

        # Fila de botones
        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(10)
        fila_botones.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(
            "background-color: #E5E7EB; color: #374151; border-radius: 6px; padding: 7px 16px; font-weight: 600;"
        )
        btn_cancelar.clicked.connect(self.cancelado.emit)
        fila_botones.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar Cambios")
        btn_guardar.setStyleSheet(
            f"background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; padding: 7px 18px; font-weight: bold;"
        )
        btn_guardar.clicked.connect(self._on_guardar)
        fila_botones.addWidget(btn_guardar)

        layout.addLayout(fila_botones)

    @staticmethod
    def _estilizar_input(widget: QLineEdit):
        widget.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; font-size: 13px; color: #1F2937; background-color: #FFFFFF; } "
            "QLineEdit:focus { border-color: #DC2626; }"
        )

    def _crear_campo_editable(self, etiqueta: str, input_widget: QLineEdit) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel(etiqueta)
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        self._estilizar_input(input_widget)
        vbox.addWidget(lbl)
        vbox.addWidget(input_widget)
        return vbox

    def _crear_campo_fijo(self, etiqueta: str, valor: str) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel(etiqueta)
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        val_widget = QLineEdit(valor)
        val_widget.setEnabled(False)
        val_widget.setStyleSheet(
            "QLineEdit { background-color: #F3F4F6; color: #6B7280; border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; font-size: 13px; }"
        )
        vbox.addWidget(lbl)
        vbox.addWidget(val_widget)
        return vbox

    def _on_guardar(self):
        nombres = self.input_nombres.text().strip()
        apellidos = self.input_apellidos.text().strip()
        correo = self.input_correo.text().strip()
        telefono = self.input_telefono.text().strip() or None

        if not nombres or not apellidos:
            QMessageBox.warning(self, "Campos Requeridos", "Los nombres y apellidos son obligatorios.")
            return

        if not correo or "@" not in correo or "." not in correo:
            QMessageBox.warning(self, "Correo Inválido", "Por favor ingresa un correo electrónico institucional válido.")
            return

        self.guardado.emit({
            "nombres": nombres,
            "apellidos": apellidos,
            "correo": correo,
            "telefono": telefono,
        })
class _PanelRolWidget(QWidget):
    """Panel contenedor para cada pestaña de rol (Docentes, Técnicos, Administradores)."""

    accion_solicitada = Signal(str, dict)  # tipo_accion, datos_usuario

    COLUMNAS = ["Carnet", "Nombres", "Apellidos", "Correo", "Estado de Cuenta"]

    def __init__(self, rol_nombre: str, parent=None):
        super().__init__(parent)
        self.rol_nombre = rol_nombre
        self._cuentas_todas: List[Dict[str, Any]] = []
        self._cuentas_visibles: List[Dict[str, Any]] = []
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        # ── Barra de filtros ──
        fila_filtros = QHBoxLayout()
        fila_filtros.setSpacing(10)

        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText(f"Buscar en {self.rol_nombre.lower()}s por carnet, nombre o correo...")
        self.input_buscar.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; font-size: 13px; color: #1F2937; background-color: #FFFFFF; }"
            "QLineEdit:focus { border-color: #DC2626; }"
        )
        self.input_buscar.textChanged.connect(self._aplicar_filtros)
        fila_filtros.addWidget(self.input_buscar, 2)

        lbl_filtro = QLabel("Estado:")
        lbl_filtro.setStyleSheet(f"color: {Colors.GRIS}; font-weight: 600; font-size: 13px;")
        fila_filtros.addWidget(lbl_filtro)

        self.combo_estado = QComboBox()
        self.combo_estado.addItems(["Todos", "Pendiente", "Activo", "Inactivo"])
        self.combo_estado.setStyleSheet(
            "QComboBox { border: 1px solid #D1D5DB; border-radius: 6px; padding: 5px 12px; font-size: 13px; color: #1F2937; background-color: #FFFFFF; }"
            "QComboBox:focus { border-color: #DC2626; }"
        )
        self.combo_estado.currentTextChanged.connect(self._aplicar_filtros)
        fila_filtros.addWidget(self.combo_estado, 1)

        self.btn_refrescar = QPushButton("Actualizar")
        self.btn_refrescar.setStyleSheet(
            f"QPushButton {{ background-color: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; "
            f"border-radius: 6px; padding: 6px 14px; font-weight: 600; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #E5E7EB; }}"
        )
        self.btn_refrescar.clicked.connect(self.cargar_datos)
        fila_filtros.addWidget(self.btn_refrescar)

        layout.addLayout(fila_filtros)

        # ── Tabla ──
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(40)
        self.tabla.horizontalHeader().setHighlightSections(False)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda row, col: self._emitir_accion("editar"))
        layout.addWidget(self.tabla)

        # ── Barra de acciones contextuales ──
        barra_acciones = QFrame()
        barra_acciones.setObjectName("barraAccionesCuentas")
        barra_acciones.setStyleSheet(
            "QFrame#barraAccionesCuentas { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 8px 14px; }"
        )
        layout_acciones = QHBoxLayout(barra_acciones)
        layout_acciones.setContentsMargins(8, 6, 8, 6)
        layout_acciones.setSpacing(10)

        self.label_info_seleccion = QLabel("Selecciona un usuario de la tabla para gestionar su cuenta.")
        self.label_info_seleccion.setStyleSheet(f"color: {Colors.GRIS}; font-size: 13px;")
        layout_acciones.addWidget(self.label_info_seleccion)
        layout_acciones.addStretch()

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.AZUL}; color: {Colors.BLANCO}; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #1D4ED8; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_editar.clicked.connect(lambda: self._emitir_accion("editar"))
        layout_acciones.addWidget(self.btn_editar)

        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_eliminar.clicked.connect(lambda: self._emitir_accion("eliminar"))
        layout_acciones.addWidget(self.btn_eliminar)

        self.btn_aprobar = QPushButton("Aprobar")
        self.btn_aprobar.setEnabled(False)
        self.btn_aprobar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ESTADO_CONFIRMADO}; color: {Colors.BLANCO}; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #15803D; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_aprobar.clicked.connect(lambda: self._emitir_accion("aprobar"))
        layout_acciones.addWidget(self.btn_aprobar)

        self.btn_rechazar = QPushButton("Rechazar")
        self.btn_rechazar.setEnabled(False)
        self.btn_rechazar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_rechazar.clicked.connect(lambda: self._emitir_accion("rechazar"))
        layout_acciones.addWidget(self.btn_rechazar)

        self.btn_activar_desactivar = QPushButton("Desactivar")
        self.btn_activar_desactivar.setEnabled(False)
        self.btn_activar_desactivar.setStyleSheet(
            f"QPushButton {{ background-color: #4B5563; color: {Colors.BLANCO}; border-radius: 6px; padding: 6px 14px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #374151; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_activar_desactivar.clicked.connect(lambda: self._emitir_accion("toggle_estado"))
        layout_acciones.addWidget(self.btn_activar_desactivar)

        layout.addWidget(barra_acciones)

    def cargar_datos(self):
        """Consulta el service layer y actualiza la tabla."""
        self._cuentas_todas = cuenta_service.listar_cuentas(self.rol_nombre)
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        texto = self.input_buscar.text().strip().casefold()
        estado_filtro = self.combo_estado.currentText()

        visibles = []
        for c in self._cuentas_todas:
            carnet = str(c.get("carnet", "")).casefold()
            nombres = str(c.get("nombres", "")).casefold()
            apellidos = str(c.get("apellidos", "")).casefold()
            correo = str(c.get("correo", "")).casefold()
            estado = c.get("estado_cuenta", "")

            if texto and not (texto in carnet or texto in nombres or texto in apellidos or texto in correo):
                continue
            if estado_filtro != "Todos" and estado != estado_filtro:
                continue
            visibles.append(c)

        self._poblar_tabla(visibles)

    def _poblar_tabla(self, cuentas: List[Dict[str, Any]]):
        self._cuentas_visibles = cuentas
        self.tabla.setRowCount(0)

        for fila, u in enumerate(cuentas):
            self.tabla.insertRow(fila)

            item_carnet = QTableWidgetItem(str(u.get("carnet", "-")))
            item_carnet.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_carnet.setData(Qt.ItemDataRole.UserRole, u)
            self.tabla.setItem(fila, 0, item_carnet)

            item_nom = QTableWidgetItem(str(u.get("nombres", "-")))
            self.tabla.setItem(fila, 1, item_nom)

            item_ape = QTableWidgetItem(str(u.get("apellidos", "-")))
            self.tabla.setItem(fila, 2, item_ape)

            item_cor = QTableWidgetItem(str(u.get("correo", "-")))
            self.tabla.setItem(fila, 3, item_cor)

            # Badge de estado de cuenta
            estado = str(u.get("estado_cuenta", "Pendiente"))
            self.tabla.setCellWidget(fila, 4, self._crear_badge_estado(estado))

        self._actualizar_estado_acciones(None)

    @staticmethod
    def _crear_badge_estado(estado: str) -> QWidget:
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel(f" {estado} ")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(22)

        if estado == "Activo":
            badge.setStyleSheet(
                f"background-color: #DCFCE7; color: {Colors.ESTADO_CONFIRMADO}; "
                f"font-weight: bold; border-radius: 4px; padding: 2px 8px; font-size: 12px;"
            )
        elif estado == "Pendiente":
            badge.setStyleSheet(
                f"background-color: #DBEAFE; color: {Colors.ESTADO_PENDIENTE}; "
                f"font-weight: bold; border-radius: 4px; padding: 2px 8px; font-size: 12px;"
            )
        else:  # Inactivo
            badge.setStyleSheet(
                f"background-color: #FEE2E2; color: {Colors.ROJO_ADMIN}; "
                f"font-weight: bold; border-radius: 4px; padding: 2px 8px; font-size: 12px;"
            )

        layout.addWidget(badge)
        return contenedor

    def _obtener_seleccion(self) -> Optional[Dict[str, Any]]:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        fila = filas[0].row()
        item = self.tabla.item(fila, 0)
        if item:
            datos = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(datos, dict):
                return datos
        return self._cuentas_visibles[fila] if fila < len(self._cuentas_visibles) else None

    def _on_seleccion_cambiada(self):
        self._actualizar_estado_acciones(self._obtener_seleccion())

    def _actualizar_estado_acciones(self, usuario: Optional[Dict[str, Any]]):
        if not usuario:
            self.label_info_seleccion.setText("Selecciona un usuario de la tabla para gestionar su cuenta.")
            self.btn_editar.setEnabled(False)
            self.btn_eliminar.setEnabled(False)
            self.btn_aprobar.setEnabled(False)
            self.btn_rechazar.setEnabled(False)
            self.btn_activar_desactivar.setEnabled(False)
            self.btn_activar_desactivar.setText("Desactivar")
            return

        carnet = usuario.get("carnet", "-")
        nombre = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip()
        estado = usuario.get("estado_cuenta", "")

        self.label_info_seleccion.setText(f"Seleccionado: <b>{carnet}</b> — {nombre} ({estado})")
        self.btn_editar.setEnabled(True)
        self.btn_eliminar.setEnabled(True)

        if estado == "Pendiente":
            self.btn_aprobar.setEnabled(True)
            self.btn_rechazar.setEnabled(True)
            self.btn_activar_desactivar.setEnabled(False)
            self.btn_activar_desactivar.setText("Desactivar")
        elif estado == "Activo":
            self.btn_aprobar.setEnabled(False)
            self.btn_rechazar.setEnabled(False)
            self.btn_activar_desactivar.setEnabled(True)
            self.btn_activar_desactivar.setText("Desactivar")
        elif estado == "Inactivo":
            self.btn_aprobar.setEnabled(False)
            self.btn_rechazar.setEnabled(False)
            self.btn_activar_desactivar.setEnabled(True)
            self.btn_activar_desactivar.setText("Activar")
        else:
            self.btn_aprobar.setEnabled(False)
            self.btn_rechazar.setEnabled(False)
            self.btn_activar_desactivar.setEnabled(False)

    def _emitir_accion(self, accion: str):
        usuario = self._obtener_seleccion()
        if usuario:
            self.accion_solicitada.emit(accion, usuario)

    def limpiar(self):
        self.input_buscar.clear()
        self.combo_estado.setCurrentIndex(0)
        self.tabla.clearSelection()
        self._cuentas_todas = []
        self._cuentas_visibles = []
        self.tabla.setRowCount(0)
        self._actualizar_estado_acciones(None)


class GestionCuentasWidget(QWidget):
    """Pantalla completa con pestañas para Docentes, Técnicos y Administradores."""

    volver_solicitado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gestionCuentasWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.usuario_correo: Optional[str] = None
        self.usuario_carnet: Optional[str] = None
        self._modal_confirmacion: Optional[ModalOverlay] = None

        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra superior roja del Administrador
        barra_superior = QFrame()
        barra_superior.setObjectName("barraSuperiorAdminModulo")
        barra_superior.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        barra_superior.setStyleSheet(
            f"background-color: {Colors.ROJO_ADMIN}; padding: 10px 16px;"
        )

        layout_barra = QHBoxLayout(barra_superior)
        layout_barra.setContentsMargins(16, 8, 16, 8)
        layout_barra.setSpacing(12)

        titulo = QLabel("Gestión de Usuarios y Aprobación de Cuentas")
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

        layout.addWidget(barra_superior)

        # Contenedor central
        self.contenedor = QWidget()
        layout_contenedor = QVBoxLayout(self.contenedor)
        layout_contenedor.setContentsMargins(20, 16, 20, 16)
        layout_contenedor.setSpacing(10)

        # QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid #E5E7EB; background: #FFFFFF; border-radius: 8px; }} "
            f"QTabBar::tab {{ background: #F3F4F6; color: #4B5563; font-weight: 600; padding: 10px 24px; "
            f"border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }} "
            f"QTabBar::tab:selected {{ background: #FFFFFF; color: {Colors.ROJO_ADMIN}; border-bottom: 2px solid {Colors.ROJO_ADMIN}; }} "
            f"QTabBar::tab:hover:!selected {{ background: #E5E7EB; }}"
        )

        self.panel_docentes = _PanelRolWidget("Docente", self)
        self.panel_tecnicos = _PanelRolWidget("Técnico", self)
        self.panel_administradores = _PanelRolWidget("Administrador", self)

        self.tabs.addTab(self.panel_docentes, "Docentes")
        self.tabs.addTab(self.panel_tecnicos, "Técnicos")
        self.tabs.addTab(self.panel_administradores, "Administradores")

        # Conectar señales de acción de cada panel (una sola vez)
        self.panel_docentes.accion_solicitada.connect(self._ejecutar_accion)
        self.panel_tecnicos.accion_solicitada.connect(self._ejecutar_accion)
        self.panel_administradores.accion_solicitada.connect(self._ejecutar_accion)

        layout_contenedor.addWidget(self.tabs)
        layout.addWidget(self.contenedor)

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()

    def set_usuario(self, correo: str, carnet: Optional[str] = None):
        """Almacena el usuario administrador autenticado para validaciones de seguridad."""
        self.usuario_correo = correo
        self.usuario_carnet = carnet

    def cargar_datos(self):
        """Carga los datos en el panel activo y actualiza todos."""
        self.panel_docentes.cargar_datos()
        self.panel_tecnicos.cargar_datos()
        self.panel_administradores.cargar_datos()

    def _panel_actual(self) -> _PanelRolWidget:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, _PanelRolWidget) else self.panel_docentes

    # ------------------------------------------------------------------
    # Despacho y ejecución de acciones
    # ------------------------------------------------------------------
    def _ejecutar_accion(self, tipo_accion: str, usuario: dict):
        if tipo_accion == "editar":
            self._abrir_modal_editar(usuario)
        elif tipo_accion == "eliminar":
            self._pedir_confirmacion_eliminar(usuario)
        elif tipo_accion == "aprobar":
            self._aprobar(usuario)
        elif tipo_accion == "rechazar":
            self._pedir_confirmacion_rechazar(usuario)
        elif tipo_accion == "toggle_estado":
            estado_actual = usuario.get("estado_cuenta")
            if estado_actual == "Activo":
                self._pedir_confirmacion_desactivar(usuario)
            elif estado_actual == "Inactivo":
                self._cambiar_estado(usuario, "Activo")

    def _abrir_modal_editar(self, usuario: dict):
        form = _FormularioEditarUsuario(usuario, parent=self)
        form.cancelado.connect(self._cerrar_modal)
        form.guardado.connect(lambda datos: self._confirmar_editar_usuario(datos, usuario))
        self._modal_confirmacion = ModalOverlay(form, self, tamano=(500, 500))
        self._modal_confirmacion.mostrar()

    def _confirmar_editar_usuario(self, datos_editados: dict, usuario_original: dict):
        self._cerrar_modal()
        carnet = usuario_original.get("carnet")
        rol = usuario_original.get("rol", self._panel_actual().rol_nombre)
        resultado = cuenta_service.actualizar_usuario(
            carnet=carnet,
            rol_nombre=rol,
            nombres=datos_editados.get("nombres", ""),
            apellidos=datos_editados.get("apellidos", ""),
            correo=datos_editados.get("correo", ""),
            telefono=datos_editados.get("telefono"),
        )
        if resultado.get("exito"):
            QMessageBox.information(self, "Usuario Actualizado", resultado.get("mensaje"))
            self.cargar_datos()
        else:
            QMessageBox.warning(self, "No se pudo actualizar", resultado.get("mensaje"))

    def _pedir_confirmacion_eliminar(self, usuario: dict):
        carnet = usuario.get("carnet", "")
        nombre = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip()
        rol = usuario.get("rol", self._panel_actual().rol_nombre)

        # Validación preventiva si el admin intenta eliminarse a sí mismo
        if rol == "Administrador" and self.usuario_carnet and carnet.upper() == self.usuario_carnet.upper():
            QMessageBox.warning(
                self,
                "Acción no permitida",
                "No puedes eliminar tu propia cuenta de administrador.",
            )
            return

        tarjeta = _TarjetaConfirmacion(
            titulo="Confirmar Eliminación de Cuenta",
            mensaje=f"¿Estás seguro de que deseas eliminar permanentemente la cuenta de "
                    f"<b>{nombre}</b> ({carnet}) con rol <b>{rol}</b>?<br><br>"
                    f"Esta acción borrará definitivamente al usuario del sistema.",
            texto_confirmar="Eliminar Cuenta",
            color_boton=Colors.ROJO_ADMIN,
        )
        tarjeta.cancelado.connect(self._cerrar_modal)
        tarjeta.confirmado.connect(lambda: self._confirmar_eliminar_cuenta(carnet, rol))

        self._modal_confirmacion = ModalOverlay(tarjeta, self, tamano=(480, 230))
        self._modal_confirmacion.mostrar()

    def _confirmar_eliminar_cuenta(self, carnet: str, rol: str):
        self._cerrar_modal()
        resultado = cuenta_service.eliminar_cuenta(
            carnet=carnet,
            rol_nombre=rol,
            carnet_solicitante=self.usuario_carnet,
        )
        if resultado.get("exito"):
            QMessageBox.information(self, "Cuenta Eliminada", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo eliminar", resultado.get("mensaje"))
        self.cargar_datos()

    def _aprobar(self, usuario: dict):
        carnet = usuario.get("carnet")
        rol = usuario.get("rol", self._panel_actual().rol_nombre)
        resultado = cuenta_service.aprobar_cuenta(carnet, rol)

        if resultado.get("exito"):
            QMessageBox.information(self, "Cuenta Aprobada", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo aprobar", resultado.get("mensaje"))
        self.cargar_datos()

    def _pedir_confirmacion_rechazar(self, usuario: dict):
        carnet = usuario.get("carnet", "")
        nombre = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip()
        rol = usuario.get("rol", self._panel_actual().rol_nombre)

        tarjeta = _TarjetaConfirmacion(
            titulo="Confirmar Rechazo de Cuenta",
            mensaje=f"¿Estás seguro de que deseas rechazar y eliminar permanentemente la solicitud de cuenta "
                    f"para <b>{nombre}</b> ({carnet})?<br><br>"
                    f"Esta acción no se puede deshacer.",
            texto_confirmar="Eliminar Solicitud",
            color_boton=Colors.ROJO_ADMIN,
        )
        tarjeta.cancelado.connect(self._cerrar_modal)
        tarjeta.confirmado.connect(lambda: self._confirmar_rechazo(carnet, rol))

        self._modal_confirmacion = ModalOverlay(tarjeta, self, tamano=(460, 220))
        self._modal_confirmacion.mostrar()

    def _confirmar_rechazo(self, carnet: str, rol: str):
        self._cerrar_modal()
        resultado = cuenta_service.rechazar_cuenta(carnet, rol)
        if resultado.get("exito"):
            QMessageBox.information(self, "Cuenta Rechazada", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo rechazar", resultado.get("mensaje"))
        self.cargar_datos()

    def _pedir_confirmacion_desactivar(self, usuario: dict):
        carnet = usuario.get("carnet", "")
        nombre = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip()
        rol = usuario.get("rol", self._panel_actual().rol_nombre)

        # Validación preventiva en UI antes del modal
        if rol == "Administrador" and self.usuario_carnet and carnet.upper() == self.usuario_carnet.upper():
            QMessageBox.warning(
                self,
                "Acción no permitida",
                "No puedes desactivar tu propia cuenta de administrador.",
            )
            return

        tarjeta = _TarjetaConfirmacion(
            titulo="Confirmar Desactivación de Cuenta",
            mensaje=f"¿Deseas cambiar el estado de la cuenta de <b>{nombre}</b> ({carnet}) a <b>Inactivo</b>?<br><br>"
                    f"El usuario no podrá iniciar sesión hasta que sea reactivado por un administrador.",
            texto_confirmar="Desactivar",
            color_boton=Colors.ROJO_ADMIN,
        )
        tarjeta.cancelado.connect(self._cerrar_modal)
        tarjeta.confirmado.connect(lambda: self._confirmar_cambio_estado(carnet, rol, "Inactivo"))

        self._modal_confirmacion = ModalOverlay(tarjeta, self, tamano=(480, 230))
        self._modal_confirmacion.mostrar()

    def _cambiar_estado(self, usuario: dict, nuevo_estado: str):
        carnet = usuario.get("carnet")
        rol = usuario.get("rol", self._panel_actual().rol_nombre)
        self._confirmar_cambio_estado(carnet, rol, nuevo_estado)

    def _confirmar_cambio_estado(self, carnet: str, rol: str, nuevo_estado: str):
        self._cerrar_modal()
        resultado = cuenta_service.cambiar_estado_cuenta(
            carnet=carnet,
            rol_nombre=rol,
            nuevo_estado=nuevo_estado,
            carnet_solicitante=self.usuario_carnet,
        )
        if resultado.get("exito"):
            QMessageBox.information(self, "Estado Actualizado", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "Operación no permitida", resultado.get("mensaje"))
        self.cargar_datos()

    def _cerrar_modal(self):
        if self._modal_confirmacion:
            self._modal_confirmacion.cerrar()
            self._modal_confirmacion = None

    def limpiar(self):
        """Limpia el estado y filtros de todos los paneles al cerrar sesión."""
        self._cerrar_modal()
        self.usuario_correo = None
        self.usuario_carnet = None
        self.panel_docentes.limpiar()
        self.panel_tecnicos.limpiar()
        self.panel_administradores.limpiar()
