"""
ui/lista_incidencias_widget.py

Responsabilidad:
    Mostrar el listado de incidencias con busqueda, filtros y acciones
    (Editar, Eliminar, Reabrir, Actualizar), respetando las reglas de
    habilitacion por estado definidas en plan_frontend_SIGII_actualizado.docx.

Dependencias:
    - styles.colors.Colors
    - styles.helpers.aplicar_estado_visual
    - Un servicio de incidencias (inyectado por constructor) que exponga:
        obtener_incidencias(filtros: dict) -> list[dict]
        eliminar_incidencia(id_reporte: int) -> bool
        reabrir_incidencia(id_reporte: int) -> bool
      Este servicio lo implementa la capa de backend (Indiana), no este
      widget. Este archivo NO debe contener SQL ni logica de negocio.

Relacion con otros modulos:
    - Emite senales que MainWindow conecta para decidir navegacion.
      Este widget NUNCA navega por si mismo (contrato establecido del
      proyecto: los widgets emiten, MainWindow decide destino).

ADVERTENCIA - contrato de estados pendiente de confirmar con el equipo:
    Este archivo usa los 5 estados de plan_frontend_SIGII_actualizado.docx:
    "Pendiente", "Confirmado", "En reparacion", "Resuelto", "Reabierto".

    El esquema actual en Protecto_integrador_2.sql define un ENUM distinto
    para la columna `estado` de la tabla `reporte`:
        ENUM('Pendiente','En proceso','Resuelto','Cancelado')

    Estos dos esquemas NO coinciden (ni en nombres ni en cantidad de
    estados). Antes de conectar este widget a datos reales, este
    desajuste debe resolverse con Marlon (dueño de la capa de BD) e
    Indiana (dueña de la logica de negocio), y el ENUM de MySQL debe
    actualizarse para reflejar los 5 estados documentados aqui.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QDateEdit, QLabel, QHeaderView,
    QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Signal, QDate, Qt

from resources.helpers import aplicar_estado_visual

# Estados en los que Editar/Eliminar siguen habilitados (Nota QA del documento)
ESTADOS_EDITABLE = {"Pendiente"}
ESTADO_REABRIBLE = "Resuelto"

COLUMNAS = ["ID", "Laboratorio", "Equipo", "Tipo de problema", "Prioridad", "Fecha", "Estado"]
COL_ID, COL_LAB, COL_EQUIPO, COL_TIPO, COL_PRIORIDAD, COL_FECHA, COL_ESTADO = range(len(COLUMNAS))


class ListaIncidenciasWidget(QWidget):
    """
    Widget de listado de incidencias para el rol Maestro.

    Nota: la vista de Tecnico usa un widget distinto (columna
    "Tecnico asignado" y boton "Tomar tarea" en vez de Editar/Eliminar),
    segun plan_frontend_SIGII_actualizado.docx. No reutilizar esta clase
    para esa pantalla sin adaptarla.
    """

    # --- Senales: este widget nunca decide navegacion, solo informa ---
    editar_solicitado = Signal(int)          # emite id_reporte
    incidencia_eliminada = Signal(int)       # emite id_reporte tras exito
    incidencia_reabierta = Signal(int)       # emite id_reporte tras exito
    volver_solicitado = Signal()             # si la pantalla tiene flecha de regreso

    def __init__(self, incidencia_service, parent=None):
        super().__init__(parent)
        self.setObjectName("listaIncidenciasWidget")
        self._service = incidencia_service
        self._incidencias_actuales: list[dict] = []

        self._construir_ui()
        self._conectar_senales()
        self.cargar_incidencias()

    # ------------------------------------------------------------------
    # Construccion de UI
    # ------------------------------------------------------------------
    def _construir_ui(self):
        layout_principal = QVBoxLayout(self)

        layout_principal.addLayout(self._construir_barra_filtros())

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.itemSelectionChanged.connect(self._actualizar_estado_botones)
        layout_principal.addWidget(self.tabla)

        layout_principal.addLayout(self._construir_barra_acciones())

        self.setLayout(layout_principal)

    def _construir_barra_filtros(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.input_buscar = QLineEdit()
        self.input_buscar.setPlaceholderText("Buscar...")
        self.input_buscar.setObjectName("inputBuscarIncidencia")

        self.combo_estado = QComboBox()
        self.combo_estado.addItems(
            ["Todos", "Pendiente", "Confirmado", "En reparacion", "Resuelto", "Reabierto"]
        )

        self.combo_laboratorio = QComboBox()
        self.combo_laboratorio.addItem("Todos")
        # TODO: poblar con self._service.obtener_laboratorios() cuando el
        # catalogo de laboratorios este disponible (pantalla del Administrador)

        self.combo_prioridad = QComboBox()
        self.combo_prioridad.addItems(["Todas", "Baja", "Media", "Alta", "Critica"])

        self.fecha_desde = QDateEdit(calendarPopup=True)
        self.fecha_desde.setDate(QDate.currentDate().addMonths(-1))

        self.fecha_hasta = QDateEdit(calendarPopup=True)
        self.fecha_hasta.setDate(QDate.currentDate())

        self.btn_filtrar = QPushButton("Filtrar")
        self.btn_filtrar.setObjectName("btnFiltrar")

        for widget in (
            QLabel("Estado:"), self.combo_estado,
            QLabel("Laboratorio:"), self.combo_laboratorio,
            QLabel("Prioridad:"), self.combo_prioridad,
            QLabel("Desde:"), self.fecha_desde,
            QLabel("Hasta:"), self.fecha_hasta,
        ):
            layout.addWidget(widget)

        layout.addWidget(self.input_buscar)
        layout.addWidget(self.btn_filtrar)
        return layout

    def _construir_barra_acciones(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setObjectName("btnEditarIncidencia")

        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setObjectName("btnEliminarIncidencia")

        self.btn_reabrir = QPushButton("Reabrir")
        self.btn_reabrir.setObjectName("btnReabrirIncidencia")

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnActualizarLista")

        for boton in (self.btn_editar, self.btn_eliminar, self.btn_reabrir, self.btn_actualizar):
            layout.addWidget(boton)

        self._actualizar_estado_botones()  # arrancan deshabilitados sin seleccion
        return layout

    def _conectar_senales(self):
        self.btn_filtrar.clicked.connect(self._on_filtrar)
        self.btn_actualizar.clicked.connect(self.cargar_incidencias)
        self.btn_editar.clicked.connect(self._on_editar)
        self.btn_eliminar.clicked.connect(self._on_eliminar)
        self.btn_reabrir.clicked.connect(self._on_reabrir)
        self.input_buscar.returnPressed.connect(self._on_filtrar)

    # ------------------------------------------------------------------
    # Carga y filtrado de datos
    # ------------------------------------------------------------------
    def cargar_incidencias(self):
        """Pide al servicio TODAS las incidencias (sin filtro) y repuebla la tabla."""
        self._aplicar_filtros_y_cargar(filtros={})

    def _on_filtrar(self):
        filtros = {
            "texto": self.input_buscar.text().strip(),
            "estado": self._valor_o_none(self.combo_estado),
            "laboratorio": self._valor_o_none(self.combo_laboratorio),
            "prioridad": self._valor_o_none(self.combo_prioridad),
            "fecha_desde": self.fecha_desde.date().toString("yyyy-MM-dd"),
            "fecha_hasta": self.fecha_hasta.date().toString("yyyy-MM-dd"),
        }
        self._aplicar_filtros_y_cargar(filtros)

    def _aplicar_filtros_y_cargar(self, filtros: dict):
        try:
            self._incidencias_actuales = self._service.obtener_incidencias(filtros)
        except Exception as error:
            QMessageBox.critical(
                self, "Error al cargar incidencias",
                f"No se pudo obtener el listado:\n{error}"
            )
            self._incidencias_actuales = []
        self._poblar_tabla(self._incidencias_actuales)

    @staticmethod
    def _valor_o_none(combo: QComboBox):
        texto = combo.currentText()
        return None if texto in ("Todos", "Todas") else texto

    # ------------------------------------------------------------------
    # Render de la tabla
    # ------------------------------------------------------------------
    def _poblar_tabla(self, incidencias: list[dict]):
        self.tabla.setRowCount(0)
        for incidencia in incidencias:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)

            self.tabla.setItem(fila, COL_ID, QTableWidgetItem(str(incidencia["id_reporte"])))
            self.tabla.setItem(fila, COL_LAB, QTableWidgetItem(incidencia["laboratorio"]))
            self.tabla.setItem(fila, COL_EQUIPO, QTableWidgetItem(incidencia["equipo"]))
            self.tabla.setItem(fila, COL_TIPO, QTableWidgetItem(incidencia["tipo_problema"]))
            self.tabla.setItem(fila, COL_PRIORIDAD, QTableWidgetItem(incidencia["prioridad"]))
            self.tabla.setItem(fila, COL_FECHA, QTableWidgetItem(str(incidencia["fecha"])))

            label_estado = QLabel(incidencia["estado"])
            label_estado.setAlignment(Qt.AlignCenter)
            aplicar_estado_visual(label_estado, incidencia["estado"])
            self.tabla.setCellWidget(fila, COL_ESTADO, label_estado)

        self._actualizar_estado_botones()

    # ------------------------------------------------------------------
    # Reglas de habilitacion de botones (contrato del documento)
    # ------------------------------------------------------------------
    def _fila_seleccionada(self) -> dict | None:
        fila = self.tabla.currentRow()
        if fila < 0 or fila >= len(self._incidencias_actuales):
            return None
        return self._incidencias_actuales[fila]

    def _actualizar_estado_botones(self):
        incidencia = self._fila_seleccionada()

        if incidencia is None:
            self.btn_editar.setEnabled(False)
            self.btn_eliminar.setEnabled(False)
            self.btn_reabrir.setEnabled(False)
            return

        es_editable = incidencia["estado"] in ESTADOS_EDITABLE
        es_reabrible = incidencia["estado"] == ESTADO_REABRIBLE

        self.btn_editar.setEnabled(es_editable)
        self.btn_eliminar.setEnabled(es_editable)
        self.btn_reabrir.setEnabled(es_reabrible)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _on_editar(self):
        incidencia = self._fila_seleccionada()
        if incidencia is None:
            return
        # Este widget NO decide que pantalla se abre; solo informa.
        self.editar_solicitado.emit(incidencia["id_reporte"])

    def _on_eliminar(self):
        incidencia = self._fila_seleccionada()
        if incidencia is None:
            return

        respuesta = QMessageBox.question(
            self, "Confirmar eliminacion",
            "Eliminar esta incidencia? Esta accion no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if respuesta != QMessageBox.Yes:
            return

        try:
            self._service.eliminar_incidencia(incidencia["id_reporte"])
        except Exception as error:
            QMessageBox.critical(self, "Error", f"No se pudo eliminar:\n{error}")
            return

        self.incidencia_eliminada.emit(incidencia["id_reporte"])
        self.cargar_incidencias()

    def _on_reabrir(self):
        incidencia = self._fila_seleccionada()
        if incidencia is None:
            return

        try:
            self._service.reabrir_incidencia(incidencia["id_reporte"])
        except Exception as error:
            QMessageBox.critical(self, "Error", f"No se pudo reabrir:\n{error}")
            return

        self.incidencia_reabierta.emit(incidencia["id_reporte"])
        self.cargar_incidencias()