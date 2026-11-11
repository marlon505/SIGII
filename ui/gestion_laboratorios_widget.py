# ui/gestion_laboratorios_widget.py
# -*- coding: utf-8 -*-
"""Pantalla de gestión de laboratorios y aviso de equipos para el Administrador.

Responsabilidad:
    - CRUD completo de laboratorios: id_laboratorio, nombre, ubicacion.
    - Captura amigable de errores:
        * Error 1062 (ID duplicado): mensaje comprensible.
        * Error 1451 (FK RESTRICT): "Este laboratorio tiene reportes asociados y no puede eliminarse".
    - Aviso visual breve: "Gestión de equipos: próxima fase" sin lógica adicional.
    - Emisión de laboratorios_modificados para actualizar catálogos en el sistema.
    - Monoventana: modales con ModalOverlay.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from resources.colors import Colors
from services import incidencia_service as laboratorio_service
from ui.modal_overlay import ModalOverlay


class _TarjetaConfirmacion(QWidget):
    """Tarjeta de confirmación estilizada para modal."""

    confirmado = Signal()
    cancelado = Signal()

    def __init__(self, titulo: str, mensaje: str, parent=None):
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
            "background-color: #E5E7EB; color: #374151; border-radius: 6px; "
            "padding: 7px 16px; font-weight: 600;"
        )
        btn_cancelar.clicked.connect(self.cancelado.emit)
        fila_botones.addWidget(btn_cancelar)

        btn_confirmar = QPushButton("Eliminar")
        btn_confirmar.setStyleSheet(
            f"background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; "
            "padding: 7px 18px; font-weight: bold;"
        )
        btn_confirmar.clicked.connect(self.confirmado.emit)
        fila_botones.addWidget(btn_confirmar)

        layout.addLayout(fila_botones)


class _FormularioLaboratorio(QWidget):
    """Formulario modal para crear o editar un laboratorio."""

    guardado = Signal(dict)
    cancelado = Signal()

    def __init__(self, modo: str = "crear", datos: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.modo = modo
        self.datos = datos or {}
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        titulo_texto = "Nuevo Laboratorio" if self.modo == "crear" else f"Editar Laboratorio ({self.datos.get('id_laboratorio', '')})"
        lbl_titulo = QLabel(titulo_texto)
        lbl_titulo.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {Colors.ROJO_ADMIN};"
        )
        layout.addWidget(lbl_titulo)

        # Campos
        layout.addLayout(self._crear_campo_id())
        layout.addLayout(self._crear_campo_nombre())
        layout.addLayout(self._crear_campo_ubicacion())

        layout.addStretch()

        # Botones
        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(10)
        fila_botones.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(
            "background-color: #E5E7EB; color: #374151; border-radius: 6px; padding: 7px 16px; font-weight: 600;"
        )
        btn_cancelar.clicked.connect(self.cancelado.emit)
        fila_botones.addWidget(btn_cancelar)

        btn_guardar = QPushButton("Guardar")
        btn_guardar.setStyleSheet(
            f"background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; padding: 7px 18px; font-weight: bold;"
        )
        btn_guardar.clicked.connect(self._on_guardar)
        fila_botones.addWidget(btn_guardar)

        layout.addLayout(fila_botones)

    def _crear_campo_id(self) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel("ID del Laboratorio (ej. LAB-11):")
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        self.input_id = QLineEdit()
        self.input_id.setMaxLength(10)
        self.input_id.setPlaceholderText("LAB-XX")
        self.input_id.setText(self.datos.get("id_laboratorio", ""))
        self._estilizar_input(self.input_id)
        if self.modo == "editar":
            self.input_id.setEnabled(False)
            self.input_id.setStyleSheet("QLineEdit { background-color: #F3F4F6; color: #6B7280; border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; }")
        vbox.addWidget(lbl)
        vbox.addWidget(self.input_id)
        return vbox

    def _crear_campo_nombre(self) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel("Nombre del Laboratorio:")
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        self.input_nombre = QLineEdit()
        self.input_nombre.setMaxLength(60)
        self.input_nombre.setPlaceholderText("Ej. Laboratorio FC 11")
        self.input_nombre.setText(self.datos.get("nombre", ""))
        self._estilizar_input(self.input_nombre)
        vbox.addWidget(lbl)
        vbox.addWidget(self.input_nombre)
        return vbox

    def _crear_campo_ubicacion(self) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel("Ubicación:")
        lbl.setStyleSheet(f"color: {Colors.GRIS}; font-size: 12px; font-weight: 600;")
        self.input_ubicacion = QLineEdit()
        self.input_ubicacion.setMaxLength(100)
        self.input_ubicacion.setPlaceholderText("Ej. Edificio FC - Rc. Tomas Borges 6")
        self.input_ubicacion.setText(self.datos.get("ubicacion") or "")
        self._estilizar_input(self.input_ubicacion)
        vbox.addWidget(lbl)
        vbox.addWidget(self.input_ubicacion)
        return vbox

    @staticmethod
    def _estilizar_input(widget: QLineEdit):
        widget.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; font-size: 13px; color: #1F2937; background-color: #FFFFFF; } "
            "QLineEdit:focus { border-color: #DC2626; }"
        )

    def _on_guardar(self):
        id_lab = self.input_id.text().strip().upper()
        nombre = self.input_nombre.text().strip()
        ubicacion = self.input_ubicacion.text().strip() or None

        if not id_lab or not nombre:
            QMessageBox.warning(self, "Campos Requeridos", "El ID y el nombre del laboratorio son obligatorios.")
            return

        self.guardado.emit({
            "id_laboratorio": id_lab,
            "nombre": nombre,
            "ubicacion": ubicacion,
        })


class GestionLaboratoriosWidget(QWidget):
    """Pantalla para el CRUD de laboratorios y aviso de equipos."""

    volver_solicitado = Signal()
    laboratorios_modificados = Signal()

    COLUMNAS = ["ID Laboratorio", "Nombre del Laboratorio", "Ubicación"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gestionLaboratoriosWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._laboratorios_todos: List[Dict[str, Any]] = []
        self._laboratorios_visibles: List[Dict[str, Any]] = []
        self._modal_overlay: Optional[ModalOverlay] = None

        self._construir_ui()
        self._conectar_senales()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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

        titulo = QLabel("Gestión de Laboratorios y Equipos")
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

        # ── Contenedor principal ──
        contenedor_cuerpo = QWidget()
        layout_cuerpo = QVBoxLayout(contenedor_cuerpo)
        layout_cuerpo.setContentsMargins(24, 20, 24, 20)
        layout_cuerpo.setSpacing(16)

        # 1. Sección CRUD de Laboratorios
        layout_cuerpo.addLayout(self._crear_barra_herramientas())

        # 2. Tabla
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

        layout_cuerpo.addWidget(self.tabla)

        # 3. Barra de acciones inferior
        layout_cuerpo.addWidget(self._crear_barra_acciones())

        layout.addWidget(contenedor_cuerpo)

    def _crear_barra_herramientas(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(10)

        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Buscar laboratorio por ID, nombre o ubicación...")
        self.input_buscar.setStyleSheet(
            "QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding: 7px 14px; font-size: 13px; color: #1F2937; background-color: #FFFFFF; } "
            "QLineEdit:focus { border-color: #DC2626; }"
        )
        self.input_buscar.textChanged.connect(self._aplicar_filtro)
        fila.addWidget(self.input_buscar, 2)

        self.btn_refrescar = QPushButton("Actualizar")
        self.btn_refrescar.setStyleSheet(
            "QPushButton { background-color: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; "
            "border-radius: 6px; padding: 7px 14px; font-weight: 600; font-size: 13px; } "
            "QPushButton:hover { background-color: #E5E7EB; }"
        )
        self.btn_refrescar.clicked.connect(self.cargar_datos)
        fila.addWidget(self.btn_refrescar)

        self.btn_nuevo = QPushButton("+ Agregar Laboratorio")
        self.btn_nuevo.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 7px 18px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }}"
        )
        self.btn_nuevo.clicked.connect(self._abrir_modal_crear)
        fila.addWidget(self.btn_nuevo)

        return fila

    def _crear_barra_acciones(self) -> QFrame:
        barra = QFrame()
        barra.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 8px 14px; }"
        )
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self.label_info = QLabel("Selecciona un laboratorio de la tabla para gestionarlo.")
        self.label_info.setStyleSheet(f"color: {Colors.GRIS}; font-size: 13px;")
        layout.addWidget(self.label_info)
        layout.addStretch()

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.AZUL}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 6px 16px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: #1D4ED8; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_editar.clicked.connect(self._abrir_modal_editar)
        layout.addWidget(self.btn_editar)

        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 6px 16px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_eliminar.clicked.connect(self._pedir_confirmacion_eliminar)
        layout.addWidget(self.btn_eliminar)

        return barra

    def _conectar_senales(self):
        self.input_buscar.textChanged.connect(self._aplicar_filtro)
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda row, col: self._abrir_modal_editar())

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()

    def cargar_datos(self):
        """Consulta la lista de laboratorios y aplica el filtro."""
        self._laboratorios_todos = laboratorio_service.listar_laboratorios()
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        texto = self.input_buscar.text().strip().casefold()
        visibles = []
        for lab in self._laboratorios_todos:
            id_lab = str(lab.get("id_laboratorio", "")).casefold()
            nombre = str(lab.get("nombre", "")).casefold()
            ubicacion = str(lab.get("ubicacion", "") or "").casefold()

            if texto and not (texto in id_lab or texto in nombre or texto in ubicacion):
                continue
            visibles.append(lab)

        self._poblar_tabla(visibles)

    def _poblar_tabla(self, laboratorios: List[Dict[str, Any]]):
        self._laboratorios_visibles = laboratorios
        self.tabla.setRowCount(0)

        for fila, lab in enumerate(laboratorios):
            self.tabla.insertRow(fila)

            # 0: ID
            item_id = QTableWidgetItem(str(lab.get("id_laboratorio", "-")))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_id.setData(Qt.ItemDataRole.UserRole, lab)
            self.tabla.setItem(fila, 0, item_id)

            # 1: Nombre
            item_nom = QTableWidgetItem(str(lab.get("nombre", "-")))
            self.tabla.setItem(fila, 1, item_nom)

            # 2: Ubicación
            item_ubi = QTableWidgetItem(str(lab.get("ubicacion") or "Sin ubicación"))
            self.tabla.setItem(fila, 2, item_ubi)

        self._actualizar_botones()

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
        return self._laboratorios_visibles[fila] if fila < len(self._laboratorios_visibles) else None

    def _on_seleccion_cambiada(self):
        self._actualizar_botones()

    def _actualizar_botones(self):
        lab = self._obtener_seleccion()
        tiene = lab is not None
        self.btn_editar.setEnabled(tiene)
        self.btn_eliminar.setEnabled(tiene)

        if lab:
            id_lab = lab.get("id_laboratorio")
            nombre = lab.get("nombre")
            self.label_info.setText(f"Seleccionado: <b>{id_lab}</b> — {nombre}")
        else:
            self.label_info.setText("Selecciona un laboratorio de la tabla para gestionarlo.")

    # ------------------------------------------------------------------
    # CRUD: Modales y Ejecución
    # ------------------------------------------------------------------
    def _abrir_modal_crear(self):
        form = _FormularioLaboratorio(modo="crear")
        form.cancelado.connect(self._cerrar_modal)
        form.guardado.connect(self._ejecutar_crear)

        self._modal_overlay = ModalOverlay(form, self, tamano=(460, 310))
        self._modal_overlay.mostrar()

    def _ejecutar_crear(self, datos: dict):
        resultado = laboratorio_service.crear_laboratorio(
            id_laboratorio=datos["id_laboratorio"],
            nombre=datos["nombre"],
            ubicacion=datos["ubicacion"],
        )
        if resultado.get("exito"):
            self._cerrar_modal()
            self.cargar_datos()
            self.laboratorios_modificados.emit()
            QMessageBox.information(self, "Laboratorio Creado", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo registrar", resultado.get("mensaje"))

    def _abrir_modal_editar(self):
        lab = self._obtener_seleccion()
        if not lab:
            return

        form = _FormularioLaboratorio(modo="editar", datos=lab)
        form.cancelado.connect(self._cerrar_modal)
        form.guardado.connect(self._ejecutar_editar)

        self._modal_overlay = ModalOverlay(form, self, tamano=(460, 310))
        self._modal_overlay.mostrar()

    def _ejecutar_editar(self, datos: dict):
        resultado = laboratorio_service.actualizar_laboratorio(
            id_laboratorio=datos["id_laboratorio"],
            nombre=datos["nombre"],
            ubicacion=datos["ubicacion"],
        )
        if resultado.get("exito"):
            self._cerrar_modal()
            self.cargar_datos()
            self.laboratorios_modificados.emit()
            QMessageBox.information(self, "Laboratorio Actualizado", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo actualizar", resultado.get("mensaje"))

    def _pedir_confirmacion_eliminar(self):
        lab = self._obtener_seleccion()
        if not lab:
            return

        id_lab = lab.get("id_laboratorio", "")
        nombre = lab.get("nombre", "")

        tarjeta = _TarjetaConfirmacion(
            titulo="Confirmar Eliminación",
            mensaje=f"¿Estás seguro de que deseas eliminar permanentemente el laboratorio <b>{nombre}</b> ({id_lab})?",
        )
        tarjeta.cancelado.connect(self._cerrar_modal)
        tarjeta.confirmado.connect(lambda: self._ejecutar_eliminar(id_lab))

        self._modal_overlay = ModalOverlay(tarjeta, self, tamano=(460, 220))
        self._modal_overlay.mostrar()

    def _ejecutar_eliminar(self, id_laboratorio: str):
        self._cerrar_modal()
        resultado = laboratorio_service.eliminar_laboratorio(id_laboratorio)
        if resultado.get("exito"):
            self.cargar_datos()
            self.laboratorios_modificados.emit()
            QMessageBox.information(self, "Laboratorio Eliminado", resultado.get("mensaje"))
        else:
            QMessageBox.warning(self, "No se pudo eliminar", resultado.get("mensaje"))

    def _cerrar_modal(self):
        if self._modal_overlay:
            self._modal_overlay.cerrar()
            self._modal_overlay = None

    def limpiar(self):
        """Limpia el estado de la pantalla al cerrar sesión."""
        self._cerrar_modal()
        self.input_buscar.clear()
        self.tabla.clearSelection()
        self._laboratorios_todos = []
        self._laboratorios_visibles = []
        self.tabla.setRowCount(0)
        self._actualizar_botones()
