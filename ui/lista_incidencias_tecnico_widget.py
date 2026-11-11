# ui/lista_incidencias_tecnico_widget.py
# -*- coding: utf-8 -*-
"""Cola compartida de incidencias para el rol Técnico.

Muestra todas las incidencias abiertas del sistema. El técnico puede
tomar una incidencia Pendiente, iniciar su reparación y marcarla como
resuelta desde una barra de acciones dedicada (independiente del
BuscadorReportesWidget).

Arquitectura:
- Solo emite señales; nunca navega ni accede directamente a la BD.
- Recibe el servicio de incidencias a través del módulo importado (DI por módulo).
- La señal incidencia_actualizada(int) la escucha MainWindow para notificar al Maestro.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QMessageBox,
    QAbstractItemView,
    QFrame,
    QTextEdit,
    QSizePolicy,
)

from ui.widgets.buscador_reportes import BuscadorReportesWidget
from ui.modal_overlay import ModalOverlay
from ui.widgets.dialogo_reasignar_widget import DialogoReasignarWidget
from resources.helpers import aplicar_estado_visual
from services import incidencia_service


# ---------------------------------------------------------------------------
# Overlay de reporte de cierre
# ---------------------------------------------------------------------------

class _OverlayReporteCierre(QWidget):
    """Overlay oscuro con formulario de reporte de cierre.

    Se coloca sobre el widget padre llenando todo su espacio. El
    resultado se entrega mediante la señal ``confirmado(str)``; si el
    usuario cancela, emite ``cancelado``.
    """

    confirmado = Signal(str)
    cancelado = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("overlayReporteCierre")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#overlayReporteCierre { background-color: rgba(0,0,0,0.55); }"
        )

        tarjeta = QFrame(self)
        tarjeta.setObjectName("tarjetaReporteCierre")
        tarjeta.setStyleSheet(
            "QFrame#tarjetaReporteCierre {"
            "  background-color: #FFFFFF;"
            "  border-radius: 12px;"
            "  padding: 24px;"
            "}"
        )
        tarjeta.setFixedWidth(520)
        tarjeta.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        layout_tarjeta = QVBoxLayout(tarjeta)
        layout_tarjeta.setSpacing(14)

        titulo = QLabel("Reporte de cierre")
        titulo.setStyleSheet("font-size: 16px; font-weight: 700; color: #1E3A8A;")
        layout_tarjeta.addWidget(titulo)

        instruccion = QLabel(
            "Describe brevemente la solución aplicada antes de marcar la incidencia como resuelta."
        )
        instruccion.setWordWrap(True)
        instruccion.setStyleSheet("color: #475569; font-size: 13px;")
        layout_tarjeta.addWidget(instruccion)

        self.texto = QTextEdit()
        self.texto.setPlaceholderText(
            "Ej: Se reemplazó el cable de alimentación y se verificó el arranque del equipo..."
        )
        self.texto.setMinimumHeight(120)
        self.texto.setMaximumHeight(200)
        self.texto.setStyleSheet(
            "QTextEdit {"
            "  border: 1px solid #D1D5DB;"
            "  border-radius: 6px;"
            "  padding: 8px;"
            "  font-size: 13px;"
            "  color: #1F2937;"
            "}"
            "QTextEdit:focus { border-color: #16A34A; }"
        )
        layout_tarjeta.addWidget(self.texto)

        fila_botones = QHBoxLayout()
        fila_botones.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("botonSecundario")
        btn_cancelar.setFixedHeight(36)
        btn_cancelar.clicked.connect(self._on_cancelar)
        fila_botones.addWidget(btn_cancelar)

        btn_confirmar = QPushButton("Confirmar resolución")
        btn_confirmar.setObjectName("botonAccionPrincipal")
        btn_confirmar.setFixedHeight(36)
        btn_confirmar.clicked.connect(self._on_confirmar)
        fila_botones.addWidget(btn_confirmar)

        layout_tarjeta.addLayout(fila_botones)

        layout_overlay = QVBoxLayout(self)
        layout_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_overlay.addWidget(tarjeta)

    def _on_confirmar(self):
        texto = self.texto.toPlainText().strip()
        if not texto:
            QMessageBox.warning(
                self, "Campo requerido",
                "El reporte de cierre no puede estar vacío.",
            )
            self.texto.setFocus()
            return
        self.confirmado.emit(texto)

    def _on_cancelar(self):
        self.cancelado.emit()

    def mostrar(self):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()
        self.texto.setFocus()

    def cerrar(self):
        self.texto.clear()
        self.hide()


# ---------------------------------------------------------------------------
# Widget principal
# ---------------------------------------------------------------------------

class ListaIncidenciasTecnicoWidget(QWidget):
    """Cola compartida: todas las incidencias abiertas del sistema.

    Permite seleccionar una incidencia y avanzar su estado con una barra
    de acciones contextual. La base de datos valida asignación y transición.
    """

    volver_solicitado = Signal()
    #: Emitida tras cada transición exitosa con el id_reporte afectado.
    incidencia_actualizada = Signal(int)

    def __init__(self, carnet_tecnico: str, parent=None):
        super().__init__(parent)
        self.carnet_tecnico = incidencia_service.resolver_carnet_tecnico(carnet_tecnico) or carnet_tecnico
        self._incidencias_todas: list[dict] = []
        self._incidencias_visibles: list[dict] = []
        self._error_carga: str | None = None
        self._overlay_cierre: _OverlayReporteCierre | None = None

        self._construir_ui()
        self._conectar_senales()
        self.cargar_datos()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ── Cabecera ──────────────────────────────────────────────────
        fila_cabecera = QHBoxLayout()
        titulo = QLabel("Incidencias Disponibles para Tomar")
        titulo.setObjectName("tituloListaTecnico")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold; color: #15803D;")
        fila_cabecera.addWidget(titulo)
        fila_cabecera.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("botonSecundario")
        btn_cerrar.clicked.connect(self.volver_solicitado.emit)
        fila_cabecera.addWidget(btn_cerrar)
        layout.addLayout(fila_cabecera)

        # ── Buscador / filtros ────────────────────────────────────────
        self.buscador = BuscadorReportesWidget(self)
        self.buscador.set_titulo("Selecciona una incidencia y elige la acción")
        self.buscador.boton_editar.hide()
        self.buscador.boton_eliminar.hide()
        self.buscador.boton_exportar_pdf.hide()
        self.buscador.boton_accion_estado.hide()   # La barra dedicada lo reemplaza
        self.buscador.boton_limpiar.setText("Limpiar filtros")
        layout.addWidget(self.buscador)

        # ── Tabla ─────────────────────────────────────────────────────
        self.tabla = QTableWidget(self)
        self.tabla.setMinimumHeight(180)
        self._configurar_tabla()
        layout.addWidget(self.tabla)

        # ── Barra de acciones dedicada ────────────────────────────────
        self._barra_acciones = self._crear_barra_acciones()
        layout.addWidget(self._barra_acciones)

        # Cargar laboratorios para el combo del buscador
        try:
            laboratorios = incidencia_service.obtener_laboratorios()
            self.buscador.cargar_laboratorios([
                (lab["id_laboratorio"], lab["nombre"]) for lab in laboratorios
            ])
        except Exception as err:
            print(f"[ListaTecnico] Error al cargar laboratorios: {err}")

    def _crear_barra_acciones(self) -> QFrame:
        """Crea la barra de acciones con un único botón contextual."""
        barra = QFrame(self)
        barra.setObjectName("barraAccionesTecnico")
        barra.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        barra.setStyleSheet(
            "QFrame#barraAccionesTecnico {"
            "  background-color: #F8FAFC;"
            "  border: 1px solid #E2E8F0;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "}"
        )

        fila = QHBoxLayout(barra)
        fila.setContentsMargins(8, 4, 8, 4)
        fila.setSpacing(10)

        self._label_accion = QLabel("Selecciona una incidencia de la tabla")
        self._label_accion.setStyleSheet("color: #64748B; font-size: 13px;")
        fila.addWidget(self._label_accion)
        fila.addStretch()

        self._btn_accion = QPushButton("Tomar incidencia")
        self._btn_accion.setObjectName("botonAccionPrincipal")
        self._btn_accion.setFixedHeight(36)
        self._btn_accion.setEnabled(False)
        self._btn_accion.setVisible(True)
        fila.addWidget(self._btn_accion)

        self._btn_reasignar = QPushButton("Reasignar técnico")
        self._btn_reasignar.setObjectName("botonReasignarReporte")
        self._btn_reasignar.setFixedHeight(36)
        self._btn_reasignar.setEnabled(False)
        self._btn_reasignar.setVisible(False)
        fila.addWidget(self._btn_reasignar)

        return barra

    def _configurar_tabla(self):
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setShowGrid(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(44)
        self.tabla.horizontalHeader().setHighlightSections(False)

    # ------------------------------------------------------------------
    # Señales
    # ------------------------------------------------------------------

    def _conectar_senales(self):
        self.buscador.filtros_cambiados.connect(self._filtrar_incidencias)
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self._btn_accion.clicked.connect(self._ejecutar_accion)
        self._btn_reasignar.clicked.connect(self._abrir_dialogo_reasignar)

    # ------------------------------------------------------------------
    # Carga y filtrado
    # ------------------------------------------------------------------

    def cargar_datos(self):
        try:
            self._incidencias_todas = incidencia_service.obtener_incidencias_disponibles()
            self._error_carga = None
        except Exception as err:
            print(f"[ListaTecnico] Error al cargar incidencias: {err}")
            self._incidencias_todas = []
            self._error_carga = str(err)
        self._filtrar_incidencias(self.buscador.filtros_actuales())

    def _filtrar_incidencias(self, filtros: dict):
        visibles = [
            inc for inc in self._incidencias_todas
            if self._coincide_con_filtros(inc, filtros)
        ]
        self._poblar_tabla(visibles)

    @staticmethod
    def _coincide_con_filtros(incidencia: dict, filtros: dict) -> bool:
        texto = filtros["texto"].casefold()
        texto_inc = " ".join(
            str(incidencia.get(campo, ""))
            for campo in ("laboratorio", "descripcion")
        ).casefold()
        if texto and texto not in texto_inc:
            return False

        laboratorio = filtros["laboratorio"]
        if laboratorio and incidencia.get("id_laboratorio") != laboratorio:
            return False

        estado = filtros["estado"]
        estados_equivalentes = {
            "Pendiente":     {"Pendiente"},
            "Confirmado":    {"Confirmado"},
            "En reparación": {"En reparación", "En reparacion", "En proceso"},
            "Resuelto":      {"Resuelto"},
            "Reabierto":     {"Reabierto"},
        }
        if estado and incidencia.get("estado") not in estados_equivalentes.get(estado, {estado}):
            return False

        return True

    # ------------------------------------------------------------------
    # Población de la tabla
    # ------------------------------------------------------------------

    def _poblar_tabla(self, incidencias: list[dict]):
        columnas = ["Laboratorio", "Tipo de problema", "Prioridad", "Estado", "Técnico asignado"]
        self.tabla.setColumnCount(len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)
        self.tabla.setRowCount(0)

        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self._incidencias_visibles = incidencias

        if not incidencias:
            self.tabla.setRowCount(1)
            mensaje = (
                f"No se pudieron cargar las incidencias: {self._error_carga}"
                if self._error_carga
                else "No hay incidencias que coincidan con los filtros."
            )
            celda = QTableWidgetItem(mensaje)
            celda.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tabla.setItem(0, 0, celda)
            self.tabla.setSpan(0, 0, 1, len(columnas))
            self._actualizar_botones(None)
            return

        for fila, inc in enumerate(incidencias):
            self.tabla.insertRow(fila)
            # Columna 0 — lleva los datos completos en UserRole
            item_lab = QTableWidgetItem(str(inc.get("laboratorio", "-")))
            item_lab.setData(Qt.ItemDataRole.UserRole, inc)
            self.tabla.setItem(fila, 0, item_lab)
            self.tabla.setItem(fila, 1, QTableWidgetItem(str(inc.get("tipo_problema", "-"))))
            self.tabla.setItem(fila, 2, QTableWidgetItem(str(inc.get("prioridad", "-"))))

            # Columna 3 — badge de estado con color via aplicar_estado_visual
            estado = str(inc.get("estado", "-"))
            label_estado = QLabel(estado)
            label_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
            aplicar_estado_visual(label_estado, estado)
            self.tabla.setCellWidget(fila, 3, label_estado)

            tecnico = inc.get("tecnico_nombre") or "Sin asignar"
            self.tabla.setItem(fila, 4, QTableWidgetItem(tecnico))

        self._actualizar_botones(self._incidencia_seleccionada())

    # ------------------------------------------------------------------
    # Selección y lógica de botones
    # ------------------------------------------------------------------

    def _incidencia_seleccionada(self) -> dict | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        datos = item.data(Qt.ItemDataRole.UserRole) if item else None
        return datos if isinstance(datos, dict) else None

    def _on_seleccion_cambiada(self):
        self._actualizar_botones(self._incidencia_seleccionada())

    def _actualizar_botones(self, incidencia: dict | None):
        """Decide texto, visibilidad y habilitación del botón contextual.

        Tabla de decisión
        -----------------
        Sin selección                       → "Tomar incidencia" deshabilitado
        Pendiente + sin asignar             → "Tomar incidencia" habilitado
        Confirmado + asignado a mí          → "Iniciar reparación" habilitado
        En reparación + asignado a mí       → "Marcar como resuelto" habilitado
        Cualquier otro caso                 → botón oculto
        """
        if not incidencia:
            self._label_accion.setText("Selecciona una incidencia de la tabla")
            self._btn_accion.setText("Tomar incidencia")
            self._btn_accion.setEnabled(False)
            self._btn_accion.setVisible(True)
            self._btn_accion.setProperty("accion_interna", "")
            self._btn_reasignar.setVisible(False)
            self._btn_reasignar.setEnabled(False)
            self._refrescar_estilo_boton()
            return

        self._btn_reasignar.setVisible(False)
        self._btn_reasignar.setEnabled(False)

        estado = incidencia.get("estado", "")
        carnet_asignado = incidencia.get("carnet_tecnico") or None
        sin_asignar = carnet_asignado is None
        es_mia = carnet_asignado == self.carnet_tecnico

        texto: str | None = None
        accion: str = ""

        if estado in ("Pendiente", "Reabierto") and sin_asignar:
            texto = "Tomar incidencia"
            accion = "tomar"
        elif es_mia and estado == "Confirmado":
            texto = "Iniciar reparación"
            accion = "iniciar_reparacion"
        elif es_mia and estado in ("En reparación", "En reparacion", "En proceso"):
            texto = "Marcar como resuelto"
            accion = "marcar_resuelta"

        if texto is not None:
            self._label_accion.setText(
                f"Incidencia #{incidencia.get('id_reporte')} — {estado}"
            )
            self._btn_accion.setText(texto)
            self._btn_accion.setEnabled(True)
            self._btn_accion.setVisible(True)
        else:
            if carnet_asignado and not es_mia:
                tec_asignado = incidencia.get("tecnico_nombre") or incidencia.get("tecnico") or carnet_asignado
                info = f"Esta incidencia está tomada por {tec_asignado}"
            elif estado in ("Resuelto", "Reabierto") and carnet_asignado:
                tec_asignado = incidencia.get("tecnico_nombre") or incidencia.get("tecnico") or carnet_asignado
                info = f"Estado '{estado}' (atendido por {tec_asignado})"
            elif estado in ("Resuelto", "Reabierto"):
                info = f"Estado '{estado}': sin acción disponible en esta cola"
            else:
                info = "Sin acción disponible para esta incidencia"
            self._label_accion.setText(info)
            self._btn_accion.setVisible(False)
            accion = ""

        self._btn_accion.setProperty("accion_interna", accion)
        self._refrescar_estilo_boton()

    def _refrescar_estilo_boton(self):
        """Fuerza el repintado QSS tras cambiar propiedades dinámicas."""
        self._btn_accion.style().unpolish(self._btn_accion)
        self._btn_accion.style().polish(self._btn_accion)

    # ------------------------------------------------------------------
    # Ejecución de acciones
    # ------------------------------------------------------------------

    def _ejecutar_accion(self):
        if str(self.carnet_tecnico).upper().startswith("ADM"):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return

        accion = self._btn_accion.property("accion_interna")
        incidencia = self._incidencia_seleccionada()
        if not incidencia or not accion:
            return

        if accion == "tomar":
            self._accion_tomar(incidencia)
        elif accion == "iniciar_reparacion":
            self._accion_iniciar_reparacion(incidencia)
        elif accion == "marcar_resuelta":
            self._mostrar_overlay_cierre(incidencia)

    def _abrir_dialogo_reasignar(self):
        if str(self.carnet_tecnico).upper().startswith("ADM"):
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return

        incidencia = self._incidencia_seleccionada()
        if not incidencia:
            return

        widget = DialogoReasignarWidget(incidencia, self)
        widget.cancelado.connect(self._cerrar_modal_reasignar)
        widget.confirmado.connect(
            lambda nuevo_carnet: self._ejecutar_reasignacion(incidencia, nuevo_carnet)
        )
        self._modal_reasignar = ModalOverlay(widget, self, tamano=(480, 310))
        self._modal_reasignar.mostrar()

    def _cerrar_modal_reasignar(self):
        if getattr(self, "_modal_reasignar", None):
            self._modal_reasignar.cerrar()
            self._modal_reasignar = None

    def _ejecutar_reasignacion(self, incidencia: dict, nuevo_carnet: str):
        id_reporte = incidencia.get("id_reporte")
        if not id_reporte:
            return

        resultado = incidencia_service.reasignar_incidencia(id_reporte, nuevo_carnet)
        if resultado.get("exito"):
            self._cerrar_modal_reasignar()
            nombre_tec = resultado.get("tecnico_nombre", nuevo_carnet)
            QMessageBox.information(
                self,
                "Incidencia Reasignada",
                resultado.get("mensaje", f"Incidencia reasignada exitosamente a {nombre_tec}."),
            )
            nuevo_estado = "Confirmado" if incidencia.get("estado") == "Pendiente" else incidencia.get("estado")
            self._actualizar_fila_estado(id_reporte, nuevo_estado, nuevo_carnet)
            for lista in (self._incidencias_visibles, self._incidencias_todas):
                for inc in lista:
                    if inc.get("id_reporte") == id_reporte:
                        inc["tecnico_nombre"] = nombre_tec
                        inc["tecnico"] = nombre_tec
                        break
            for fila in range(self.tabla.rowCount()):
                item = self.tabla.item(fila, 0)
                if item:
                    datos = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(datos, dict) and datos.get("id_reporte") == id_reporte:
                        datos["tecnico_nombre"] = nombre_tec
                        datos["tecnico"] = nombre_tec
                        self.tabla.setItem(fila, 4, QTableWidgetItem(nombre_tec))
                        break
            self.incidencia_actualizada.emit(id_reporte)
        else:
            QMessageBox.critical(
                self,
                "Error al Reasignar",
                resultado.get("mensaje", "No se pudo reasignar la incidencia."),
            )

    def _accion_tomar(self, incidencia: dict):
        """Tomar incidencia: atómico, maneja carrera entre técnicos."""
        resultado = incidencia_service.tomar_incidencia(
            incidencia["id_reporte"], self.carnet_tecnico
        )
        if not resultado.get("exito"):
            if resultado.get("motivo") == "carrera":
                QMessageBox.warning(
                    self,
                    "Incidencia no disponible",
                    "Esta incidencia ya fue tomada por otro técnico.\n"
                    "La lista se actualizará ahora.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "No se pudo tomar la incidencia",
                    resultado.get("mensaje", "Inténtalo de nuevo."),
                )
            self.cargar_datos()
            self.tabla.clearSelection()
            return

        id_reporte = incidencia["id_reporte"]
        self._actualizar_fila_estado(id_reporte, "Confirmado", self.carnet_tecnico)
        self.incidencia_actualizada.emit(id_reporte)

    def _accion_iniciar_reparacion(self, incidencia: dict):
        resultado = incidencia_service.iniciar_reparacion(
            incidencia["id_reporte"], self.carnet_tecnico
        )
        if not resultado.get("exito"):
            QMessageBox.warning(
                self,
                "No se pudo iniciar la reparación",
                resultado.get("mensaje", "Inténtalo de nuevo."),
            )
            self.cargar_datos()
            return

        id_reporte = incidencia["id_reporte"]
        self._actualizar_fila_estado(id_reporte, "En reparación", self.carnet_tecnico)
        self.incidencia_actualizada.emit(id_reporte)

    def _mostrar_overlay_cierre(self, incidencia: dict):
        """Muestra overlay de reporte de cierre (no QDialog)."""
        if self._overlay_cierre is None:
            self._overlay_cierre = _OverlayReporteCierre(self)

        # Desconectar señales previas para evitar doble-disparo
        try:
            self._overlay_cierre.confirmado.disconnect()
        except RuntimeError:
            pass
        try:
            self._overlay_cierre.cancelado.disconnect()
        except RuntimeError:
            pass

        self._overlay_cierre.confirmado.connect(
            lambda texto: self._accion_marcar_resuelta(incidencia, texto)
        )
        self._overlay_cierre.cancelado.connect(self._overlay_cierre.cerrar)
        self._overlay_cierre.mostrar()

    def _accion_marcar_resuelta(self, incidencia: dict, reporte_cierre: str):
        if self._overlay_cierre:
            self._overlay_cierre.cerrar()

        resultado = incidencia_service.marcar_resuelta(
            incidencia["id_reporte"], self.carnet_tecnico, reporte_cierre
        )
        if not resultado.get("exito"):
            QMessageBox.warning(
                self,
                "No se pudo marcar como resuelta",
                resultado.get("mensaje", "Inténtalo de nuevo."),
            )
            self.cargar_datos()
            return

        id_reporte = incidencia["id_reporte"]
        self._actualizar_fila_estado(id_reporte, "Resuelto", self.carnet_tecnico)
        self.incidencia_actualizada.emit(id_reporte)

    # ------------------------------------------------------------------
    # Actualización de fila sin recargar toda la vista
    # ------------------------------------------------------------------

    def _actualizar_fila_estado(
        self, id_reporte: int, nuevo_estado: str, carnet_tecnico: str
    ):
        """Actualiza en memoria y en la tabla la incidencia afectada.

        No recarga toda la lista: solo modifica el dict y el widget de celda,
        luego llama a _actualizar_botones para reflejar las nuevas acciones.
        """
        for lista in (self._incidencias_visibles, self._incidencias_todas):
            for inc in lista:
                if inc.get("id_reporte") == id_reporte:
                    inc["estado"] = nuevo_estado
                    inc["carnet_tecnico"] = carnet_tecnico
                    break

        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0)
            if not item:
                continue
            datos = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(datos, dict) or datos.get("id_reporte") != id_reporte:
                continue

            datos["estado"] = nuevo_estado
            datos["carnet_tecnico"] = carnet_tecnico

            label_estado = QLabel(nuevo_estado)
            label_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
            aplicar_estado_visual(label_estado, nuevo_estado)
            self.tabla.setCellWidget(fila, 3, label_estado)
            self.tabla.setItem(fila, 4, QTableWidgetItem(carnet_tecnico or "Sin asignar"))
            self.tabla.selectRow(fila)
            break

        self._actualizar_botones(self._incidencia_seleccionada())

    # ------------------------------------------------------------------
    # Redimensionar overlay al cambiar el tamaño del widget
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay_cierre and self._overlay_cierre.isVisible():
            self._overlay_cierre.setGeometry(self.rect())

