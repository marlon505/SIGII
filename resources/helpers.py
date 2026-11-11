# styles/helpers.py
# pyrefly: ignore [missing-import]
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QTableWidgetItem

RUTA_RECURSOS = Path(__file__).resolve().parent


def cargar_imagen_fondo(nombre_archivo: str) -> QPixmap:
    """Carga una imagen de fondo desde resources, sin depender de la carpeta actual."""
    ruta = RUTA_RECURSOS / nombre_archivo
    imagen = QPixmap(str(ruta))
    if imagen.isNull():
        raise FileNotFoundError(f"No se pudo cargar la imagen de fondo: {ruta}")
    return imagen


def aplicar_estado_visual(label: QLabel, estado: str):
    """Mapea el texto del estado a la propiedad QSS y fuerza el repintado."""
    mapa = {
        "Pendiente": "pendiente",
        "Confirmado": "confirmado",
        "En reparación": "en_reparacion",
        "Resuelto": "resuelto",
        "Reabierto": "reabierto",
    }
    label.setProperty("estado", mapa.get(estado, ""))
    label.style().unpolish(label)
    label.style().polish(label)

def poblar_fila_estado(tabla, fila: int, valores: list[str], indice_estado: int):
    """Llena una fila de QTableWidget, coloreando la columna de estado.

    valores: textos en el mismo orden que las columnas de la tabla.
    indice_estado: posición (0-based) de la columna que contiene el estado.

    Reutilizable en cualquier tabla de incidencias del sistema (Maestro,
    Técnico, Administrador) — no la dupliques dentro de cada widget.
    """
    for col, texto in enumerate(valores):
        if col == indice_estado:
            label = QLabel(texto)
            aplicar_estado_visual(label, texto)
            tabla.setCellWidget(fila, col, label)
        else:
            tabla.setItem(fila, col, QTableWidgetItem(texto))