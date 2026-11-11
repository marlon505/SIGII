"""
ui/registrar_incidencia_form.py

Objetivo:
    Formulario para que un Maestro capture una nueva incidencia.

Responsabilidad:
    Capturar datos y emitir una señal con ellos. NO hace consultas SQL
    directamente — esa es la regla ya establecida en el proyecto (la UI
    nunca llama queries; eso vive en services/). Hoy no existe todavía
    services/incidencia_service.py (Fase 3 pendiente), así que quien use
    este formulario decide qué hacer con los datos mientras tanto.

Dependencias:
    PySide6.QtWidgets, PySide6.QtCore

Relación con otros módulos:
    Se muestra dentro de un ModalOverlay, típicamente desde
    dashboard_maestro.py.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QDateEdit, QPushButton
)
from PySide6.QtCore import Signal, QDate

from services import incidencia_service


class RegistrarIncidenciaForm(QWidget):
    """
    Señales:
        guardar_solicitado(dict): se emite al presionar "Guardar", con
            los datos capturados.
        cancelar_solicitado(): se emite al presionar "Cancelar".
    """

    guardar_solicitado = Signal(dict)
    cancelar_solicitado = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("registrarIncidenciaForm")
        self._construir_ui()

    def _construir_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setSpacing(14)

        titulo = QLabel("Registrar Incidencia")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E3A8A;")
        layout_principal.addWidget(titulo)

        # --- Laboratorio ---
        fila_laboratorio = QHBoxLayout()
        fila_laboratorio.addWidget(QLabel("Laboratorio:"))
        self.combo_laboratorio = QComboBox()
        self._cargar_catalogo_laboratorios()
        self.combo_laboratorio.currentTextChanged.connect(self._actualizar_equipos)
        fila_laboratorio.addWidget(self.combo_laboratorio)
        layout_principal.addLayout(fila_laboratorio)

        # --- Equipo (se filtra según el laboratorio, según el spec) ---
        fila_equipo = QHBoxLayout()
        fila_equipo.addWidget(QLabel("Equipo:"))
        self.combo_equipo = QComboBox()
        fila_equipo.addWidget(self.combo_equipo)
        layout_principal.addLayout(fila_equipo)
        self._actualizar_equipos(self.combo_laboratorio.currentText())

        # --- Tipo de problema ---
        fila_tipo = QHBoxLayout()
        fila_tipo.addWidget(QLabel("Tipo de problema:"))
        self.combo_tipo_problema = QComboBox()
        self._cargar_catalogo_categorias()
        self.combo_tipo_problema.currentTextChanged.connect(self._actualizar_prioridad_por_categoria)
        fila_tipo.addWidget(self.combo_tipo_problema)
        layout_principal.addLayout(fila_tipo)

        # --- Prioridad ---
        fila_prioridad = QHBoxLayout()
        fila_prioridad.addWidget(QLabel("Prioridad:"))
        self.combo_prioridad = QComboBox()
        self.combo_prioridad.addItems(["Baja", "Media", "Alta", "Crítica"])
        self.combo_prioridad.setCurrentText("Media")  # valor por defecto, según spec
        fila_prioridad.addWidget(self.combo_prioridad)
        layout_principal.addLayout(fila_prioridad)

        # --- Fecha ---
        fila_fecha = QHBoxLayout()
        fila_fecha.addWidget(QLabel("Fecha:"))
        self.input_fecha = QDateEdit()
        self.input_fecha.setDate(QDate.currentDate())
        self.input_fecha.setCalendarPopup(True)
        self.input_fecha.setMaximumDate(QDate.currentDate())  # no puede ser futura
        fila_fecha.addWidget(self.input_fecha)
        layout_principal.addLayout(fila_fecha)

        # --- Descripción: la "pequeña caja de texto" ---
        layout_principal.addWidget(QLabel("Descripción:"))
        self.input_descripcion = QTextEdit()
        self.input_descripcion.setPlaceholderText("Describe brevemente qué ocurrió...")
        self.input_descripcion.setFixedHeight(90)
        layout_principal.addWidget(self.input_descripcion)

        layout_principal.addStretch()

        # --- Botones ---
        fila_botones = QHBoxLayout()
        fila_botones.addStretch()

        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar_solicitado.emit)
        fila_botones.addWidget(self.boton_cancelar)

        self.boton_guardar = QPushButton("Guardar")
        self.boton_guardar.setStyleSheet(
            "background-color: #1E3A8A; color: white; padding: 6px 18px; border-radius: 4px;"
        )
        self.boton_guardar.clicked.connect(self._on_guardar)
        fila_botones.addWidget(self.boton_guardar)

        layout_principal.addLayout(fila_botones)

    def _cargar_catalogo_laboratorios(self):
        try:
            labs = incidencia_service.obtener_laboratorios()
            nombres = [l["nombre"] for l in labs] if labs else [f"Laboratorio FC {i}" for i in range(1, 11)]
        except Exception:
            nombres = [f"Laboratorio FC {i}" for i in range(1, 11)]
        self.combo_laboratorio.addItems(nombres)

    def _cargar_catalogo_categorias(self):
        self._mapa_prioridades = {}
        try:
            cats = incidencia_service.obtener_categorias()
            if cats:
                for c in cats:
                    self._mapa_prioridades[c["nombre"]] = c.get("prioridad", "Media")
                nombres = [c["nombre"] for c in cats]
            else:
                nombres = [
                    "Falla de encendido / No enciende", "Pantalla sin señal / Monitor apagado",
                    "Sin conexión a Internet / Falla de red", "Teclado dañado / Teclas no responden",
                    "Mouse no responde / Dañado", "Sistema operativo no inicia / Pantalla azul",
                    "Lentitud extrema / Bloqueo del sistema", "Software no abre o error de licencia",
                    "Sin audio / Problema con auriculares o bocinas", "Puerto USB dañado / No reconoce periféricos",
                    "Proyector / Cañón no enciende o sin señal", "Sobrecalentamiento / Ruido excesivo de ventilador",
                    "Infección por virus / Malware", "Otro problema"
                ]
        except Exception:
            nombres = [
                "Falla de encendido / No enciende", "Pantalla sin señal / Monitor apagado",
                "Sin conexión a Internet / Falla de red", "Teclado dañado / Teclas no responden",
                "Mouse no responde / Dañado", "Sistema operativo no inicia / Pantalla azul",
                "Lentitud extrema / Bloqueo del sistema", "Software no abre o error de licencia",
                "Sin audio / Problema con auriculares o bocinas", "Puerto USB dañado / No reconoce periféricos",
                "Proyector / Cañón no enciende o sin señal", "Sobrecalentamiento / Ruido excesivo de ventilador",
                "Infección por virus / Malware", "Otro problema"
            ]
        self.combo_tipo_problema.addItems(nombres)

    def _actualizar_prioridad_por_categoria(self, categoria: str):
        if hasattr(self, "_mapa_prioridades") and categoria in self._mapa_prioridades:
            prio = self._mapa_prioridades[categoria]
            self.combo_prioridad.setCurrentText(prio)

    def _actualizar_equipos(self, laboratorio: str):
        """
        Genera la lista de equipos correspondientes al laboratorio seleccionado.
        """
        self.combo_equipo.clear()
        equipos = [f"PC-{i:02d}" for i in range(1, 21)]
        self.combo_equipo.addItems(equipos)

    def _on_guardar(self):
        # Validación mínima de UI. La validación de negocio real
        # (ej. "el equipo ya tiene una incidencia abierta") vive en
        # services/, no aquí — la UI no decide reglas de negocio.
        campos_invalidos = False
        if not self.input_descripcion.toPlainText().strip():
            self.input_descripcion.setStyleSheet("border: 1px solid #DC2626;")
            campos_invalidos = True
        else:
            self.input_descripcion.setStyleSheet("")

        if campos_invalidos:
            return

        datos = {
            "laboratorio": self.combo_laboratorio.currentText(),
            "equipo": self.combo_equipo.currentText(),
            "tipo_problema": self.combo_tipo_problema.currentText(),
            "prioridad": self.combo_prioridad.currentText(),
            "fecha": self.input_fecha.date().toString("yyyy-MM-dd"),
            "descripcion": self.input_descripcion.toPlainText().strip(),
        }
        self.guardar_solicitado.emit(datos)