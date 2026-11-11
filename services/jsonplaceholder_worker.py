"""Consulta en segundo plano de las publicaciones de demostración."""

from PySide6.QtCore import QThread, Signal

from services.api_client import ExternalAPIError
from services.api_client import obtener_publicaciones


class JSONPlaceholderWorker(QThread):
    completado = Signal(object)
    error = Signal(str)

    def run(self):
        try:
            self.completado.emit(obtener_publicaciones())
        except ExternalAPIError as error:
            self.error.emit(str(error))
