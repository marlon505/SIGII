# ui/lista_incidencias_admin_widget.py
# -*- coding: utf-8 -*-
"""Pantalla de lista general y gestión de incidencias para el rol Administrador.

Responsabilidad:
    - Mostrar todas las incidencias del sistema en cualquier estado.
    - Reutilizar BuscadorReportesWidget para búsquedas y filtros.
    - Mostrar columna 'Técnico asignado'.
    - Indicador visual rojo cuando hayan transcurrido más de 5 días desde fecha_confirmado.
    - Botón 'Editar' junto a 'Exportar PDF' para modificar cualquier detalle o estado de la incidencia.
    - Abrir DetalleIncidenciaWidget con historial completo e interactivo.
    - Exportación de reportes a PDF (seleccionado y tabla completa).
"""

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QMarginsF, Qt, Signal
from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from resources.colors import Colors
from resources.helpers import aplicar_estado_visual
from services import incidencia_service
from services.report_export_service import (
    exportar_incidencias_excel,
)
from ui.detalle_incidencia_widget import DetalleIncidenciaWidget
from ui.modal_overlay import ModalOverlay
from ui.report_export_api_worker import ReportExportAPIWorker
from ui.widgets.buscador_reportes import BuscadorReportesWidget
from ui.widgets.dialogo_reasignar_widget import DialogoReasignarWidget


class ListaIncidenciasAdminWidget(QWidget):
    """Pantalla de supervisión y gestión de incidencias del Administrador."""

    volver_solicitado = Signal()
    incidencia_actualizada = Signal(int)

    COLUMNAS = [
        "ID",
        "Laboratorio",
        "Equipo",
        "Tipo de problema",
        "Prioridad",
        "Estado",
        "Técnico asignado",
        "Fecha",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("listaIncidenciasAdminWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._incidencias_todas: List[Dict[str, Any]] = []
        self._incidencias_visibles: List[Dict[str, Any]] = []
        self._modal_detalle: Optional[ModalOverlay] = None
        self._export_api_worker: Optional[ReportExportAPIWorker] = None

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

        titulo = QLabel("Supervisión y Gestión General de Incidencias")
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

        # ── Contenedor central ──
        contenedor_cuerpo = QWidget()
        layout_cuerpo = QVBoxLayout(contenedor_cuerpo)
        layout_cuerpo.setContentsMargins(20, 16, 20, 16)
        layout_cuerpo.setSpacing(12)

        # ── Buscador y filtros reutilizados ──
        self.buscador = BuscadorReportesWidget(self)
        self.buscador.set_titulo("Buscar y filtrar incidencias de todo el recinto")
        self.buscador.label_titulo.setStyleSheet(
            f"color: {Colors.ROJO_ADMIN}; font-size: 16px; font-weight: bold;"
        )

        # El administrador tiene habilitados 'Editar', 'Eliminar' y 'Exportar PDF'
        self.buscador.boton_editar.show()
        self.buscador.boton_eliminar.setText("Eliminar")
        self.buscador.boton_eliminar.show()
        self.buscador.boton_accion_estado.hide()
        self.buscador.boton_reasignar.show()
        self.buscador.boton_exportar_pdf.show()
        self.buscador.mostrar_opciones_exportacion_administrador()

        estilo_btn_admin = (
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 6px 16px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; border: 1px solid #CBD5E1; }}"
        )
        self.buscador.boton_editar.setStyleSheet(estilo_btn_admin)
        self.buscador.boton_eliminar.setStyleSheet(estilo_btn_admin)
        self.buscador.boton_reasignar.setStyleSheet(estilo_btn_admin)
        self.buscador.boton_exportar_pdf.setStyleSheet(estilo_btn_admin)

        layout_cuerpo.addWidget(self.buscador)

        # ── Tabla de incidencias ──
        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(42)
        self.tabla.horizontalHeader().setHighlightSections(False)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        layout_cuerpo.addWidget(self.tabla)

        # ── Barra informativa inferior ──
        barra_pie = QFrame()
        barra_pie.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 6px 14px; }"
        )
        layout_pie = QHBoxLayout(barra_pie)
        layout_pie.setContentsMargins(8, 4, 8, 4)
        layout_pie.setSpacing(10)

        self.label_info = QLabel("Haz doble clic en una fila o selecciónala para editar o ver su historial.")
        self.label_info.setStyleSheet(f"color: {Colors.GRIS}; font-size: 13px;")
        layout_pie.addWidget(self.label_info)
        layout_pie.addStretch()

        self.btn_ver_detalle = QPushButton("Ver Historial y Detalle")
        self.btn_ver_detalle.setEnabled(False)
        self.btn_ver_detalle.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; border-radius: 6px; "
            f"padding: 6px 16px; font-weight: bold; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {Colors.ROJO_ADMIN_OSCURO}; }} "
            f"QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}"
        )
        self.btn_ver_detalle.clicked.connect(self._abrir_detalle_seleccionado)
        layout_pie.addWidget(self.btn_ver_detalle)

        layout_cuerpo.addWidget(barra_pie)
        layout.addWidget(contenedor_cuerpo)

        self._cargar_catalogo_laboratorios()

    def _conectar_senales(self):
        self.buscador.filtros_cambiados.connect(self._filtrar_incidencias)
        self.buscador.accion_editar.connect(self._abrir_edicion_seleccionada)
        self.buscador.accion_reasignar.connect(self._abrir_dialogo_reasignar)
        self.buscador.accion_eliminar.connect(self._eliminar_seleccionadas)
        self.buscador.accion_exportar_pdf.connect(self._exportar_seleccionado_pdf)
        self.buscador.accion_exportar_todo_pdf.connect(self._exportar_todo_pdf)
        self.buscador.accion_exportar_todo_excel.connect(self._exportar_todo_excel)
        self.buscador.accion_exportar_todo_pdf_api.connect(
            lambda: self._exportar_todo_api("pdf")
        )
        self.buscador.accion_exportar_todo_excel_api.connect(
            lambda: self._exportar_todo_api("excel_pdf")
        )
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda row, col: self._abrir_edicion_seleccionada())

    def _cargar_catalogo_laboratorios(self):
        try:
            labs = incidencia_service.obtener_laboratorios()
            self.buscador.cargar_laboratorios([
                (lab["id_laboratorio"], lab["nombre"]) for lab in labs
            ])
        except Exception as err:
            print(f"[ListaAdmin] Error al cargar laboratorios: {err}")

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()

    def cargar_datos(self):
        """Consulta todas las incidencias con su historial completo."""
        seleccion_previa = self._obtener_seleccion()
        id_previo = seleccion_previa.get("id_reporte") if seleccion_previa else None

        try:
            self._incidencias_todas = incidencia_service.obtener_todas_las_incidencias_admin()
        except Exception as err:
            print(f"[ListaAdmin] Error al cargar incidencias: {err}")
            self._incidencias_todas = []

        self._filtrar_incidencias(self.buscador.filtros_actuales())

        if id_previo is not None:
            for row in range(self.tabla.rowCount()):
                item = self.tabla.item(row, 0)
                if item:
                    datos = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(datos, dict) and datos.get("id_reporte") == id_previo:
                        self.tabla.selectRow(row)
                        break

    def _filtrar_incidencias(self, filtros: dict):
        texto = filtros.get("texto", "").casefold()
        lab_filtro = filtros.get("laboratorio")
        estado_filtro = filtros.get("estado")
        f_desde = filtros.get("fecha_desde")
        f_hasta = filtros.get("fecha_hasta")

        estados_equivalentes = {
            "Pendiente": {"Pendiente"},
            "Confirmado": {"Confirmado"},
            "En reparación": {"En reparación", "En reparacion", "En proceso"},
            "Resuelto": {"Resuelto"},
            "Reabierto": {"Reabierto"},
        }

        visibles = []
        for inc in self._incidencias_todas:
            # Filtro texto
            texto_inc = " ".join(str(inc.get(campo, "")) for campo in (
                "id_reporte", "laboratorio", "equipo", "tipo_problema",
                "descripcion", "tecnico_nombre", "profesor_nombre"
            )).casefold()
            if texto and texto not in texto_inc:
                continue

            # Filtro laboratorio
            if lab_filtro and inc.get("id_laboratorio") != lab_filtro:
                continue

            # Filtro estado
            if estado_filtro and inc.get("estado") not in estados_equivalentes.get(estado_filtro, {estado_filtro}):
                continue

            # Filtro fechas
            f_reporte = self._fecha_de_reporte(inc.get("fecha_dt") or inc.get("fecha"))
            if f_desde and (f_reporte is None or f_reporte < f_desde):
                continue
            if f_hasta and (f_reporte is None or f_reporte > f_hasta):
                continue

            visibles.append(inc)

        self._poblar_tabla(visibles)

    @staticmethod
    def _fecha_de_reporte(valor) -> Optional[date]:
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        try:
            return date.fromisoformat(str(valor)[:10])
        except (TypeError, ValueError):
            return None

    def _poblar_tabla(self, incidencias: List[Dict[str, Any]]):
        self._incidencias_visibles = incidencias
        self.tabla.setRowCount(0)

        for fila, inc in enumerate(incidencias):
            self.tabla.insertRow(fila)

            # 0: ID
            item_id = QTableWidgetItem(f"#{inc.get('id_reporte', '-')}")
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_id.setData(Qt.ItemDataRole.UserRole, inc)
            self.tabla.setItem(fila, 0, item_id)

            # 1: Laboratorio
            item_lab = QTableWidgetItem(str(inc.get("laboratorio", "-")))
            self.tabla.setItem(fila, 1, item_lab)

            # 2: Equipo
            item_eq = QTableWidgetItem(str(inc.get("equipo", "-")))
            item_eq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila, 2, item_eq)

            # 3: Tipo de problema
            item_tipo = QTableWidgetItem(str(inc.get("tipo_problema", "-")))
            self.tabla.setItem(fila, 3, item_tipo)

            # 4: Prioridad
            item_prio = QTableWidgetItem(str(inc.get("prioridad", "-")))
            item_prio.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila, 4, item_prio)

            # 5: Estado (Badge + Indicador de 5 días de vencimiento si aplica)
            self.tabla.setCellWidget(fila, 5, self._crear_badge_estado(inc))

            # 6: Técnico asignado
            tecnico = inc.get("tecnico_nombre") or inc.get("tecnico") or "Sin asignar"
            item_tec = QTableWidgetItem(str(tecnico))
            item_tec.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila, 6, item_tec)

            # 7: Fecha
            fecha = str(inc.get("fecha", "-"))[:16]
            item_fecha = QTableWidgetItem(fecha)
            item_fecha.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(fila, 7, item_fecha)

        self._actualizar_botones()

    def _crear_badge_estado(self, inc: dict) -> QWidget:
        """Crea el badge de estado e incluye el indicador rojo si pasaron 5 días."""
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        estado = inc.get("estado", "Pendiente")
        badge_estado = QLabel(f" {estado} ")
        badge_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        aplicar_estado_visual(badge_estado, estado)
        layout.addWidget(badge_estado)

        # Indicador de vencimiento (+5 días desde fecha_confirmado)
        if inc.get("vencida"):
            badge_vencida = QLabel("⚠️ +5d")
            badge_vencida.setToolTip("Incidencia vencida: Han pasado más de 5 días desde su confirmación.")
            badge_vencida.setStyleSheet(
                f"background-color: {Colors.ROJO_ADMIN}; color: {Colors.BLANCO}; "
                f"font-weight: bold; border-radius: 4px; padding: 1px 5px; font-size: 11px;"
            )
            layout.addWidget(badge_vencida)

        return contenedor

    def _obtener_selecciones(self) -> List[Dict[str, Any]]:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return []
        resultado = []
        for index in filas:
            fila = index.row()
            item = self.tabla.item(fila, 0)
            datos = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(datos, dict):
                resultado.append(datos)
            elif fila < len(self._incidencias_visibles):
                resultado.append(self._incidencias_visibles[fila])
        return resultado

    def _obtener_seleccion(self) -> Optional[Dict[str, Any]]:
        selecciones = self._obtener_selecciones()
        return selecciones[0] if selecciones else None

    def _on_seleccion_cambiada(self):
        self._actualizar_botones()

    def _actualizar_botones(self):
        selecciones = self._obtener_selecciones()
        cantidad = len(selecciones)
        tiene_seleccion = cantidad > 0
        es_uno = cantidad == 1

        self.btn_ver_detalle.setEnabled(es_uno)
        self.buscador.actualizar_seleccion(tiene_seleccion)
        self.buscador.boton_editar.setEnabled(es_uno)
        self.buscador.boton_reasignar.setEnabled(es_uno)
        self.buscador.boton_eliminar.setEnabled(tiene_seleccion)

        if es_uno:
            inc = selecciones[0]
            id_rep = inc.get("id_reporte")
            lab = inc.get("laboratorio")
            eq = inc.get("equipo")
            self.label_info.setText(f"Seleccionada: <b style='color: {Colors.ROJO_ADMIN};'>#{id_rep}</b> — {lab} ({eq})")
        elif cantidad > 1:
            self.label_info.setText(f"Seleccionadas: <b style='color: {Colors.ROJO_ADMIN};'>{cantidad} incidencias</b> para eliminar o exportar.")
        else:
            self.label_info.setText("Haz doble clic en una fila o selecciónala para editar o ver su historial.")

    def _eliminar_seleccionadas(self):
        selecciones = self._obtener_selecciones()
        if not selecciones:
            QMessageBox.warning(
                self,
                "Eliminar Incidencias",
                "Por favor selecciona una o más incidencias de la tabla para eliminar.",
            )
            return

        cantidad = len(selecciones)
        ids = [s.get("id_reporte") for s in selecciones if s.get("id_reporte")]
        if not ids:
            return

        if cantidad == 1:
            inc = selecciones[0]
            id_rep = inc.get("id_reporte")
            lab = inc.get("laboratorio", "-")
            eq = inc.get("equipo", "-")
            tipo = inc.get("tipo_problema", "-")
            estado = inc.get("estado", "-")
            mensaje = (
                f"¿Estás seguro de que deseas eliminar permanentemente la incidencia #{id_rep}?\n\n"
                f"• Ubicación: {lab} ({eq})\n"
                f"• Tipo de problema: {tipo}\n"
                f"• Estado: {estado}\n\n"
                "Esta acción no se puede deshacer."
            )
        else:
            ids_texto = ", ".join(f"#{i}" for i in ids[:10])
            if len(ids) > 10:
                ids_texto += f" y {len(ids) - 10} más"
            mensaje = (
                f"¿Estás seguro de que deseas eliminar permanentemente las {cantidad} incidencias seleccionadas?\n\n"
                f"Incidencias: {ids_texto}\n\n"
                "Esta acción no se puede deshacer."
            )

        respuesta = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            mensaje,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        resultado = incidencia_service.eliminar_incidencias(ids)
        if resultado.get("exito"):
            QMessageBox.information(
                self,
                "Incidencias Eliminadas",
                resultado.get("mensaje", f"{cantidad} incidencia(s) eliminada(s) correctamente."),
            )
            self.cargar_datos()
        else:
            QMessageBox.critical(
                self,
                "Error al Eliminar",
                resultado.get("mensaje", "No se pudieron eliminar las incidencias de la base de datos."),
            )

    def _abrir_edicion_seleccionada(self):
        datos = self._obtener_seleccion()
        if not datos:
            QMessageBox.warning(self, "Editar Incidencia", "Por favor selecciona una incidencia de la tabla.")
            return

        id_rep = datos.get("id_reporte", 0)
        detalle = DetalleIncidenciaWidget(datos, self, usuario_rol="Administrador", solo_lectura=False)
        detalle.cerrar_solicitado.connect(self._cerrar_modal_detalle)
        detalle.guardado_exitoso.connect(lambda: self._on_edicion_guardada(id_rep))

        self._modal_detalle = ModalOverlay(detalle, self, tamano=(650, 680))
        self._modal_detalle.mostrar()

    def _on_edicion_guardada(self, id_reporte: int):
        self.cargar_datos()
        self.incidencia_actualizada.emit(id_reporte)

    def _abrir_detalle_seleccionado(self):
        datos = self._obtener_seleccion()
        if not datos:
            return

        detalle = DetalleIncidenciaWidget(datos, self, solo_lectura=True)
        detalle.cerrar_solicitado.connect(self._cerrar_modal_detalle)

        self._modal_detalle = ModalOverlay(detalle, self, tamano=(650, 680))
        self._modal_detalle.mostrar()

    def _cerrar_modal_detalle(self):
        if self._modal_detalle:
            self._modal_detalle.cerrar()
            self._modal_detalle = None

    def _abrir_dialogo_reasignar(self):
        """Abre el diálogo modal para que el Administrador reasigne la incidencia a otro técnico."""
        datos = self._obtener_seleccion()
        if not datos:
            QMessageBox.warning(
                self,
                "Seleccionar Incidencia",
                "Por favor selecciona una incidencia de la tabla para reasignarla.",
            )
            return

        widget = DialogoReasignarWidget(datos, self)
        widget.cancelado.connect(self._cerrar_modal_reasignar)
        widget.confirmado.connect(
            lambda nuevo_carnet: self._ejecutar_reasignacion(datos, nuevo_carnet)
        )
        self._modal_reasignar = ModalOverlay(widget, self, tamano=(480, 310))
        self._modal_reasignar.mostrar()

    def _cerrar_modal_reasignar(self):
        if getattr(self, "_modal_reasignar", None):
            self._modal_reasignar.cerrar()
            self._modal_reasignar = None

    def _ejecutar_reasignacion(self, datos: dict, nuevo_carnet: str):
        id_rep = datos.get("id_reporte")
        if not id_rep:
            return

        resultado = incidencia_service.reasignar_incidencia(id_rep, nuevo_carnet)
        if resultado.get("exito"):
            self._cerrar_modal_reasignar()
            QMessageBox.information(
                self,
                "Incidencia Reasignada",
                resultado.get("mensaje", "La incidencia ha sido reasignada exitosamente."),
            )
            self.cargar_datos()
            self.incidencia_actualizada.emit(id_rep)
        else:
            QMessageBox.critical(
                self,
                "Error al Reasignar",
                resultado.get("mensaje", "No se pudo reasignar la incidencia."),
            )

    # ------------------------------------------------------------------
    # Exportación a PDF
    # ------------------------------------------------------------------
    def _exportar_seleccionado_pdf(self):
        datos = self._obtener_seleccion()
        if not datos:
            QMessageBox.warning(self, "Exportar PDF", "Selecciona una incidencia de la tabla.")
            return

        id_rep = datos.get("id_reporte", "X")
        nombre_sugerido = f"Incidencia_{id_rep}.pdf"
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, f"Exportar Incidencia #{id_rep} a PDF", nombre_sugerido, "Documentos PDF (*.pdf)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith(".pdf"):
            ruta_archivo += ".pdf"

        html = f"""<html><head><style>
            body {{ font-family: Arial, sans-serif; margin: 20px; color: #1F2937; }}
            h1 {{ color: {Colors.ROJO_ADMIN}; border-bottom: 2px solid {Colors.ROJO_ADMIN}; padding-bottom: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            th, td {{ padding: 8px 12px; text-align: left; border: 1px solid #E5E7EB; }}
            th {{ background-color: {Colors.ROJO_ADMIN_FONDO}; color: {Colors.ROJO_ADMIN}; width: 28%; font-weight: bold; }}
            .footer {{ margin-top: 30px; font-size: 9pt; color: #6B7280; text-align: center; }}
        </style></head><body>
            <h1>Reporte de Incidencia #{id_rep}</h1>
            <table>
                <tr><th>ID Reporte</th><td>#{id_rep}</td></tr>
                <tr><th>Laboratorio</th><td>{datos.get('laboratorio', '-')}</td></tr>
                <tr><th>Equipo</th><td>{datos.get('equipo', '-')}</td></tr>
                <tr><th>Tipo de problema</th><td>{datos.get('tipo_problema', '-')}</td></tr>
                <tr><th>Prioridad</th><td>{datos.get('prioridad', '-')}</td></tr>
                <tr><th>Estado</th><td><b>{datos.get('estado', '-')}</b></td></tr>
                <tr><th>Técnico asignado</th><td>{datos.get('tecnico_nombre') or datos.get('tecnico') or 'Sin asignar'}</td></tr>
                <tr><th>Fecha de reporte</th><td>{str(datos.get('fecha', '-'))}</td></tr>
                <tr><th>Fecha confirmación</th><td>{str(datos.get('fecha_confirmado', 'No confirmada'))}</td></tr>
                <tr><th>Fecha resolución</th><td>{str(datos.get('fecha_resolucion', 'Pendiente'))}</td></tr>
                <tr><th>Reportado por</th><td>{datos.get('profesor_nombre') or datos.get('profesor') or '-'}</td></tr>
                <tr><th>Descripción</th><td>{datos.get('descripcion', '-')}</td></tr>
                <tr><th>Reporte de cierre</th><td>{datos.get('reporte_cierre') or 'Sin reporte de cierre'}</td></tr>
            </table>
            <div class="footer">Generado por SIGII el {date.today().strftime('%d/%m/%Y')}. Documento corporativo de supervisión.</div>
        </body></html>"""

        self._generar_pdf(ruta_archivo, html, f"Incidencia #{id_rep} exportada exitosamente a PDF.")

    def _exportar_todo_pdf(self):
        reportes = self._incidencias_visibles
        if not reportes:
            QMessageBox.warning(self, "Exportar PDF", "No hay incidencias para exportar con los filtros actuales.")
            return

        nombre_sugerido = f"Lista_Incidencias_{date.today().strftime('%Y%m%d')}.pdf"
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Exportar Listado General a PDF", nombre_sugerido, "Documentos PDF (*.pdf)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith(".pdf"):
            ruta_archivo += ".pdf"

        filas_html = ""
        for inc in reportes:
            tec = inc.get("tecnico_nombre") or inc.get("tecnico") or "Sin asignar"
            filas_html += f"""<tr>
                <td>#{inc.get('id_reporte', '-')}</td>
                <td>{inc.get('laboratorio', '-')}</td>
                <td>{inc.get('equipo', '-')}</td>
                <td>{inc.get('tipo_problema', '-')}</td>
                <td>{inc.get('estado', '-')}</td>
                <td>{tec}</td>
                <td>{str(inc.get('fecha', '-'))[:10]}</td>
            </tr>"""

        html = f"""<html><head><style>
            body {{ font-family: Arial, sans-serif; margin: 16px; color: #1F2937; }}
            h2 {{ color: {Colors.ROJO_ADMIN}; border-bottom: 2px solid {Colors.ROJO_ADMIN}; padding-bottom: 6px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 10pt; }}
            th {{ background-color: {Colors.ROJO_ADMIN_FONDO}; color: {Colors.ROJO_ADMIN}; padding: 8px; border: 1px solid #E5E7EB; text-align: left; }}
            td {{ padding: 7px 8px; border: 1px solid #E5E7EB; }}
            .footer {{ margin-top: 24px; font-size: 9pt; color: #6B7280; text-align: center; border-top: 1px solid #E5E7EB; padding-top: 8px; }}
        </style></head><body>
            <h2>Lista General de Incidencias</h2>
            <table>
                <tr><th>ID</th><th>Laboratorio</th><th>Equipo</th><th>Problema</th><th>Estado</th><th>Técnico</th><th>Fecha</th></tr>
                {filas_html}
            </table>
            <div class="footer">Generado el {date.today().strftime('%d/%m/%Y')} · Total de registros: {len(reportes)}.</div>
        </body></html>"""

        self._generar_pdf(ruta_archivo, html, f"Se exportaron {len(reportes)} incidencias exitosamente.")

    def _exportar_todo_excel(self):
        reportes = self._incidencias_visibles
        if not reportes:
            QMessageBox.warning(
                self, "Exportar Excel",
                "No hay incidencias para exportar con los filtros actuales.",
            )
            return

        nombre_sugerido = f"Incidencias_{date.today():%Y%m%d}.xlsx"
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Exportar incidencias a Excel", nombre_sugerido,
            "Libro de Excel (*.xlsx)",
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith(".xlsx"):
            ruta_archivo += ".xlsx"

        try:
            ruta = exportar_incidencias_excel(reportes, ruta_archivo)
        except (OSError, ValueError, ImportError) as error:
            QMessageBox.critical(
                self, "Error al Exportar",
                f"No se pudo generar el archivo Excel:\n{error}",
            )
            return

        QMessageBox.information(
            self, "Exportación Exitosa",
            f"Se exportaron {len(reportes)} incidencias.\nGuardado en:\n{ruta}",
        )

    def _exportar_todo_api(self, formato: str):
        if self._export_api_worker and self._export_api_worker.isRunning():
            return
        if formato not in ("pdf", "excel_pdf"):
            QMessageBox.critical(
                self,
                "Formato no válido",
                "Selecciona una plantilla PDF o Excel para exportar el reporte como PDF.",
            )
            return

        reportes = self._incidencias_visibles
        if not reportes:
            QMessageBox.warning(
                self,
                "Exportar por API",
                "No hay incidencias para exportar con los filtros actuales.",
            )
            return

        es_plantilla_excel = formato == "excel_pdf"
        extension = ".pdf"
        etiqueta = "PDF con plantilla Excel" if es_plantilla_excel else "PDF"
        nombre_sugerido = f"Incidencias_API_{date.today():%Y%m%d}{extension}"
        filtro = "Documento PDF (*.pdf)"
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar incidencias como {etiqueta} mediante Carbone API",
            nombre_sugerido,
            filtro,
        )
        if not ruta_archivo:
            return
        ruta_archivo = str(Path(ruta_archivo).with_suffix(extension))

        confirmacion = QMessageBox.question(
            self,
            "Enviar datos a Carbone Cloud",
            "Las incidencias visibles se enviarán a Carbone Cloud para generar el archivo. "
            "¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmacion != QMessageBox.StandardButton.Yes:
            return

        self.buscador.boton_exportar_pdf.setEnabled(False)
        self.buscador.boton_exportar_pdf.setText(f"Generando {etiqueta} con Carbone...")
        worker = ReportExportAPIWorker(
            [dict(reporte) for reporte in reportes],
            ruta_archivo,
            formato,
            self,
        )
        self._export_api_worker = worker
        worker.completado.connect(
            lambda ruta: QMessageBox.information(
                self,
                "Exportación por API exitosa",
                f"Se exportaron {len(reportes)} incidencias.\nGuardado en:\n{ruta}",
            )
        )
        worker.error.connect(
            lambda mensaje: QMessageBox.critical(
                self, "Error en la API de exportación", mensaje
            )
        )
        worker.finished.connect(self._finalizar_exportacion_api)
        worker.start()

    def _finalizar_exportacion_api(self):
        self._export_api_worker = None
        self.buscador.boton_exportar_pdf.setEnabled(True)
        self.buscador.boton_exportar_pdf.setText("Exportar PDF/Excel  ▾")

    def _generar_pdf(self, ruta_archivo: str, html: str, mensaje_exito: str):
        try:
            escritor = QPdfWriter(ruta_archivo)
            escritor.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            escritor.setResolution(96)
            layout = escritor.pageLayout()
            layout.setMargins(QMarginsF(20, 20, 20, 20))
            escritor.setPageLayout(layout)
            documento = QTextDocument()
            documento.setPageSize(escritor.pageLayout().paintRectPixels(96).size())
            documento.setHtml(html)
            documento.print_(escritor)
            QMessageBox.information(self, "Exportación Exitosa", f"{mensaje_exito}\nGuardado en:\n{ruta_archivo}")
        except Exception as ex:
            QMessageBox.critical(self, "Error al Exportar", f"No se pudo generar el archivo PDF:\n{str(ex)}")

    def limpiar(self):
        """Limpia el estado de la pantalla al cerrar sesión."""
        self._cerrar_modal_detalle()
        self.tabla.clearSelection()
        self._incidencias_todas = []
        self._incidencias_visibles = []
        self.tabla.setRowCount(0)
        self._actualizar_botones()
