"""
ui/detalle_incidencia_widget.py

Objetivo:
    Widget para mostrar y permitir la edición completa de una incidencia reportada
    (Laboratorio, Equipo, Tipo de problema, Prioridad, Estado, Fecha,
    Técnico asignado y Descripción).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QComboBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from resources.colors import Colors
from services import incidencia_service


class DetalleIncidenciaWidget(QWidget):
    """
    Muestra los datos de una incidencia en una tarjeta modal
    y permite modificar todos sus campos guardándolos en MySQL.
    """

    cerrar_solicitado = Signal()
    guardado_exitoso = Signal()

    def __init__(self, datos: dict, parent: QWidget = None, usuario_rol: str = None, solo_lectura: bool = False):
        super().__init__(parent)
        self._datos = datos or {}
        self._usuario_rol = usuario_rol
        self._solo_lectura = solo_lectura
        self._mapa_prioridades = {}
        self._construir_ui()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        id_rep = self._datos.get("id_reporte")
        es_admin = bool(self._usuario_rol and self._usuario_rol.lower() in ["administrador", "admin"])

        if self._solo_lectura:
            titulo_texto = f"Historial y Detalle de Incidencia #{id_rep}" if id_rep else "Detalle de Incidencia"
            color_titulo = Colors.ROJO_ADMIN
        else:
            titulo_texto = f"Editar Incidencia #{id_rep}" if id_rep else "Editar Incidencia"
            color_titulo = Colors.ROJO_ADMIN if es_admin else Colors.AZUL

        titulo = QLabel(titulo_texto)
        titulo.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color_titulo};")
        layout.addWidget(titulo)

        # Contenedor de formulario
        grid_frame = QFrame()
        grid_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QLabel {
                font-size: 13px;
            }
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                font-size: 13px;
                color: #1E293B;
                min-width: 180px;
            }
            QComboBox:hover {
                border-color: #94A3B8;
            }
        """)
        grid_layout = QVBoxLayout(grid_frame)
        grid_layout.setContentsMargins(14, 12, 14, 12)
        grid_layout.setSpacing(8)

        def _crear_etiqueta(texto: str) -> QLabel:
            lbl = QLabel(f"<b>{texto}:</b>")
            lbl.setStyleSheet("color: #475569;")
            lbl.setFixedWidth(140)
            return lbl

        # 1. Laboratorio
        fila_lab = QHBoxLayout()
        fila_lab.addWidget(_crear_etiqueta("Laboratorio"))
        self.combo_laboratorio = QComboBox()
        self._cargar_catalogo_laboratorios()
        lab_actual = str(self._datos.get("laboratorio", "")).strip()
        idx_lab = self.combo_laboratorio.findText(lab_actual, Qt.MatchFlag.MatchFixedString)
        if idx_lab >= 0:
            self.combo_laboratorio.setCurrentIndex(idx_lab)
        elif lab_actual:
            self.combo_laboratorio.addItem(lab_actual)
            self.combo_laboratorio.setCurrentText(lab_actual)
        self.combo_laboratorio.currentTextChanged.connect(self._actualizar_equipos)
        fila_lab.addWidget(self.combo_laboratorio)
        fila_lab.addStretch()
        grid_layout.addLayout(fila_lab)

        # 2. Equipo
        fila_eq = QHBoxLayout()
        fila_eq.addWidget(_crear_etiqueta("Equipo"))
        self.combo_equipo = QComboBox()
        self._actualizar_equipos(self.combo_laboratorio.currentText())
        eq_actual = str(self._datos.get("equipo", "")).strip()
        idx_eq = self.combo_equipo.findText(eq_actual, Qt.MatchFlag.MatchFixedString)
        if idx_eq >= 0:
            self.combo_equipo.setCurrentIndex(idx_eq)
        elif eq_actual:
            self.combo_equipo.addItem(eq_actual)
            self.combo_equipo.setCurrentText(eq_actual)
        fila_eq.addWidget(self.combo_equipo)
        fila_eq.addStretch()
        grid_layout.addLayout(fila_eq)

        # 3. Tipo de problema
        fila_tipo = QHBoxLayout()
        fila_tipo.addWidget(_crear_etiqueta("Tipo de problema"))
        self.combo_tipo_problema = QComboBox()
        self._cargar_catalogo_categorias()
        tipo_actual = str(self._datos.get("tipo_problema", "")).strip()
        idx_tipo = self.combo_tipo_problema.findText(tipo_actual, Qt.MatchFlag.MatchFixedString)
        if idx_tipo >= 0:
            self.combo_tipo_problema.setCurrentIndex(idx_tipo)
        elif tipo_actual:
            self.combo_tipo_problema.addItem(tipo_actual)
            self.combo_tipo_problema.setCurrentText(tipo_actual)
        self.combo_tipo_problema.currentTextChanged.connect(self._actualizar_prioridad_por_categoria)
        fila_tipo.addWidget(self.combo_tipo_problema)
        fila_tipo.addStretch()
        grid_layout.addLayout(fila_tipo)

        # 4. Prioridad
        fila_prio = QHBoxLayout()
        fila_prio.addWidget(_crear_etiqueta("Prioridad"))
        self.combo_prioridad = QComboBox()
        self.combo_prioridad.addItems(["Baja", "Media", "Alta", "Crítica"])
        prio_actual = str(self._datos.get("prioridad", "Media")).strip()
        idx_prio = self.combo_prioridad.findText(prio_actual, Qt.MatchFlag.MatchFixedString)
        if idx_prio >= 0:
            self.combo_prioridad.setCurrentIndex(idx_prio)
        elif prio_actual:
            self.combo_prioridad.addItem(prio_actual)
            self.combo_prioridad.setCurrentText(prio_actual)
        fila_prio.addWidget(self.combo_prioridad)
        fila_prio.addStretch()
        grid_layout.addLayout(fila_prio)

        # 5. Estado
        fila_estado = QHBoxLayout()
        fila_estado.addWidget(_crear_etiqueta("Estado"))
        self.combo_estado = QComboBox()
        self.combo_estado.addItems(["Pendiente", "Confirmado", "En proceso", "En reparación", "Resuelto", "Reabierto"])
        estado_actual = str(self._datos.get("estado", "Pendiente")).strip()
        idx_estado = self.combo_estado.findText(estado_actual, Qt.MatchFlag.MatchFixedString)
        if idx_estado < 0:
            estado_norm = estado_actual.replace("reparacion", "reparación")
            idx_estado = self.combo_estado.findText(estado_norm, Qt.MatchFlag.MatchFixedString)
        if idx_estado >= 0:
            self.combo_estado.setCurrentIndex(idx_estado)
        elif estado_actual:
            self.combo_estado.addItem(estado_actual)
            self.combo_estado.setCurrentText(estado_actual)
        fila_estado.addWidget(self.combo_estado)
        fila_estado.addStretch()
        grid_layout.addLayout(fila_estado)

        # 6. Técnico asignado
        fila_tec = QHBoxLayout()
        fila_tec.addWidget(_crear_etiqueta("Técnico asignado"))
        es_tecnico = bool(self._usuario_rol and self._usuario_rol.lower() in ["técnico", "tecnico"])
        if es_admin and not self._solo_lectura:
            self.combo_tecnico = QComboBox()
            if es_admin:
                self.combo_tecnico.addItem("Sin asignar", None)
            try:
                tecnicos = incidencia_service.obtener_tecnicos()
                for tec in tecnicos:
                    self.combo_tecnico.addItem(tec["nombre_completo"], tec["carnet_tecnico"])
            except Exception as e:
                print(f"[DetalleIncidencia] Error cargando técnicos: {e}")

            carnet_actual = self._datos.get("carnet_tecnico")
            nombre_tec_actual = self._datos.get("tecnico_nombre") or self._datos.get("tecnico", "")
            idx_tec = -1
            if carnet_actual:
                idx_tec = self.combo_tecnico.findData(carnet_actual)
            if idx_tec < 0 and nombre_tec_actual and nombre_tec_actual != "Sin asignar":
                idx_tec = self.combo_tecnico.findText(nombre_tec_actual, Qt.MatchFlag.MatchContains)
            if idx_tec >= 0:
                self.combo_tecnico.setCurrentIndex(idx_tec)
            elif nombre_tec_actual and nombre_tec_actual != "Sin asignar":
                self.combo_tecnico.addItem(nombre_tec_actual, carnet_actual)
                self.combo_tecnico.setCurrentIndex(self.combo_tecnico.count() - 1)
            fila_tec.addWidget(self.combo_tecnico)
        else:
            tecnico = self._datos.get("tecnico_nombre") or self._datos.get("tecnico", "Sin asignar")
            val_tec = QLabel(str(tecnico))
            val_tec.setStyleSheet("color: #1E293B; font-weight: 500;")
            fila_tec.addWidget(val_tec)
        fila_tec.addStretch()
        grid_layout.addLayout(fila_tec)

        # 7. Información fija / auditoría
        def _fila_info(label: str, valor: str):
            h = QHBoxLayout()
            h.addWidget(_crear_etiqueta(label))
            val = QLabel(str(valor))
            val.setStyleSheet("color: #1E293B; font-weight: 500;")
            h.addWidget(val)
            h.addStretch()
            return h

        grid_layout.addLayout(_fila_info("Fecha de reporte", self._datos.get("fecha", "-")))

        if self._solo_lectura or es_admin:
            profesor = self._datos.get("profesor_nombre") or self._datos.get("profesor") or "-"
            grid_layout.addLayout(_fila_info("Reportado por", profesor))
            f_conf = self._datos.get("fecha_confirmado") or "No confirmada"
            grid_layout.addLayout(_fila_info("Fecha confirmado", str(f_conf)))
            f_res = self._datos.get("fecha_resolucion") or "Pendiente de resolución"
            grid_layout.addLayout(_fila_info("Fecha resolución", str(f_res)))
            if self._datos.get("reporte_cierre"):
                grid_layout.addLayout(_fila_info("Reporte de cierre", str(self._datos.get("reporte_cierre"))))

        layout.addWidget(grid_frame)

        # 8. Descripción completa
        layout.addWidget(QLabel("<b>Descripción de la incidencia:</b>"))
        self.input_descripcion = QTextEdit()
        self.input_descripcion.setPlainText(self._datos.get("descripcion", ""))
        self.input_descripcion.setPlaceholderText("Detalles de la incidencia...")
        self.input_descripcion.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                color: #334155;
            }
            QTextEdit:focus {
                border-color: #1E3A8A;
            }
        """)
        self.input_descripcion.setFixedHeight(85)
        layout.addWidget(self.input_descripcion)

        # --- BOTONERA INFERIOR ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        # Botón Cancelar / Cerrar
        self.btn_cerrar = QPushButton("Cancelar")
        self.btn_cerrar.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0;
                color: #334155;
                font-weight: 600;
                padding: 7px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #CBD5E1;
            }
        """)
        self.btn_cerrar.clicked.connect(self.cerrar_solicitado.emit)
        btn_layout.addWidget(self.btn_cerrar)

        # Botón Guardar Cambios
        self.btn_guardar = QPushButton("Guardar Cambios")
        color_btn = Colors.ROJO_ADMIN if es_admin else Colors.AZUL
        color_hover = Colors.ROJO_ADMIN_OSCURO if es_admin else "#1D4ED8"
        self.btn_guardar.setStyleSheet(f"""
            QPushButton {{
                background-color: {color_btn};
                color: white;
                font-weight: 600;
                padding: 7px 18px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {color_hover};
            }}
        """)
        self.btn_guardar.clicked.connect(self._guardar_cambios)
        btn_layout.addWidget(self.btn_guardar)

        layout.addLayout(btn_layout)

        # Ajustes según modo
        if self._solo_lectura:
            titulo.setText(f"Historial y Detalle de Incidencia #{id_rep}" if id_rep else "Detalle de Incidencia")
            self.combo_laboratorio.setEnabled(False)
            self.combo_equipo.setEnabled(False)
            self.combo_tipo_problema.setEnabled(False)
            self.combo_prioridad.setEnabled(False)
            self.combo_estado.setEnabled(False)
            self.input_descripcion.setReadOnly(True)
            self.btn_guardar.hide()
            self.btn_cerrar.setText("Cerrar")
        elif self._usuario_rol and self._usuario_rol.lower() in ["técnico", "tecnico"]:
            titulo.setText(f"Gestionar Incidencia #{id_rep}" if id_rep else "Gestionar Incidencia")
            self.combo_laboratorio.setEnabled(False)
            self.combo_equipo.setEnabled(False)
            self.combo_tipo_problema.setEnabled(False)
            self.combo_prioridad.setEnabled(False)
            self.input_descripcion.setReadOnly(True)
            # El combo_estado permanece HABILITADO

    def _cargar_catalogo_laboratorios(self):
        try:
            labs = incidencia_service.obtener_laboratorios()
            nombres = [l["nombre"] for l in labs] if labs else [f"Laboratorio FC {i}" for i in range(1, 11)]
        except Exception:
            nombres = [f"Laboratorio FC {i}" for i in range(1, 11)]
        self.combo_laboratorio.clear()
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
        self.combo_tipo_problema.clear()
        self.combo_tipo_problema.addItems(nombres)

    def _actualizar_prioridad_por_categoria(self, categoria: str):
        if hasattr(self, "_mapa_prioridades") and categoria in self._mapa_prioridades:
            prio = self._mapa_prioridades[categoria]
            self.combo_prioridad.setCurrentText(prio)

    def _actualizar_equipos(self, laboratorio: str):
        self.combo_equipo.clear()
        equipos = [f"PC-{i:02d}" for i in range(1, 21)]
        self.combo_equipo.addItems(equipos)

    def _guardar_cambios(self):
        if self._solo_lectura:
            QMessageBox.warning(self, "Modo de Visión", "Acción no disponible en modo de visión.")
            return

        id_rep = self._datos.get("id_reporte")
        if not id_rep:
            QMessageBox.warning(self, "Error", "No se encontró el ID de la incidencia.")
            return

        desc_texto = self.input_descripcion.toPlainText().strip()
        if not desc_texto:
            QMessageBox.warning(self, "Campo requerido", "Por favor ingresa una descripción para la incidencia.")
            return

        if self._usuario_rol and self._usuario_rol.lower() in ["técnico", "tecnico"]:
            nuevo_estado = self.combo_estado.currentText()
            res = incidencia_service.actualizar_estado_incidencia(id_rep, nuevo_estado)
        else:
            datos_actualizados = {
                "laboratorio": self.combo_laboratorio.currentText(),
                "equipo": self.combo_equipo.currentText(),
                "tipo_problema": self.combo_tipo_problema.currentText(),
                "prioridad": self.combo_prioridad.currentText(),
                "estado": self.combo_estado.currentText(),
                "descripcion": desc_texto,
            }
            if hasattr(self, "combo_tecnico"):
                datos_actualizados["carnet_tecnico"] = self.combo_tecnico.currentData()

            res = incidencia_service.actualizar_incidencia(id_rep, datos_actualizados)

        if res.get("exito"):
            QMessageBox.information(
                self,
                "Incidencia Actualizada",
                "Todos los datos de la incidencia han sido actualizados en la base de datos."
            )
            self.guardado_exitoso.emit()
            self.cerrar_solicitado.emit()
        else:
            QMessageBox.critical(
                self,
                "Error al Actualizar",
                res.get("mensaje", "No se pudo actualizar la incidencia en la base de datos.")
            )
