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
from ui.detalle_incidencia_widget import DetalleIncidenciaWidget
from ui.registrar_incidencia_form import RegistrarIncidenciaForm
from ui.lista_incidencias_tecnico_widget import ListaIncidenciasTecnicoWidget
from ui.dashboards.ui_dashboard_maestro import Ui_DashboardMaestroWidget as Ui_DashboardTecnicoWidget
from ui.widgets.buscador_reportes import BuscadorReportesWidget
from ui.widgets.dialogo_reasignar_widget import DialogoReasignarWidget
from services import incidencia_service

class DashboardTecnicoWidget(QWidget):
    """Dashboard del rol Tecnico.

    Responsabilidad: mostrar resumen de laboratorios/equipos, las
    incidencias asignadas al Tecnico (filtradas por su carnet/correo),
    permitir explorar y tomar incidencias disponibles, y gestionar reportes de cierre.
    """

    cerrar_sesion = Signal()
    incidencia_actualizada = Signal(int)
    volver_a_admin = Signal()

    def _tabla_cola(self):
        """Tabla visible de la cola del técnico."""
        return self.ui.tabla_mis_reportes

    def __init__(self, parent=None):
        super().__init__(parent)

        self.usuario_correo = None
        self.usuario_carnet = None
        self.es_modo_vision = False

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
        self.contenido.setObjectName(u"dashboardContenidoTecnico")
        self.ui = Ui_DashboardTecnicoWidget()
        self.ui.setupUi(self.contenido)

        # Personalizar encabezados para el rol de Técnico
        self.ui.titulo_dashboard.setText("Panel de Técnico")
        self.ui.titulo_mis_reportes.setText("Cola de Asignaciones (Incidencias Disponibles y Asignadas)")

        self.scroll_area.setWidget(self.contenido)
        main_layout.addWidget(self.scroll_area)

        self._aplicar_styled_background()
        self._crear_boton_incidencias_disponibles()
        self._crear_boton_registrar()
        self._crear_boton_salir_modo_vista()
        self._conectar_senales()
        self._ajustar_tamanos()
        self._crear_buscador_reportes()

        self._timer_actualizacion = QTimer(self)
        self._timer_actualizacion.setInterval(15000)
        self._timer_actualizacion.timeout.connect(self.cargar_datos)
        self.cargar_datos()

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_datos()
        if not self._timer_actualizacion.isActive():
            self._timer_actualizacion.start()

    def hideEvent(self, event):
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
        self.buscador_reportes.set_titulo("Buscar y filtrar incidencias")
        # El técnico puede editar y accionar estados, pero no eliminar
        self.buscador_reportes.boton_eliminar.hide()
        self.buscador_reportes.boton_accion_estado.setText("Tomar incidencia")
        self.buscador_reportes.boton_accion_estado.setEnabled(False)
        self.buscador_reportes.boton_accion_estado.show()

        # Conectar Acciones
        self.buscador_reportes.boton_accion_estado.clicked.connect(self._avanzar_estado_seleccionado)
        self.buscador_reportes.boton_reasignar.hide()
        # Reasignar sólo permitido para Administrador
        self.buscador_reportes.accion_editar.connect(self._editar_seleccion)
        self.buscador_reportes.accion_exportar_pdf.connect(self._exportar_pdf_seleccion)
        self.buscador_reportes.accion_exportar_todo_pdf.connect(self._exportar_todo_pdf)
        
        layout_reportes = self.ui.frame_mis_reportes.layout()
        layout_reportes.insertWidget(1, self.buscador_reportes)
        self.buscador_reportes.filtros_cambiados.connect(self._filtrar_mis_reportes)

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
        self._cargar_cola_asignaciones()
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

    def _cargar_cola_asignaciones(self):
        """Consulta y muestra las asignaciones en cola para el tecnico actual (o todas en modo de visión)."""
        try:
            identificador = None if getattr(self, "es_modo_vision", False) else (self.usuario_carnet or self.usuario_correo)
            self._cola_asignaciones = incidencia_service.obtener_cola_asignaciones_por_tecnico(
                identificador
            )
        except Exception as err:
            print(f"Error al cargar la cola de asignaciones: {err}")
            self._cola_asignaciones = []

        self._filtrar_cola_asignaciones(self.buscador_reportes.filtros_actuales())

    def _filtrar_mis_reportes(self, filtros: dict):
        self._filtrar_cola_asignaciones(filtros)

    def _filtrar_cola_asignaciones(self, filtros: dict):
        """Filtra las asignaciones cargadas y conserva la correspondencia fila-datos."""
        reportes = getattr(self, "_cola_asignaciones", [])
        filtrados = [
            reporte for reporte in reportes
            if self._reporte_coincide_con_filtros(reporte, filtros)
        ]
        self._poblar_cola_asignaciones(filtrados)

    def _poblar_cola_asignaciones(self, reportes: list[dict]):
        """Renderiza solo las asignaciones visibles en la tabla Cola de asignaciones."""
        tabla = getattr(self.ui, "tabla_cola_asignaciones", self.ui.tabla_mis_reportes)
        columnas = ["Laboratorio", "Equipo", "Tipo de problema", "Descripción", "Estado", "Técnico asignado", "Fecha"]
        tabla.setColumnCount(len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        self._configurar_tabla(tabla)
        self._cola_asignaciones_datos = reportes

        header = tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        tabla.setColumnWidth(4, 130)
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

            # 4: Estado (badge)
            tabla.setCellWidget(fila, 4, self._crear_badge_estado(estado))

            # 5: Técnico asignado
            tecnico_txt = rep.get("tecnico_nombre") or rep.get("tecnico") or rep.get("carnet_tecnico") or "Sin asignar"
            item_tec = QTableWidgetItem(str(tecnico_txt))
            item_tec.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 5, item_tec)

            # 6: Fecha
            item_fecha = QTableWidgetItem(str(fecha))
            item_fecha.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 6, item_fecha)

        self._actualizar_boton_accion_estado()

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

        fecha_reporte = DashboardTecnicoWidget._fecha_de_reporte(reporte.get("fecha"))
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

    def _on_cola_doble_clic(self, row: int, col: int):
        if hasattr(self, "_cola_asignaciones_datos") and 0 <= row < len(self._cola_asignaciones_datos):
            datos = self._cola_asignaciones_datos[row]
            self._mostrar_detalle_incidencia(datos)

    def _on_seleccion_mis_reportes_cambiada(self):
        tabla = self._tabla_cola()
        self.buscador_reportes.actualizar_seleccion(
            bool(tabla.selectionModel().selectedRows())
        )
        if getattr(self, "es_modo_vision", False):
            self.buscador_reportes.boton_editar.setText("Ver detalle")
        self._actualizar_boton_accion_estado()

    def _actualizar_boton_accion_estado(self):
        boton = self.buscador_reportes.boton_accion_estado
        if getattr(self, "es_modo_vision", False):
            boton.setText("Modo de visión (solo lectura)")
            boton.setEnabled(False)
            boton.show()
            return

        datos = self._obtener_reporte_seleccionado()
        if not datos:
            boton.setText("Selecciona una incidencia")
            boton.setEnabled(False)
            boton.show()
            return

        estado = datos.get("estado", "")
        carnet_actual = self.usuario_carnet or self.usuario_correo or ""
        carnet_valido = incidencia_service.resolver_carnet_tecnico(carnet_actual) or carnet_actual
        carnet_asignado = datos.get("carnet_tecnico")
        sin_asignar = not carnet_asignado
        es_mia = carnet_asignado == carnet_valido

        if estado in ("Pendiente", "Reabierto") and sin_asignar:
            boton.setText("Tomar incidencia")
            boton.setEnabled(True)
            boton.show()
        elif es_mia and estado == "Confirmado":
            boton.setText("Iniciar reparación")
            boton.setEnabled(True)
            boton.show()
        elif es_mia and estado in ("En reparación", "En reparacion", "En proceso"):
            boton.setText("Marcar como resuelto")
            boton.setEnabled(True)
            boton.show()
        elif es_mia and estado == "Resuelto":
            boton.setText("Reabrir incidencia")
            boton.setEnabled(True)
            boton.show()
        elif carnet_asignado and not es_mia:
            tec_asignado = datos.get("tecnico_nombre") or datos.get("tecnico") or carnet_asignado
            boton.setText(f"Tomada por {tec_asignado}")
            boton.setEnabled(False)
            boton.show()
        else:
            boton.setText("Sin acción disponible")
            boton.setEnabled(False)
            boton.show()

    def _avanzar_estado_seleccionado(self):
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return
        datos = self._obtener_reporte_seleccionado()
        if not datos:
            return

        estado = datos.get("estado", "")
        carnet_actual = self.usuario_carnet or self.usuario_correo or ""
        carnet = incidencia_service.resolver_carnet_tecnico(carnet_actual) or carnet_actual

        if estado == "Pendiente":
            if datos.get("carnet_tecnico"):
                return
            resultado = incidencia_service.tomar_incidencia(datos["id_reporte"], carnet)
        elif estado == "Confirmado":
            resultado = incidencia_service.iniciar_reparacion(datos["id_reporte"], carnet)
        elif estado in ("En reparación", "En reparacion", "En proceso"):
            from PySide6.QtWidgets import QInputDialog
            reporte_cierre, ok = QInputDialog.getMultiLineText(
                self,
                "Reporte de Cierre",
                "Describe la solución aplicada antes de marcar como resuelta:",
            )
            if not ok or not reporte_cierre.strip():
                return
            resultado = incidencia_service.marcar_resuelta(
                datos["id_reporte"], carnet, reporte_cierre
            )
        elif estado == "Resuelto":
            resultado = incidencia_service.avanzar_estado_tecnico(
                datos["id_reporte"], carnet, "Confirmado"
            )
        else:
            return

        if not resultado.get("exito"):
            QMessageBox.warning(
                self,
                "No se pudo actualizar",
                resultado.get("mensaje", "No fue posible cambiar el estado."),
            )
            return

        id_reporte = datos["id_reporte"]
        # Al cambiar de estado, el filtro anterior puede ocultar esa fila.
        self.buscador_reportes.seleccionar_estado(None)
        self.cargar_datos()
        self.incidencia_actualizada.emit(id_reporte)
        for fila, reporte in enumerate(getattr(self, "_cola_asignaciones_datos", [])):
            if reporte.get("id_reporte") == id_reporte:
                self._tabla_cola().selectRow(fila)
                break

    def _fila_seleccionada(self) -> int | None:
        filas = self._tabla_cola().selectionModel().selectedRows()
        return filas[0].row() if filas else None

    def _obtener_reporte_seleccionado(self) -> dict | None:
        fila = self._fila_seleccionada()
        if fila is None:
            return None

        item = self._tabla_cola().item(fila, 0)
        if item:
            datos = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(datos, dict):
                return datos

        reportes = getattr(self, "_cola_asignaciones_datos", [])
        return reportes[fila] if fila < len(reportes) else None

    def _abrir_dialogo_reasignar(self):
        """Abre el diálogo modal para reasignar la incidencia a otro técnico."""
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return

        datos = self._obtener_reporte_seleccionado()
        if not datos:
            QMessageBox.warning(
                self,
                "Seleccionar Incidencia",
                "Por favor, selecciona una incidencia de la tabla para reasignarla.",
            )
            return

        widget = DialogoReasignarWidget(datos, self)
        widget.cancelado.connect(self._cerrar_modal)
        widget.confirmado.connect(
            lambda nuevo_carnet: self._ejecutar_reasignacion(datos, nuevo_carnet)
        )
        self._modal = ModalOverlay(widget, self, tamano=(480, 310))
        self._modal.mostrar()

    def _ejecutar_reasignacion(self, datos: dict, nuevo_carnet: str):
        id_rep = datos.get("id_reporte")
        if not id_rep:
            return

        resultado = incidencia_service.reasignar_incidencia(id_rep, nuevo_carnet)
        if resultado.get("exito"):
            self._cerrar_modal()
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

    def _editar_seleccion(self):
        """Abre el modal de detalle para la fila seleccionada."""
        datos = self._obtener_reporte_seleccionado()
        if datos:
            self._mostrar_detalle_incidencia(datos)

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

    def _mostrar_detalle_incidencia(self, datos: dict):
        es_vision = getattr(self, "es_modo_vision", False)
        widget = DetalleIncidenciaWidget(datos, self, usuario_rol="Técnico", solo_lectura=es_vision)
        widget.cerrar_solicitado.connect(self._cerrar_modal)
        widget.guardado_exitoso.connect(self.cargar_datos)
        self._modal = ModalOverlay(widget, self)
        self._modal.mostrar()

    def _abrir_aceptar_incidencia(self, datos: dict):
        self._mostrar_detalle_incidencia(datos)

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

    def _crear_boton_incidencias_disponibles(self):
        self.boton_incidencias_disponibles = QPushButton("Tomar incidencias")
        self.boton_incidencias_disponibles.setObjectName("botonRegistrarIncidencia")
        self.boton_incidencias_disponibles.setMinimumHeight(38)
        self.boton_incidencias_disponibles.clicked.connect(self._abrir_incidencias_disponibles)
        layout_barra = self.ui.barra_superior.layout()
        indice_cerrar_sesion = layout_barra.indexOf(self.ui.boton_cerrar_sesion)
        layout_barra.insertWidget(indice_cerrar_sesion, self.boton_incidencias_disponibles)

    def _abrir_incidencias_disponibles(self):
        if getattr(self, "es_modo_vision", False):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return
        carnet_o_correo = self.usuario_carnet or self.usuario_correo or ""
        widget = ListaIncidenciasTecnicoWidget(carnet_o_correo)
        widget.volver_solicitado.connect(self._cerrar_modal)
        widget.incidencia_actualizada.connect(self._on_incidencia_actualizada)
        self._modal = ModalOverlay(widget, self, tamano=(980, 720))
        self._modal.mostrar()

    def _on_incidencia_actualizada(self, id_reporte: int):
        self.cargar_datos()
        self.incidencia_actualizada.emit(id_reporte)

    def _crear_boton_registrar(self):
        self.boton_registrar_incidencia = QPushButton("Registrar Incidencia")
        self.boton_registrar_incidencia.setObjectName("botonRegistrarIncidencia")
        self.boton_registrar_incidencia.setMinimumHeight(38)
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
        if hasattr(self, "boton_incidencias_disponibles"):
            self.boton_incidencias_disponibles.setVisible(not activo)
        if hasattr(self, "boton_registrar_incidencia"):
            self.boton_registrar_incidencia.setEnabled(not activo)
            self.boton_registrar_incidencia.setToolTip("Acción no disponible en modo de visión." if activo else "")
        if hasattr(self, "buscador_reportes"):
            if activo:
                self.buscador_reportes.set_titulo("Cola de Asignaciones (Modo de Visión - Solo Lectura)")
                self.buscador_reportes.boton_editar.setText("Ver detalle")
                self.buscador_reportes.boton_accion_estado.setText("Modo de visión (solo lectura)")
                self.buscador_reportes.boton_accion_estado.setEnabled(False)
            else:
                self.buscador_reportes.set_titulo("Buscar y filtrar incidencias")
                self.buscador_reportes.boton_editar.setText("Editar")
                self.buscador_reportes.boton_accion_estado.setText("Tomar incidencia")
                self._actualizar_boton_accion_estado()
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
        identificador = self.usuario_carnet or self.usuario_correo
        resultado = incidencia_service.registrar_incidencia(
            self.usuario_correo or self.usuario_carnet,
            datos,
            carnet_tecnico=identificador
        )
        if resultado.get("exito"):
            self._cerrar_modal()
            self.cargar_datos()
            id_rep = resultado.get("id_reporte")
            if id_rep:
                self.incidencia_actualizada.emit(id_rep)
            QMessageBox.information(
                self, "Incidencia Guardada",
                "La incidencia ha sido guardada exitosamente y asignada a tu cola de trabajo."
            )
        else:
            QMessageBox.critical(
                self, "Error al Guardar",
                resultado.get("mensaje", "No se pudo guardar la incidencia.")
            )

    def _exportar_todo_pdf(self):
        """Genera un PDF con TODAS las incidencias visibles en la tabla del técnico."""
        reportes = getattr(self, "_mis_reportes_datos", [])
        if not reportes:
            QMessageBox.warning(self, "Exportar Todo", "No hay incidencias en la tabla.")
            return
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar Todos los Reportes en PDF",
            "Mis_asignaciones.pdf", "Documentos PDF (*.pdf)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith(".pdf"):
            ruta_archivo += ".pdf"
        filas_html = ""
        for rep in reportes:
            filas_html += f"""<tr>
                <td>{rep.get('id_reporte','-')}</td>
                <td>{rep.get('laboratorio','-')}</td>
                <td>{rep.get('equipo','-')}</td>
                <td>{rep.get('tipo_problema','-')}</td>
                <td><b>{rep.get('estado','Pendiente')}</b></td>
                <td>{rep.get('tecnico_nombre') or rep.get('carnet_tecnico') or 'Sin asignar'}</td>
                <td>{rep.get('fecha','-')}</td></tr>"""
        html = f"""<html><head><style>
            body{{font-family:Arial,sans-serif;color:#1F2937;}}
            h2{{color:#1E3A8A;}}
            table{{width:100%;border-collapse:collapse;margin-top:15px;}}
            th{{background:#F3F4F6;font-weight:bold;padding:8px;text-align:left;}}
            td{{padding:7px 8px;font-size:10pt;}}
            .footer{{margin-top:30px;font-size:9pt;color:#6B7280;text-align:center;border-top:1px solid #E5E7EB;padding-top:8px;}}
        </style></head><body>
            <h2>Cola de Asignaciones</h2>
            <table><tr><th>ID</th><th>Laboratorio</th><th>Equipo</th><th>Tipo</th><th>Estado</th><th>Técnico</th><th>Fecha</th></tr>
            {filas_html}</table>
            <div class="footer">Generado el {date.today().strftime('%d/%m/%Y')}. Total: {len(reportes)} incidencia(s).</div>
        </body></html>"""
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
            QMessageBox.information(self, "Exportación Exitosa",
                f"Se exportaron {len(reportes)} incidencias en:\n{ruta_archivo}")
        except Exception as ex:
            QMessageBox.critical(self, "Error al Exportar", f"No se pudo generar el PDF:\n{str(ex)}")

    def _cerrar_modal(self):
        if getattr(self, "_modal", None):
            self._modal.cerrar()
            self._modal = None
            self.cargar_datos()
