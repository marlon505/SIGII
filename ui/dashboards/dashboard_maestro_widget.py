from datetime import date

from PySide6.QtCore import Qt, Signal, QMarginsF, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QPushButton,
    QMessageBox,
    QFileDialog,
)

from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize

from ui.modal_overlay import ModalOverlay
from ui.registrar_incidencia_form import RegistrarIncidenciaForm
from ui.detalle_incidencia_widget import DetalleIncidenciaWidget
from ui.dashboards.ui_dashboard_maestro import Ui_DashboardMaestroWidget
from ui.widgets.buscador_reportes import BuscadorReportesWidget
from resources.helpers import aplicar_estado_visual
from services import incidencia_service


class DashboardMaestroWidget(QWidget):
    """Dashboard del rol Maestro.

    Responsabilidad: mostrar resumen de laboratorios/equipos, las
    incidencias propias del Maestro (filtradas por su correo/carnet),
    las últimas incidencias del sistema y los reportes de cierre.
    """

    cerrar_sesion = Signal()
    volver_a_admin = Signal()
    incidencia_registrada = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.usuario_correo = None
        self.usuario_carnet = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Contenedor con Scroll para permitir que el dashboard sea tan amplio como sea necesario
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setObjectName(u"dashboardScroll")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.contenido = QWidget()
        self.contenido.setObjectName(u"dashboardContenido")
        self.ui = Ui_DashboardMaestroWidget()
        self.ui.setupUi(self.contenido)

        self.scroll_area.setWidget(self.contenido)
        main_layout.addWidget(self.scroll_area)

        self._aplicar_styled_background()
        self._conectar_senales()
        self._ajustar_tamanos()
        self._crear_buscador_reportes()
        self._crear_boton_actualizar()
        self._crear_boton_registrar()
        self._crear_boton_salir_modo_vista()

        # Timer de sincronización periódica (cada 15s) entre equipos
        self._timer_actualizacion = QTimer(self)
        self._timer_actualizacion.setInterval(15000)
        self._timer_actualizacion.timeout.connect(self._on_timer_actualizacion)

        self.cargar_datos()

    def recargar(self, *args):
        """Recarga todas las incidencias y estadísticas desde MySQL."""
        self.cargar_datos()

    def _on_timer_actualizacion(self):
        """Consulta periódica para sincronizar con otras instancias de técnicos."""
        if self.isVisible():
            self._cargar_mis_reportes()
            self._cargar_ultimos_reportes()

    def showEvent(self, event):
        """Recarga automática al mostrar el widget e inicia el timer de 15 s."""
        super().showEvent(event)
        self.recargar()
        if not self._timer_actualizacion.isActive():
            self._timer_actualizacion.start()

    def hideEvent(self, event):
        """Detiene el timer cuando el widget no está visible para ahorrar recursos."""
        super().hideEvent(event)
        if self._timer_actualizacion.isActive():
            self._timer_actualizacion.stop()

    def set_usuario(self, correo: str, carnet: str = None):
        """Establece el usuario activo autenticado y recarga sus reportes."""
        self.usuario_correo = correo
        self.usuario_carnet = carnet
        self.cargar_datos()

    def _conectar_senales(self):
        self.ui.boton_cerrar_sesion.clicked.connect(self.cerrar_sesion.emit)
        self.ui.tabla_mis_reportes.cellDoubleClicked.connect(self._on_mis_reportes_doble_clic)
        self.ui.tabla_mis_reportes.itemSelectionChanged.connect(self._on_seleccion_mis_reportes_cambiada)

    def _ajustar_tamanos(self):
        self.ui.tabla_mis_reportes.setMinimumHeight(250)
        self.ui.lista_ultimos_reportes.setMinimumHeight(150)
        self.ui.frame_resumen_laboratorios.setMinimumHeight(95)
        self.ui.frame_resumen_equipos.setMinimumHeight(95)

    def _crear_buscador_reportes(self):
        """Inserta el buscador y entrega al widget el catálogo ya consultado."""
        self.buscador_reportes = BuscadorReportesWidget(self.ui.frame_mis_reportes)
        layout_reportes = self.ui.frame_mis_reportes.layout()
        layout_reportes.insertWidget(1, self.buscador_reportes)
        self.buscador_reportes.filtros_cambiados.connect(self._filtrar_mis_reportes)
        self.buscador_reportes.accion_editar.connect(self._editar_seleccion)
        self.buscador_reportes.accion_eliminar.connect(self._eliminar_seleccion)
        self.buscador_reportes.accion_exportar_pdf.connect(self._exportar_pdf_seleccion)
        self.buscador_reportes.accion_exportar_todo_pdf.connect(self._exportar_todo_pdf)

        try:
            laboratorios = incidencia_service.obtener_laboratorios()
            self.buscador_reportes.cargar_laboratorios([
                (laboratorio["id_laboratorio"], laboratorio["nombre"])
                for laboratorio in laboratorios
            ])
        except Exception as err:
            print(f"Error al cargar catálogo de laboratorios: {err}")

    def _aplicar_styled_background(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.contenido.setAttribute(Qt.WA_StyledBackground, True)
        for frame in (
            self.ui.barra_superior,
            self.ui.frame_resumen_laboratorios,
            self.ui.frame_resumen_equipos,
            self.ui.frame_mis_reportes,
            self.ui.frame_ultimos_reportes,
        ):
            frame.setAttribute(Qt.WA_StyledBackground, True)

    def cargar_datos(self):
        """Recarga todos los componentes del dashboard con datos frescos de la BD."""
        stats = self._obtener_estadisticas_seguras()
        self._cargar_resumen_laboratorios(stats)
        self._cargar_resumen_equipos(stats)
        self._cargar_mis_reportes()
        self._cargar_ultimos_reportes()

    def _obtener_estadisticas_seguras(self) -> dict:
        try:
            return incidencia_service.obtener_resumen_estadisticas()
        except Exception as e:
            print(f"Advertencia al obtener estadísticas: {e}")
            return {
                "laboratorios_operativos": 0,
                "laboratorios_total": 0,
                "equipos_operativos": 0,
                "equipos_fuera": 0,
            }

    def _cargar_resumen_laboratorios(self, stats: dict):
        operativos = stats.get("laboratorios_operativos", 0)
        total = stats.get("laboratorios_total", 0)
        self.ui.label_valor_laboratorios.setText(f"{operativos} operativos / {total} total")

    def _cargar_resumen_equipos(self, stats: dict):
        operativos = stats.get("equipos_operativos", 0)
        fuera_de_servicio = stats.get("equipos_fuera", 0)
        self.ui.label_valor_equipos.setText(
            f"{operativos} operativos / {fuera_de_servicio} fuera de servicio"
        )

    def _configurar_tabla(self, tabla: QTableWidget):
        tabla.setRowCount(0)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        tabla.setShowGrid(False)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setVisible(False)
        tabla.verticalHeader().setDefaultSectionSize(44)
        tabla.horizontalHeader().setHighlightSections(False)
        tabla.horizontalHeader().setStretchLastSection(False)

    def _crear_badge_estado(self, estado: str) -> QWidget:
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel(estado)
        badge.setObjectName(u"badgeEstado")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(24)

        estado_norm = estado.lower().strip()
        if "proceso" in estado_norm or "reparacion" in estado_norm:
            badge.setProperty("tipo_estado", "proceso")
        elif "confirmado" in estado_norm:
            badge.setProperty("tipo_estado", "confirmado")
        elif "pendiente" in estado_norm:
            badge.setProperty("tipo_estado", "pendiente")
        elif "resuelto" in estado_norm:
            badge.setProperty("tipo_estado", "resuelto")
        elif "reabierto" in estado_norm:
            badge.setProperty("tipo_estado", "reabierto")
        else:
            badge.setProperty("tipo_estado", "general")

        layout.addWidget(badge)
        return contenedor

    def _cargar_mis_reportes(self):
        """Consulta y muestra las incidencias registradas por el profesor actual (o todas en modo de visión)."""
        try:
            correo_consulta = None if getattr(self, "es_modo_vision", False) else self.usuario_correo
            self._mis_reportes_todos = incidencia_service.listar_incidencias_del_maestro(
                correo_consulta
            )
        except Exception as err:
            print(f"Error al cargar mis reportes: {err}")
            self._mis_reportes_todos = []

        self._filtrar_mis_reportes(self.buscador_reportes.filtros_actuales())

    def _filtrar_mis_reportes(self, filtros: dict):
        """Filtra los reportes cargados y conserva la correspondencia fila-datos."""
        reportes = getattr(self, "_mis_reportes_todos", [])
        filtrados = [
            reporte for reporte in reportes
            if self._reporte_coincide_con_filtros(reporte, filtros)
        ]
        self._poblar_mis_reportes(filtrados)

    def _poblar_mis_reportes(self, reportes: list[dict]):
        """Renderiza solo los reportes visibles en la tabla Mis reportes."""
        tabla = self.ui.tabla_mis_reportes
        columnas = ["Laboratorio", "Equipo", "Tipo de problema", "Descripción", "Estado", "Técnico asignado", "Fecha"]
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        self._configurar_tabla(tabla)

        header = tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        tabla.setColumnWidth(4, 140)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self._mis_reportes_datos = reportes

        for fila, rep in enumerate(reportes):
            tabla.insertRow(fila)
            lab = rep.get("laboratorio", "-")
            equipo = rep.get("equipo", "-")
            tipo = rep.get("tipo_problema", "-")
            descripcion = rep.get("descripcion", "-")
            estado = rep.get("estado", "Pendiente")
            tecnico = rep.get("tecnico_nombre") or rep.get("tecnico") or "Sin asignar"
            fecha = str(rep.get("fecha", "-"))

            # 0: Lab
            item_lab = QTableWidgetItem(str(lab))
            item_lab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_lab.setData(Qt.ItemDataRole.UserRole, rep)
            tabla.setItem(fila, 0, item_lab)

            # 1: Equipo
            item_eq = QTableWidgetItem(str(equipo))
            item_eq.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 1, item_eq)

            # 2: Tipo de problema
            item_tipo = QTableWidgetItem(str(tipo))
            item_tipo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 2, item_tipo)

            # 3: Descripción
            item_desc = QTableWidgetItem(str(descripcion))
            item_desc.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item_desc.setToolTip(f"Doble clic para ver detalles:\n{descripcion}")
            tabla.setItem(fila, 3, item_desc)

            # 4: Estado (usando aplicar_estado_visual oficial)
            label_estado = QLabel(estado)
            label_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
            aplicar_estado_visual(label_estado, estado)
            tabla.setCellWidget(fila, 4, label_estado)

            # 5: Técnico asignado
            item_tec = QTableWidgetItem(str(tecnico))
            item_tec.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 5, item_tec)

            # 6: Fecha
            item_fecha = QTableWidgetItem(str(fecha))
            item_fecha.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 6, item_fecha)

    @staticmethod
    def _reporte_coincide_con_filtros(reporte: dict, filtros: dict) -> bool:
        texto = filtros["texto"].casefold()
        texto_reporte = " ".join(str(reporte.get(campo, "")) for campo in (
            "laboratorio", "equipo", "descripcion"
        )).casefold()
        if texto and texto not in texto_reporte:
            return False

        laboratorio = filtros["laboratorio"]
        if laboratorio and reporte.get("id_laboratorio") != laboratorio:
            return False

        estado = filtros["estado"]
        estados_equivalentes = {
            "Pendiente": {"Pendiente"},
            "Confirmado": {"Confirmado"},
            "En reparación": {"En reparación", "En reparacion", "En proceso"},
            "Resuelto": {"Resuelto"},
            "Reabierto": {"Reabierto"},
        }
        if estado and reporte.get("estado") not in estados_equivalentes[estado]:
            return False

        fecha_reporte = DashboardMaestroWidget._fecha_de_reporte(reporte.get("fecha"))
        fecha_desde = filtros["fecha_desde"]
        fecha_hasta = filtros["fecha_hasta"]
        if fecha_desde and (fecha_reporte is None or fecha_reporte < fecha_desde):
            return False
        if fecha_hasta and (fecha_reporte is None or fecha_reporte > fecha_hasta):
            return False
        return True

    @staticmethod
    def _fecha_de_reporte(valor) -> date | None:
        if isinstance(valor, date):
            return valor
        try:
            return date.fromisoformat(str(valor)[:10])
        except (TypeError, ValueError):
            return None


    def _on_mis_reportes_doble_clic(self, row: int, col: int):
        if hasattr(self, "_mis_reportes_datos") and 0 <= row < len(self._mis_reportes_datos):
            datos = self._mis_reportes_datos[row]
            self._mostrar_detalle_incidencia(datos)

    def _on_seleccion_mis_reportes_cambiada(self):
        """Habilita/deshabilita los botones Editar y Eliminar según la selección actual."""
        hay_seleccion = bool(self.ui.tabla_mis_reportes.selectedItems())
        self.buscador_reportes.actualizar_seleccion(hay_seleccion)
        if getattr(self, "es_modo_vision", False):
            self.buscador_reportes.boton_eliminar.setEnabled(False)
            self.buscador_reportes.boton_eliminar.setToolTip("Acción no disponible en modo de visión.")

    def _fila_seleccionada(self) -> int | None:
        """Devuelve el índice de la fila actualmente seleccionada, o None si no hay ninguna."""
        filas = self.ui.tabla_mis_reportes.selectionModel().selectedRows()
        if filas:
            return filas[0].row()
        current = self.ui.tabla_mis_reportes.currentRow()
        return current if current >= 0 else None

    def _obtener_reporte_seleccionado(self) -> dict | None:
        """Obtiene el diccionario de datos de la incidencia seleccionada."""
        row = self._fila_seleccionada()
        if row is None:
            return None
        item = self.ui.tabla_mis_reportes.item(row, 0)
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                return data
        if hasattr(self, "_mis_reportes_datos") and 0 <= row < len(self._mis_reportes_datos):
            return self._mis_reportes_datos[row]
        return None

    def _editar_seleccion(self):
        """Abre el modal de detalle para la fila seleccionada."""
        row = self._fila_seleccionada()
        if row is not None and hasattr(self, "_mis_reportes_datos") and row < len(self._mis_reportes_datos):
            self._mostrar_detalle_incidencia(self._mis_reportes_datos[row])

    def _eliminar_seleccion(self):
        """Solicita confirmación y elimina la incidencia de la fila seleccionada."""
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return
        row = self._fila_seleccionada()
        if row is None or not hasattr(self, "_mis_reportes_datos") or row >= len(self._mis_reportes_datos):
            return
        datos = self._mis_reportes_datos[row]
        id_rep = datos.get("id_reporte")
        lab = datos.get("laboratorio", "-")
        equipo = datos.get("equipo", "-")
        if not id_rep:
            return
        respuesta = QMessageBox.question(
            self,
            "Cancelar Incidencia",
            f"¿Estás seguro de que deseas cancelar y eliminar la incidencia #{id_rep} ({lab} - {equipo})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            res = incidencia_service.eliminar_incidencia(id_rep)
            if res.get("exito"):
                QMessageBox.information(
                    self,
                    "Incidencia Cancelada",
                    f"La incidencia #{id_rep} ha sido cancelada y eliminada exitosamente.",
                )
                self.cargar_datos()
            else:
                QMessageBox.critical(
                    self,
                    "Error al Eliminar",
                    res.get("mensaje", "No se pudo eliminar la incidencia."),
                )

    def _exportar_pdf_seleccion(self):
        """Genera y descarga en formato PDF la incidencia seleccionada."""
        datos = self._obtener_reporte_seleccionado()
        if not datos:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                "Por favor, selecciona una incidencia de la tabla para exportar."
            )
            return

        id_rep = datos.get("id_reporte", "N/A")

        # 1. Solicitar ruta de guardado al usuario
        ruta_sugerida = f"Incidencia_{id_rep}.pdf"
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Incidencia en PDF",
            ruta_sugerida,
            "Documentos PDF (*.pdf)"
        )

        if not ruta_archivo:
            return  # El usuario canceló el diálogo

        # Asegurar extensión .pdf
        if not ruta_archivo.lower().endswith(".pdf"):
            ruta_archivo += ".pdf"

        # 2. Construir contenido HTML del reporte con estilos compatibles con Qt QTextDocument
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, Helvetica, sans-serif;
                    color: #1F2937;
                }}
                .header {{
                    border-bottom: 2px solid #1E3A8A;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                .titulo {{
                    color: #1E3A8A;
                    font-size: 20pt;
                    font-weight: bold;
                }}
                .subtitulo {{
                    color: #4B5563;
                    font-size: 11pt;
                    margin-top: 4px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                    margin-bottom: 20px;
                }}
                th, td {{
                    padding: 8px 12px;
                    text-align: left;
                    border-bottom: 1px solid #E5E7EB;
                    font-size: 11pt;
                }}
                th {{
                    background-color: #F3F4F6;
                    color: #1F2937;
                    width: 32%;
                    font-weight: bold;
                }}
                .descripcion-box {{
                    background-color: #F9FAFB;
                    border: 1px solid #D1D5DB;
                    padding: 12px;
                    font-size: 11pt;
                    line-height: 1.5;
                    margin-top: 8px;
                }}
                .footer {{
                    margin-top: 30px;
                    font-size: 9pt;
                    color: #6B7280;
                    text-align: center;
                    border-top: 1px solid #E5E7EB;
                    padding-top: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="titulo">Reporte de Incidencia #{id_rep}</div>
                <div class="subtitulo">Sistema de Gestión e Información de Incidencias (SIGII)</div>
            </div>

            <table border="0" cellspacing="0" cellpadding="6">
                <tr><th>ID Reporte</th><td>#{id_rep}</td></tr>
                <tr><th>Laboratorio</th><td>{datos.get('laboratorio', '-')}</td></tr>
                <tr><th>Equipo</th><td>{datos.get('equipo', '-')}</td></tr>
                <tr><th>Tipo de Problema</th><td>{datos.get('tipo_problema', '-')}</td></tr>
                <tr><th>Prioridad</th><td>{datos.get('prioridad', 'Normal')}</td></tr>
                <tr><th>Estado</th><td><b>{datos.get('estado', 'Pendiente')}</b></td></tr>
                <tr><th>Fecha de Registro</th><td>{datos.get('fecha', '-')}</td></tr>
                <tr><th>Docente Reportante</th><td>{datos.get('profesor', self.usuario_correo or '-')}</td></tr>
                <tr><th>Técnico Asignado</th><td>{datos.get('tecnico', 'Sin asignar')}</td></tr>
            </table>

            <div style="color: #1E3A8A; font-size: 13pt; font-weight: bold; margin-top: 20px;">Descripción del Problema</div>
            <div class="descripcion-box">
                {datos.get('descripcion', 'Sin descripción detallada.')}
            </div>

            <div class="footer">
                Documento generado el {date.today().strftime('%d/%m/%Y')} a través del Panel de Maestro.
            </div>
        </body>
        </html>
        """

        # 3. Escribir el documento a PDF usando QPdfWriter configurado a 96 DPI y márgenes estándar
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

            QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"El reporte de la incidencia #{id_rep} ha sido guardado exitosamente en:\n{ruta_archivo}"
            )
        except Exception as ex:
            QMessageBox.critical(
                self,
                "Error al Exportar",
                f"Ocurrió un error al intentar generar el PDF:\n{str(ex)}"
            )

    def _exportar_todo_pdf(self):
        """Genera un PDF con TODAS las incidencias actualmente visibles en la tabla."""
        reportes = getattr(self, "_mis_reportes_datos", [])
        if not reportes:
            QMessageBox.warning(
                self,
                "Exportar Todo",
                "No hay incidencias en la tabla para exportar."
            )
            return

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Todos los Reportes en PDF",
            "Todos_mis_reportes.pdf",
            "Documentos PDF (*.pdf)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith(".pdf"):
            ruta_archivo += ".pdf"

        filas_html = ""
        for rep in reportes:
            filas_html += f"""
            <tr style="border-bottom: 1px solid #E5E7EB;">
                <td>{rep.get('id_reporte', '-')}</td>
                <td>{rep.get('laboratorio', '-')}</td>
                <td>{rep.get('equipo', '-')}</td>
                <td>{rep.get('tipo_problema', '-')}</td>
                <td><b>{rep.get('estado', 'Pendiente')}</b></td>
                <td>{rep.get('fecha', '-')}</td>
            </tr>"""

        html = f"""
        <html><head><style>
            body {{ font-family: Arial, sans-serif; color: #1F2937; }}
            h2 {{ color: #1E3A8A; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th {{ background-color: #F3F4F6; font-weight: bold; padding: 8px; text-align: left; }}
            td {{ padding: 7px 8px; font-size: 10pt; }}
            .footer {{ margin-top: 30px; font-size: 9pt; color: #6B7280; text-align: center; border-top: 1px solid #E5E7EB; padding-top: 8px; }}
        </style></head><body>
            <h2>Mis Reportes de Incidencias</h2>
            <div style="color:#4B5563; font-size:10pt;">Sistema de Gestión e Información de Incidencias (SIGII)</div>
            <table>
                <tr><th>ID</th><th>Laboratorio</th><th>Equipo</th><th>Tipo</th><th>Estado</th><th>Fecha</th></tr>
                {filas_html}
            </table>
            <div class="footer">Documento generado el {date.today().strftime('%d/%m/%Y')}. Total: {len(reportes)} incidencia(s).</div>
        </body></html>
        """

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
            QMessageBox.information(
                self, "Exportación Exitosa",
                f"Se exportaron {len(reportes)} incidencias en:\n{ruta_archivo}"
            )
        except Exception as ex:
            QMessageBox.critical(self, "Error al Exportar", f"No se pudo generar el PDF:\n{str(ex)}")

    def _mostrar_detalle_incidencia(self, datos: dict):
        es_vision = getattr(self, "es_modo_vision", False)
        detalle_widget = DetalleIncidenciaWidget(datos, self, solo_lectura=es_vision)
        detalle_widget.cerrar_solicitado.connect(self._cerrar_modal)
        detalle_widget.guardado_exitoso.connect(self.cargar_datos)
        self._modal = ModalOverlay(detalle_widget, self)
        self._modal.mostrar()

    def _cargar_ultimos_reportes(self):
        """Consulta y muestra los reportes de cierre recientes."""
        lista = self.ui.lista_ultimos_reportes
        lista.clear()
        try:
            reportes = incidencia_service.obtener_ultimos_reportes_cierre(limite=5)
        except Exception as err:
            print(f"Error al cargar ultimos reportes: {err}")
            reportes = []

        if not reportes:
            reportes = ["No hay reportes de cierre recientes."]
        lista.addItems(reportes)

    def _crear_boton_actualizar(self):
        self.boton_actualizar = QPushButton("Actualizar")
        self.boton_actualizar.setObjectName("botonRegistrarIncidencia")
        self.boton_actualizar.clicked.connect(self.recargar)
        layout_barra = self.ui.barra_superior.layout()
        indice_cerrar_sesion = layout_barra.indexOf(self.ui.boton_cerrar_sesion)
        layout_barra.insertWidget(indice_cerrar_sesion, self.boton_actualizar)

    def _crear_boton_registrar(self):
        self.boton_registrar_incidencia = QPushButton("Registrar Incidencia")
        self.boton_registrar_incidencia.setObjectName("botonRegistrarIncidencia")
        self.boton_registrar_incidencia.clicked.connect(self._abrir_formulario_registrar)
        layout_barra = self.ui.barra_superior.layout()
        indice_cerrar_sesion = layout_barra.indexOf(self.ui.boton_cerrar_sesion)
        layout_barra.insertWidget(indice_cerrar_sesion, self.boton_registrar_incidencia)

    def _crear_boton_salir_modo_vista(self):
        self.boton_salir_modo_vista = QPushButton("Salir")
        self.boton_salir_modo_vista.setObjectName("botonSalirModoVista")
        self.boton_salir_modo_vista.setToolTip("Regresar al panel de administrador")
        self.boton_salir_modo_vista.clicked.connect(self.volver_a_admin.emit)
        self.boton_salir_modo_vista.hide()
        layout_barra = self.ui.barra_superior.layout()
        layout_barra.addWidget(self.boton_salir_modo_vista)

    def activar_modo_vista_admin(self, activo: bool):
        self.es_modo_vision = activo
        if hasattr(self, "boton_salir_modo_vista"):
            self.boton_salir_modo_vista.setVisible(activo)
        if hasattr(self, "buscador_reportes"):
            if activo:
                self.buscador_reportes.set_titulo("Reportes de Docentes (Modo de Visión - Solo Lectura)")
                self.buscador_reportes.boton_eliminar.setEnabled(False)
                self.buscador_reportes.boton_eliminar.setToolTip("Acción no disponible en modo de visión.")
            else:
                self.buscador_reportes.set_titulo("Buscar y filtrar mis reportes")
                self.buscador_reportes.boton_eliminar.setToolTip("")
        self.cargar_datos()

    def _abrir_formulario_registrar(self):
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return
        formulario = RegistrarIncidenciaForm()
        formulario.guardar_solicitado.connect(self._on_incidencia_guardada)
        formulario.cancelar_solicitado.connect(self._cerrar_modal)

        self._modal = ModalOverlay(formulario, self)
        self._modal.mostrar()

    def _on_incidencia_guardada(self, datos: dict):
        """Guarda la incidencia en la BD asociada al Gmail/carnet del profesor."""
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return
        resultado = incidencia_service.registrar_incidencia(self.usuario_correo, datos)
        if resultado.get("exito"):
            self._cerrar_modal()
            self.cargar_datos()
            id_rep = resultado.get("id_reporte") or 0
            self.incidencia_registrada.emit(id_rep)
            QMessageBox.information(
                self,
                "Incidencia Guardada",
                "La incidencia ha sido guardada exitosamente en la base de datos y ya aparece en tu tabla de reportes."
            )
        else:
            QMessageBox.critical(
                self,
                "Error al Guardar",
                resultado.get("mensaje", "No se pudo guardar la incidencia en la base de datos.")
            )

    def _cerrar_modal(self):
        if getattr(self, "_modal", None):
            self._modal.cerrar()
            self._modal = None
