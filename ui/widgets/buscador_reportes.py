"""Controles de búsqueda y filtrado para los reportes del Maestro.

Este módulo solo recopila la interacción del usuario. No consulta la base de
datos ni importa la capa ``services``; el contenedor decide cómo aplicar los
filtros recibidos mediante ``filtros_cambiados``.
"""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker, Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


ESTADOS_REPORTE = (
    ("Todos", None, "chipTodos"),
    ("Pendiente", "Pendiente", "chipPendiente"),
    ("Confirmado", "Confirmado", "chipConfirmado"),
    ("En reparación", "En reparación", "chipEnReparacion"),
    ("Resuelto", "Resuelto", "chipResuelto"),
    ("Reabierto", "Reabierto", "chipReabierto"),
)

# Representa una fecha sin filtro y permite que QDateEdit muestre su texto
# especial en lugar de una fecha inventada.
FECHA_SIN_FILTRO = QDate(1900, 1, 1)
RUTA_ICONO_LUPA = Path(__file__).resolve().parents[2] / "resources" / "icons" / "lupa.svg"


class BuscadorReportesWidget(QWidget):
    """Emite filtros para la tabla "Mis reportes" sin conocer su origen de datos."""

    filtros_cambiados = Signal(dict)
    accion_editar = Signal()
    accion_reasignar = Signal()
    accion_eliminar = Signal()
    accion_exportar_pdf = Signal()
    accion_exportar_todo_pdf = Signal()
    accion_exportar_todo_excel = Signal()
    accion_exportar_todo_pdf_api = Signal()
    accion_exportar_todo_excel_api = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("buscadorReportesWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._ajustando_fechas = False

        self._construir_ui()
        self._conectar_senales()

    def _construir_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 18, 20, 18)
        layout_principal.setSpacing(14)

        self.label_titulo = QLabel("Buscar y filtrar mis reportes")
        self.label_titulo.setObjectName("tituloBuscadorReportes")
        layout_principal.addWidget(self.label_titulo)

        self.input_buscar = QLineEdit()
        self.input_buscar.setObjectName("inputBuscarReportes")
        self.input_buscar.setPlaceholderText(
            "Buscar por laboratorio, equipo o descripción..."
        )
        accion_lupa = QAction(
            QIcon(str(RUTA_ICONO_LUPA)),
            "Buscar",
            self.input_buscar,
        )
        self.input_buscar.addAction(accion_lupa, QLineEdit.ActionPosition.LeadingPosition)
        layout_principal.addWidget(self.input_buscar)

        etiqueta_estados = QLabel("Filtrar por estado")
        etiqueta_estados.setObjectName("etiquetaFiltrosReportes")
        layout_principal.addWidget(etiqueta_estados)

        layout_chips = QHBoxLayout()
        layout_chips.setSpacing(8)
        self.grupo_estados = QButtonGroup(self)
        self.grupo_estados.setExclusive(True)
        self.chips_estado = {}
        for texto, estado, object_name in ESTADOS_REPORTE:
            chip = QPushButton(texto)
            chip.setObjectName(object_name)
            chip.setCheckable(True)
            chip.setProperty("estado", estado)
            self.grupo_estados.addButton(chip)
            self.chips_estado[estado] = chip
            layout_chips.addWidget(chip)
        self.chips_estado[None].setChecked(True)
        layout_chips.addStretch()

        # Botones de acción (se activan al seleccionar una fila)
        self.boton_editar = QPushButton("Editar")
        self.boton_editar.setObjectName("botonEditarReporte")
        self.boton_editar.setEnabled(False)
        self.boton_editar.setFixedHeight(34)
        layout_chips.addWidget(self.boton_editar)

        self.boton_accion_estado = QPushButton()
        self.boton_accion_estado.setObjectName("botonAccionTecnico")
        self.boton_accion_estado.setEnabled(False)
        self.boton_accion_estado.setFixedHeight(34)
        self.boton_accion_estado.hide()
        layout_chips.addWidget(self.boton_accion_estado)

        self.boton_reasignar = QPushButton("Reasignar")
        self.boton_reasignar.setObjectName("botonReasignarReporte")
        self.boton_reasignar.setEnabled(False)
        self.boton_reasignar.setFixedHeight(34)
        self.boton_reasignar.hide()
        self.boton_reasignar.clicked.connect(self.accion_reasignar.emit)
        layout_chips.addWidget(self.boton_reasignar)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("botonEliminarReporte")
        self.boton_eliminar.setEnabled(False)
        self.boton_eliminar.setFixedHeight(34)
        layout_chips.addWidget(self.boton_eliminar)

        from PySide6.QtWidgets import QMenu
        self.boton_exportar_pdf = QPushButton("Exportar PDF/Excel  ▾")
        self.boton_exportar_pdf.setObjectName("botonExportarPdf")
        self.boton_exportar_pdf.setEnabled(False)
        self.boton_exportar_pdf.setFixedHeight(34)

        self._menu_exportar = QMenu(self)
        self._accion_exportar_uno = self._menu_exportar.addAction("Exportar seleccionado como PDF")
        self._accion_exportar_todo = self._menu_exportar.addAction("Exportar todo como PDF (local)")
        self._accion_exportar_excel = self._menu_exportar.addAction("Exportar todo como Excel (local)")
        self._menu_exportar.addSeparator()
        self._accion_exportar_pdf_api = self._menu_exportar.addAction("Exportar todo como PDF (Carbone API)")
        self._accion_exportar_excel_api = self._menu_exportar.addAction(
            "Exportar todo como PDF con plantilla Excel (Carbone API)"
        )
        self._accion_exportar_excel.setVisible(False)
        self._accion_exportar_pdf_api.setVisible(False)
        self._accion_exportar_excel_api.setVisible(False)
        self.boton_exportar_pdf.setMenu(self._menu_exportar)
        layout_chips.addWidget(self.boton_exportar_pdf)

        layout_principal.addLayout(layout_chips)

        layout_selectores = QHBoxLayout()
        layout_selectores.setSpacing(12)

        self.combo_laboratorio = QComboBox()
        self.combo_laboratorio.setObjectName("comboLaboratorioReportes")
        self.combo_laboratorio.addItem("Todos los laboratorios", None)
        layout_selectores.addLayout(
            self._crear_campo("Laboratorio", self.combo_laboratorio)
        )

        self.fecha_desde = self._crear_selector_fecha("fechaDesdeReportes")
        layout_selectores.addLayout(self._crear_campo("Fecha desde", self.fecha_desde))

        self.fecha_hasta = self._crear_selector_fecha("fechaHastaReportes")
        layout_selectores.addLayout(self._crear_campo("Fecha hasta", self.fecha_hasta))

        self.boton_limpiar = QPushButton("Limpiar filtros")
        self.boton_limpiar.setObjectName("botonLimpiarFiltrosReportes")
        layout_selectores.addWidget(self.boton_limpiar, 0, Qt.AlignmentFlag.AlignBottom)
        layout_principal.addLayout(layout_selectores)

    @staticmethod
    def _crear_campo(etiqueta: str, control: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(5)
        label = QLabel(etiqueta)
        label.setObjectName("etiquetaCampoReporte")
        layout.addWidget(label)
        layout.addWidget(control)
        return layout

    @staticmethod
    def _crear_selector_fecha(object_name: str) -> QDateEdit:
        selector = QDateEdit(calendarPopup=True)
        selector.setObjectName(object_name)
        selector.setDisplayFormat("dd/MM/yyyy")
        selector.setMinimumDate(FECHA_SIN_FILTRO)
        selector.setSpecialValueText("Sin fecha")
        selector.setDate(FECHA_SIN_FILTRO)
        return selector

    def _conectar_senales(self):
        self.input_buscar.textChanged.connect(self._emitir_filtros)
        self.combo_laboratorio.currentIndexChanged.connect(self._emitir_filtros)
        self.grupo_estados.buttonClicked.connect(self._on_chip_estado_clic)
        self.fecha_desde.dateChanged.connect(self._on_fecha_desde_cambiada)
        self.fecha_hasta.dateChanged.connect(self._on_fecha_hasta_cambiada)
        self.boton_limpiar.clicked.connect(self.limpiar_filtros)
        self.boton_editar.clicked.connect(self.accion_editar.emit)
        self.boton_eliminar.clicked.connect(self.accion_eliminar.emit)
        self._accion_exportar_uno.triggered.connect(self.accion_exportar_pdf.emit)
        self._accion_exportar_todo.triggered.connect(self.accion_exportar_todo_pdf.emit)
        self._accion_exportar_excel.triggered.connect(self.accion_exportar_todo_excel.emit)
        self._accion_exportar_pdf_api.triggered.connect(self.accion_exportar_todo_pdf_api.emit)
        self._accion_exportar_excel_api.triggered.connect(self.accion_exportar_todo_excel_api.emit)

    def mostrar_opciones_exportacion_administrador(self):
        """Muestra opciones Excel y API solo en la pantalla de administración."""
        self.boton_exportar_pdf.setText("Exportar PDF/Excel  ▾")
        self._accion_exportar_excel.setVisible(True)
        self._accion_exportar_pdf_api.setVisible(True)
        self._accion_exportar_excel_api.setVisible(True)

    def cargar_laboratorios(self, lista_laboratorios: list[tuple[str, str]]):
        """Carga el catálogo recibido como pares ``(id_laboratorio, nombre)``."""
        laboratorio_actual = self.combo_laboratorio.currentData()
        bloqueador = QSignalBlocker(self.combo_laboratorio)
        self.combo_laboratorio.clear()
        self.combo_laboratorio.addItem("Todos los laboratorios", None)
        for id_laboratorio, nombre in lista_laboratorios:
            self.combo_laboratorio.addItem(nombre, id_laboratorio)

        indice = self.combo_laboratorio.findData(laboratorio_actual)
        self.combo_laboratorio.setCurrentIndex(max(indice, 0))
        del bloqueador

    def set_titulo(self, nuevo_titulo: str):
        """Permite cambiar el texto de cabecera del buscador según el rol."""
        self.label_titulo.setText(nuevo_titulo)

    def seleccionar_estado(self, estado: str | None):
        """Activa programáticamente un chip de estado (ej: 'Pendiente')."""
        if estado in self.chips_estado:
            self.chips_estado[estado].setChecked(True)
            self._emitir_filtros()

    def filtros_actuales(self) -> dict:
        """Devuelve exactamente el contrato de filtros que consume el contenedor."""
        return {
            "texto": self.input_buscar.text().strip(),
            "laboratorio": self.combo_laboratorio.currentData(),
            "estado": self._estado_seleccionado(),
            "fecha_desde": self._fecha_o_none(self.fecha_desde.date()),
            "fecha_hasta": self._fecha_o_none(self.fecha_hasta.date()),
        }

    def limpiar_filtros(self):
        """Restaura el estado sin filtros y emite una única actualización."""
        controles = (
            self.input_buscar,
            self.combo_laboratorio,
            self.fecha_desde,
            self.fecha_hasta,
        )
        bloqueadores = [QSignalBlocker(control) for control in controles]
        self.input_buscar.clear()
        self.combo_laboratorio.setCurrentIndex(0)
        self.fecha_desde.setDate(FECHA_SIN_FILTRO)
        self.fecha_hasta.setDate(FECHA_SIN_FILTRO)
        self.chips_estado[None].setChecked(True)
        del bloqueadores
        self._emitir_filtros()

    def _on_chip_estado_clic(self, boton: QPushButton):
        # QButtonGroup exclusivo garantiza que "Todos" desactive los demás.
        if boton.isChecked():
            self._emitir_filtros()

    def _on_fecha_desde_cambiada(self, nueva_fecha: QDate):
        if self._ajustando_fechas:
            return
        self._corregir_rango("desde", nueva_fecha)
        self._emitir_filtros()

    def _on_fecha_hasta_cambiada(self, nueva_fecha: QDate):
        if self._ajustando_fechas:
            return
        self._corregir_rango("hasta", nueva_fecha)
        self._emitir_filtros()

    def _corregir_rango(self, origen: str, nueva_fecha: QDate):
        otra_fecha = self.fecha_hasta if origen == "desde" else self.fecha_desde
        if not self._tiene_fecha(nueva_fecha) or not self._tiene_fecha(otra_fecha.date()):
            return
        if (origen == "desde" and nueva_fecha > otra_fecha.date()) or (
            origen == "hasta" and nueva_fecha < otra_fecha.date()
        ):
            self._ajustando_fechas = True
            otra_fecha.setDate(nueva_fecha)
            self._ajustando_fechas = False

    def _estado_seleccionado(self) -> str | None:
        boton = self.grupo_estados.checkedButton()
        return boton.property("estado") if boton else None

    @staticmethod
    def _tiene_fecha(fecha: QDate) -> bool:
        return fecha > FECHA_SIN_FILTRO

    @classmethod
    def _fecha_o_none(cls, fecha: QDate) -> date | None:
        if not cls._tiene_fecha(fecha):
            return None
        return date(fecha.year(), fecha.month(), fecha.day())

    def _emitir_filtros(self, *_):
        self.filtros_cambiados.emit(self.filtros_actuales())

    def actualizar_seleccion(self, hay_seleccion: bool):
        """Habilita o deshabilita los botones de acción según si hay una fila seleccionada."""
        self.boton_editar.setEnabled(hay_seleccion)
        self.boton_reasignar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)
        # El botón PDF siempre está activo; la opción "seleccionado" se habilita por fila
        self.boton_exportar_pdf.setEnabled(True)
        self._accion_exportar_uno.setEnabled(hay_seleccion)
