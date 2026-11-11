"""Solicitud en segundo plano de reportes a Carbone Cloud."""

from typing import Any, Mapping, Sequence

from PySide6.QtCore import QThread, Signal

from services.report_export_service import (
    CarboneExportError,
    exportar_incidencias_con_carbone,
)


class ReportExportAPIWorker(QThread):
    completado = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        incidencias: Sequence[Mapping[str, Any]],
        filename: str,
        formato: str,
        parent=None,
    ):
        super().__init__(parent)
        self.incidencias = incidencias
        self.filename = filename
        self.formato = formato

    def run(self):
        try:
            ruta = exportar_incidencias_con_carbone(
                self.incidencias,
                self.filename,
                self.formato,
            )
        except (CarboneExportError, OSError, TypeError, ValueError) as error:
            self.error.emit(str(error))
            return
        self.completado.emit(ruta)
