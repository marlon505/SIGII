"""Widget para reasignar una incidencia a otro técnico registrado en el sistema."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFrame,
    QMessageBox,
)
from services import incidencia_service


class DialogoReasignarWidget(QWidget):
    """Permite seleccionar un técnico registrado para reasignarle la incidencia."""

    confirmado = Signal(str)  # Emite el carnet_tecnico del técnico seleccionado
    cancelado = Signal()

    def __init__(self, datos_incidencia: dict, parent: QWidget = None):
        super().__init__(parent)
        self._datos = datos_incidencia or {}
        self._construir_ui()
        self._cargar_tecnicos()

    def _construir_ui(self):
        self.setObjectName("dialogoReasignarWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#dialogoReasignarWidget {
                background-color: #FFFFFF;
                border-radius: 12px;
            }
            QLabel#tituloReasignar {
                font-size: 18px;
                font-weight: 700;
                color: #1E3A8A;
            }
            QFrame#tarjetaInfoIncidencia {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
            QComboBox#comboTecnicosRegistrados {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #FFFFFF;
                color: #1E293B;
            }
            QComboBox#comboTecnicosRegistrados:focus {
                border-color: #15803D;
            }
            QPushButton#btnConfirmarReasignar {
                background-color: #15803D;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                padding: 8px 18px;
                font-size: 13px;
            }
            QPushButton#btnConfirmarReasignar:hover {
                background-color: #166534;
            }
            QPushButton#btnCancelarReasignar {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton#btnCancelarReasignar:hover {
                background-color: #E2E8F0;
                color: #1E293B;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # 1. Cabecera
        id_rep = self._datos.get("id_reporte", "N/A")
        titulo = QLabel(f"Reasignar Incidencia #{id_rep}")
        titulo.setObjectName("tituloReasignar")
        layout.addWidget(titulo)

        # 2. Resumen de la incidencia
        lab = self._datos.get("laboratorio", "-")
        equipo = self._datos.get("equipo", "-")
        tipo = self._datos.get("tipo_problema", "-")
        tec_actual = (
            self._datos.get("tecnico_nombre")
            or self._datos.get("tecnico")
            or self._datos.get("carnet_tecnico")
            or "Sin asignar"
        )

        tarjeta_info = QFrame(self)
        tarjeta_info.setObjectName("tarjetaInfoIncidencia")
        layout_info = QVBoxLayout(tarjeta_info)
        layout_info.setContentsMargins(12, 10, 12, 10)
        layout_info.setSpacing(5)

        lbl_det = QLabel(f"<b>Ubicación:</b> {lab} ({equipo})  |  <b>Tipo:</b> {tipo}")
        lbl_det.setStyleSheet("color: #334155; font-size: 13px;")
        lbl_det.setWordWrap(True)
        layout_info.addWidget(lbl_det)

        lbl_tec_act = QLabel(f"<b>Técnico actual:</b> {tec_actual}")
        lbl_tec_act.setStyleSheet("color: #475569; font-size: 13px;")
        layout_info.addWidget(lbl_tec_act)

        layout.addWidget(tarjeta_info)

        # 3. Selección del nuevo técnico
        lbl_instruccion = QLabel("Selecciona el nuevo técnico asignado:")
        lbl_instruccion.setStyleSheet("font-weight: 600; color: #1E293B; font-size: 13px;")
        layout.addWidget(lbl_instruccion)

        self.combo_tecnicos = QComboBox(self)
        self.combo_tecnicos.setObjectName("comboTecnicosRegistrados")
        layout.addWidget(self.combo_tecnicos)

        layout.addStretch()

        # 4. Fila de botones
        fila_botones = QHBoxLayout()
        fila_botones.setSpacing(10)
        fila_botones.addStretch()

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btnCancelarReasignar")
        btn_cancelar.clicked.connect(self.cancelado.emit)
        fila_botones.addWidget(btn_cancelar)

        btn_confirmar = QPushButton("Reasignar incidencia")
        btn_confirmar.setObjectName("btnConfirmarReasignar")
        btn_confirmar.clicked.connect(self._on_confirmar)
        fila_botones.addWidget(btn_confirmar)

        layout.addLayout(fila_botones)

    def _cargar_tecnicos(self):
        self.combo_tecnicos.clear()
        try:
            tecnicos = incidencia_service.obtener_tecnicos()
        except Exception as err:
            print(f"[DialogoReasignar] Error al cargar técnicos: {err}")
            tecnicos = []

        if not tecnicos:
            self.combo_tecnicos.addItem("No hay técnicos registrados", None)
            return

        carnet_actual = self._datos.get("carnet_tecnico")
        indice_actual = -1

        for idx, tec in enumerate(tecnicos):
            carnet = tec.get("carnet_tecnico")
            nombre = tec.get("nombre_completo") or carnet
            texto_item = f"{nombre} ({carnet})"
            self.combo_tecnicos.addItem(texto_item, carnet)
            if carnet and carnet == carnet_actual:
                indice_actual = idx

        if indice_actual >= 0:
            self.combo_tecnicos.setCurrentIndex(indice_actual)

    def _on_confirmar(self):
        carnet_elegido = self.combo_tecnicos.currentData()
        if not carnet_elegido:
            QMessageBox.warning(
                self,
                "Selección requerida",
                "Por favor selecciona un técnico registrado de la lista.",
            )
            return

        carnet_actual = self._datos.get("carnet_tecnico")
        if carnet_elegido == carnet_actual:
            QMessageBox.information(
                self,
                "Mismo técnico",
                "La incidencia ya está asignada a este técnico. Selecciona a otro técnico para reasignarla.",
            )
            return

        self.confirmado.emit(carnet_elegido)
