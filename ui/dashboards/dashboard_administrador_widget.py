import logging

from PySide6.QtCharts import QChart, QChartView, QPieSeries
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.modal_overlay import ModalOverlay
from ui.registrar_incidencia_form import RegistrarIncidenciaForm
from services import incidencia_service as estadisticas_service
from services import incidencia_service

logger = logging.getLogger(__name__)

COLORES_ESTADO = {
    "Pendiente": "#3B82F6",
    "Confirmado": "#16A34A",
    "En reparación": "#D4A017",
    "Resuelto": "#6B7280",
    "Reabierto": "#DC2626",
}
PALETA_RESPALDO = ["#DC2626", "#B91C1C", "#16A34A", "#D4A017", "#3B82F6", "#6B7280"]


class DashboardAdministradorWidget(QWidget):
    """Dashboard del rol Administrador.

    Objetivo: dar una vista de supervisión del sistema y accesos a las
    pantallas de administración, además de permitir registrar incidencias.

    Responsabilidad: solo presentación. Consulta datos al service layer,
    los muestra y emite señales; nunca navega ni toca la base de datos.

    Dependencias: incidencia_service (datos compartidos con los otros
    dashboards), estadisticas_service (métricas exclusivas del
    Administrador), RegistrarIncidenciaForm y ModalOverlay (mismo flujo
    de registro que el Maestro).

    Relación: MainWindow conecta sus señales de navegación al QStackedWidget.
    """

    cerrar_sesion = Signal()
    cambiar_modo_vista = Signal(str)
    incidencia_registrada = Signal(int)
    abrir_gestion_laboratorios = Signal()
    abrir_registro_usuarios = Signal()
    abrir_lista_incidencias = Signal()
    abrir_configuracion = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.usuario_correo = None
        self.usuario_carnet = None
        self._modal = None

        self._construir_interfaz()
        self._timer_actualizacion = QTimer(self)
        self._timer_actualizacion.setInterval(15000)
        self._timer_actualizacion.timeout.connect(self.cargar_datos)

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
        """Establece el usuario activo autenticado y recarga los datos."""
        self.usuario_correo = correo
        self.usuario_carnet = carnet
        self.cargar_datos()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _construir_interfaz(self):
        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setObjectName("dashboardScroll")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.contenido = QWidget()
        self.contenido.setObjectName("dashboardContenidoAdmin")
        layout = QVBoxLayout(self.contenido)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(self._crear_barra_superior())
        layout.addWidget(self._crear_accesos_administracion())
        layout.addLayout(self._crear_fila_metricas())
        layout.addLayout(self._crear_fila_analisis())
        layout.addLayout(self._crear_fila_actividad())
        layout.addStretch()

        scroll_area.setWidget(self.contenido)
        layout_raiz.addWidget(scroll_area)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.contenido.setAttribute(Qt.WA_StyledBackground, True)

    def _crear_tarjeta(self, nombre_objeto: str, titulo: str) -> tuple[QFrame, QVBoxLayout]:
        """Crea un QFrame con título; la base de todos los bloques del dashboard."""
        frame = QFrame()
        frame.setObjectName(nombre_objeto)
        frame.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("tituloSeccion")
        layout.addWidget(etiqueta_titulo)
        return frame, layout

    def _crear_tarjeta_metrica(
        self, nombre_frame: str, titulo: str, nombre_valor: str
    ) -> tuple[QFrame, QLabel]:
        frame, layout = self._crear_tarjeta(nombre_frame, titulo)
        frame.setMinimumHeight(95)

        etiqueta_valor = QLabel("-")
        etiqueta_valor.setObjectName(nombre_valor)
        etiqueta_valor.setWordWrap(True)
        layout.addWidget(etiqueta_valor)
        layout.addStretch()
        return frame, etiqueta_valor

    def _crear_barra_superior(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("barra_superior")
        barra.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        titulo = QLabel("Panel de Administrador")
        titulo.setObjectName("titulo_dashboard")

        self.boton_actualizar = QPushButton("Actualizar")
        self.boton_actualizar.setObjectName("botonRegistrarIncidencia")
        self.boton_actualizar.clicked.connect(self.cargar_datos)

        self.boton_registrar_incidencia = QPushButton("Registrar Incidencia")
        self.boton_registrar_incidencia.setObjectName("botonRegistrarIncidencia")
        self.boton_registrar_incidencia.clicked.connect(self._abrir_formulario_registrar)

        self.boton_cerrar_sesion = QPushButton("Cerrar sesión")
        self.boton_cerrar_sesion.setObjectName("boton_cerrar_sesion")
        self.boton_cerrar_sesion.clicked.connect(self.cerrar_sesion.emit)

        self.selector_modo_vista = QComboBox()
        self.selector_modo_vista.setObjectName("selectorModoVistaAdmin")
        self.selector_modo_vista.addItems(["Modo de vista", "Maestro", "Técnico"])
        self.selector_modo_vista.setCurrentIndex(0)
        self.selector_modo_vista.setToolTip("Cambiar a la vista de otro rol")
        self.selector_modo_vista.currentTextChanged.connect(self._on_modo_vista_cambiado)

        layout.addWidget(titulo)
        layout.addStretch()
        layout.addWidget(self.selector_modo_vista)
        layout.addWidget(self.boton_actualizar)
        layout.addWidget(self.boton_registrar_incidencia)
        layout.addWidget(self.boton_cerrar_sesion)
        return barra

    def _on_modo_vista_cambiado(self, texto: str):
        if texto in ("Maestro", "Técnico"):
            self.selector_modo_vista.blockSignals(True)
            self.selector_modo_vista.setCurrentIndex(0)
            self.selector_modo_vista.blockSignals(False)
            self.cambiar_modo_vista.emit(texto)

    def _crear_accesos_administracion(self) -> QWidget:
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        accesos = (
            ("Laboratorios y equipos", self.abrir_gestion_laboratorios),
            ("Docentes y técnicos", self.abrir_registro_usuarios),
            ("Lista de incidencias", self.abrir_lista_incidencias),
            ("Configuración", self.abrir_configuracion),
        )
        for texto, senal in accesos:
            boton = QPushButton(texto)
            boton.setObjectName("botonAccesoAdmin")
            boton.clicked.connect(senal.emit)
            layout.addWidget(boton)
        layout.addStretch()
        return contenedor

    def _crear_fila_metricas(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(16)

        self.frame_resumen_laboratorios, self.label_valor_laboratorios = self._crear_tarjeta_metrica(
            "frame_resumen_laboratorios", "Laboratorios con incidencias", "label_valor_laboratorios"
        )
        self.frame_resumen_equipos, self.label_valor_equipos = self._crear_tarjeta_metrica(
            "frame_resumen_equipos", "Equipos mencionados en reportes", "label_valor_equipos"
        )
        self.frame_resueltas_mes, self.label_valor_resueltas_mes = self._crear_tarjeta_metrica(
            "frame_resueltas_mes", "Incidencias resueltas este mes", "label_valor_resueltas_mes"
        )
        self.frame_dificultades, self.label_valor_dificultades = self._crear_tarjeta_metrica(
            "frame_dificultades", "Dificultades encontradas", "label_valor_dificultades"
        )

        for tarjeta in (
            self.frame_resumen_laboratorios,
            self.frame_resumen_equipos,
            self.frame_resueltas_mes,
            self.frame_dificultades,
        ):
            fila.addWidget(tarjeta, 1)
        return fila

    def _crear_fila_analisis(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(16)
        fila.addWidget(self._crear_tarjeta_tipos_problema(), 1)
        fila.addWidget(self._crear_tarjeta_distribucion_mensual(), 1)
        return fila

    def _crear_tarjeta_tipos_problema(self) -> QFrame:
        frame, layout = self._crear_tarjeta("frame_tipos_problema", "Tipos de problemas reportados")

        tabla = QTableWidget(0, 2)
        tabla.setObjectName("tabla_tipos_problema")
        tabla.setHorizontalHeaderLabels(["Tipo de problema", "Cantidad"])
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        tabla.setShowGrid(False)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setVisible(False)
        tabla.verticalHeader().setDefaultSectionSize(40)
        tabla.horizontalHeader().setHighlightSections(False)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tabla.setMinimumHeight(250)

        self.tabla_tipos_problema = tabla
        layout.addWidget(tabla)
        return frame

    def _crear_tarjeta_distribucion_mensual(self) -> QFrame:
        frame, layout = self._crear_tarjeta(
            "frame_distribucion_mensual", "Porcentaje de problemas este mes"
        )

        self.serie_pastel = QPieSeries()
        grafico = QChart()
        grafico.addSeries(self.serie_pastel)
        grafico.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        grafico.setBackgroundVisible(False)

        self.vista_grafico = QChartView(grafico)
        self.vista_grafico.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vista_grafico.setFrameShape(QFrame.Shape.NoFrame)
        self.vista_grafico.setMinimumHeight(250)

        self.label_sin_datos_grafico = QLabel("Aún no hay incidencias registradas este mes.")
        self.label_sin_datos_grafico.setObjectName("mensajeSinDatos")
        self.label_sin_datos_grafico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_sin_datos_grafico.setMinimumHeight(250)

        layout.addWidget(self.vista_grafico)
        layout.addWidget(self.label_sin_datos_grafico)
        return frame

    def _crear_fila_actividad(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(16)

        self.frame_ultimas_incidencias, layout_incidencias = self._crear_tarjeta(
            "frame_ultimas_incidencias", "Últimas incidencias"
        )
        self.lista_ultimas_incidencias = QListWidget()
        self.lista_ultimas_incidencias.setObjectName("lista_ultimas_incidencias")
        self.lista_ultimas_incidencias.setMinimumHeight(150)
        layout_incidencias.addWidget(self.lista_ultimas_incidencias)

        self.frame_ultimos_reportes, layout_reportes = self._crear_tarjeta(
            "frame_ultimos_reportes", "Últimos reportes"
        )
        self.lista_ultimos_reportes = QListWidget()
        self.lista_ultimos_reportes.setObjectName("lista_ultimos_reportes")
        self.lista_ultimos_reportes.setMinimumHeight(150)
        layout_reportes.addWidget(self.lista_ultimos_reportes)

        fila.addWidget(self.frame_ultimas_incidencias, 1)
        fila.addWidget(self.frame_ultimos_reportes, 1)
        return fila

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos(self):
        """Recarga todos los bloques del dashboard con datos frescos de la BD."""
        stats = self._consultar(
            incidencia_service.obtener_resumen_estadisticas,
            {
                "laboratorios_con_incidencias": 0,
                "laboratorios_total": 0,
                "equipos_identificados": 0,
                "equipos_con_incidencias": 0,
            },
        )
        self._cargar_resumen_laboratorios(stats)
        self._cargar_resumen_equipos(stats)
        self._cargar_resueltas_mes()
        self._cargar_dificultades()
        self._cargar_tipos_problema()
        self._cargar_distribucion_mensual()
        self._cargar_ultimas_incidencias()
        self._cargar_ultimos_reportes()

    @staticmethod
    def _consultar(funcion, valor_por_defecto, *args, **kwargs):
        """Ejecuta una consulta del service layer; si falla, devuelve un valor vacío
        para que el dashboard siga usable en lugar de cerrarse."""
        try:
            return funcion(*args, **kwargs)
        except Exception:
            logger.exception("Error al ejecutar %s", getattr(funcion, "__name__", funcion))
            return valor_por_defecto

    @staticmethod
    def _poblar_lista(lista: QListWidget, lineas: list[str], mensaje_vacio: str):
        lista.clear()
        lista.addItems(lineas or [mensaje_vacio])

    def _cargar_resumen_laboratorios(self, stats: dict):
        afectados = stats.get("laboratorios_con_incidencias", 0)
        total = stats.get("laboratorios_total", 0)
        self.label_valor_laboratorios.setText(f"{afectados} con incidencias / {total} registrados")

    def _cargar_resumen_equipos(self, stats: dict):
        total = stats.get("equipos_identificados", 0)
        afectados = stats.get("equipos_con_incidencias", 0)
        self.label_valor_equipos.setText(
            f"{afectados} con incidencias / {total} identificados"
        )

    def _cargar_resueltas_mes(self):
        total = self._consultar(estadisticas_service.contar_resueltas_mes, 0)
        self.label_valor_resueltas_mes.setText(str(total))

    def _cargar_dificultades(self):
        dificultades = self._consultar(
            estadisticas_service.obtener_dificultades, {"vencidas": 0, "reabiertas": 0}
        )
        self.label_valor_dificultades.setText(
            f"{dificultades.get('vencidas', 0)} vencidas / "
            f"{dificultades.get('reabiertas', 0)} reabiertas"
        )

    def _cargar_tipos_problema(self):
        tipos = self._consultar(estadisticas_service.obtener_tipos_problema, [], limite=5)
        tabla = self.tabla_tipos_problema
        tabla.setRowCount(0)
        for fila, tipo in enumerate(tipos):
            tabla.insertRow(fila)
            item_tipo = QTableWidgetItem(str(tipo.get("tipo", "-")))
            item_cantidad = QTableWidgetItem(str(tipo.get("cantidad", 0)))
            item_cantidad.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tabla.setItem(fila, 0, item_tipo)
            tabla.setItem(fila, 1, item_cantidad)

    def _cargar_distribucion_mensual(self):
        datos = self._consultar(estadisticas_service.obtener_distribucion_mensual, [])
        datos = [dato for dato in datos if dato.get("cantidad", 0) > 0]
        total = sum(dato["cantidad"] for dato in datos)

        self.serie_pastel.clear()
        for indice, dato in enumerate(datos):
            porcentaje = dato["cantidad"] * 100 / total
            rebanada = self.serie_pastel.append(
                f"{dato['etiqueta']} ({porcentaje:.0f}%)", dato["cantidad"]
            )
            rebanada.setBrush(QColor(self._color_para(dato["etiqueta"], indice)))
            rebanada.setLabelVisible(False)

        self.vista_grafico.setVisible(total > 0)
        self.label_sin_datos_grafico.setVisible(total == 0)

    @staticmethod
    def _color_para(etiqueta: str, indice: int) -> str:
        return COLORES_ESTADO.get(etiqueta, PALETA_RESPALDO[indice % len(PALETA_RESPALDO)])

    def _cargar_ultimas_incidencias(self):
        incidencias = self._consultar(incidencia_service.obtener_ultimas_incidencias, [], limite=5)
        self._poblar_lista(
            self.lista_ultimas_incidencias,
            [self._formatear_incidencia(incidencia) for incidencia in incidencias],
            "No hay incidencias recientes.",
        )

    @staticmethod
    def _formatear_incidencia(incidencia: dict) -> str:
        return (
            f"#{incidencia.get('id_reporte', '-')} · {incidencia.get('laboratorio', '-')} · "
            f"{incidencia.get('equipo', '-')} · {incidencia.get('estado', '-')} · "
            f"{str(incidencia.get('fecha', '-'))[:10]}"
        )

    def _cargar_ultimos_reportes(self):
        reportes = self._consultar(incidencia_service.obtener_ultimos_reportes_cierre, [], limite=5)
        self._poblar_lista(
            self.lista_ultimos_reportes, reportes, "No hay reportes de cierre recientes."
        )

    # ------------------------------------------------------------------
    # Registro de incidencias (el Administrador también puede reportar)
    # ------------------------------------------------------------------
    def _abrir_formulario_registrar(self):
        formulario = RegistrarIncidenciaForm()
        formulario.guardar_solicitado.connect(self._on_incidencia_guardada)
        formulario.cancelar_solicitado.connect(self._cerrar_modal)

        self._modal = ModalOverlay(formulario, self)
        self._modal.mostrar()

    def _on_incidencia_guardada(self, datos: dict):
        resultado = incidencia_service.registrar_incidencia(self.usuario_correo, datos)
        if resultado.get("exito"):
            self._cerrar_modal()
            self.cargar_datos()
            self.incidencia_registrada.emit(resultado.get("id_reporte") or 0)
            QMessageBox.information(
                self,
                "Incidencia Guardada",
                "La incidencia ha sido registrada exitosamente.",
            )
        else:
            QMessageBox.critical(
                self,
                "Error al Guardar",
                resultado.get("mensaje", "No se pudo guardar la incidencia en la base de datos."),
            )

    def _cerrar_modal(self):
        if self._modal:
            self._modal.cerrar()
            self._modal = None
