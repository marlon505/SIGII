"""Generación local de reportes PDF y Excel."""
from datetime import date, datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import json
import os
import re
import socket

from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COLUMNAS = (
    ("ID reporte", "id_reporte"),
    ("Laboratorio", "laboratorio"),
    ("Equipo", "equipo"),
    ("Tipo de problema", "tipo_problema"),
    ("Prioridad", "prioridad"),
    ("Estado", "estado"),
    ("Técnico asignado", "tecnico_nombre"),
    ("Reportado por", "profesor_nombre"),
    ("Fecha", "fecha"),
    ("Fecha confirmación", "fecha_confirmado"),
    ("Fecha resolución", "fecha_resolucion"),
    ("Descripción", "descripcion"),
    ("Reporte de cierre", "reporte_cierre"),
)

COLOR_PRIMARIO = "B91C1C"
COLOR_CLARO = "FEE2E2"
CARACTERES_NO_VALIDOS = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")


def exportar_incidencias_excel(
    incidencias: Sequence[Mapping[str, Any]],
    filename: str | Path,
) -> str:
    """Guarda las incidencias recibidas, normalmente las visibles tras filtrar."""
    if not incidencias:
        raise ValueError("No hay incidencias para exportar.")

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Incidencias"
    hoja.freeze_panes = "A2"
    hoja.sheet_view.showGridLines = False
    hoja.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNAS))}{len(incidencias) + 1}"

    for indice, (titulo, _) in enumerate(COLUMNAS, start=1):
        celda = hoja.cell(row=1, column=indice, value=titulo)
        celda.fill = PatternFill("solid", fgColor=COLOR_PRIMARIO)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.alignment = Alignment(horizontal="center", vertical="center")

    for numero_fila, incidencia in enumerate(incidencias, start=2):
        for numero_columna, (_, campo) in enumerate(COLUMNAS, start=1):
            valor = incidencia.get(campo)
            if campo == "tecnico_nombre":
                valor = valor or incidencia.get("tecnico") or "Sin asignar"
            elif campo == "profesor_nombre":
                valor = valor or incidencia.get("profesor") or ""
            elif valor is None:
                valor = ""
            if isinstance(valor, str):
                valor = CARACTERES_NO_VALIDOS.sub("", valor)

            celda = hoja.cell(row=numero_fila, column=numero_columna, value=valor)
            if isinstance(valor, str):
                celda.data_type = "s"
            if numero_fila % 2 == 1:
                celda.fill = PatternFill("solid", fgColor=COLOR_CLARO)
            celda.alignment = Alignment(vertical="top", wrap_text=True)

    for numero_columna, (titulo, campo) in enumerate(COLUMNAS, start=1):
        valores = [titulo] + [
            str(incidencia.get(campo) or "")[:120] for incidencia in incidencias[:200]
        ]
        ancho = min(max(max(map(len, valores)) + 2, 12), 42)
        hoja.column_dimensions[get_column_letter(numero_columna)].width = ancho

    hoja.row_dimensions[1].height = 24
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.oddHeader.center.text = "SIGII | Reporte de incidencias"
    hoja.oddFooter.right.text = f"Emitido: {datetime.now():%d/%m/%Y %H:%M}"

    ruta = Path(filename)
    libro.save(ruta)
    return str(ruta)


def exportar_incidencias_pdf(
    incidencias: Sequence[Mapping[str, Any]],
    filename: str | Path,
) -> str:
    """Genera un PDF de resumen con las incidencias recibidas."""
    if not incidencias:
        raise ValueError("No hay incidencias para exportar.")

    ruta = Path(filename)
    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Reporte de incidencias SIGII",
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloIncidencias",
        parent=estilos["Title"],
        textColor=colors.HexColor(f"#{COLOR_PRIMARIO}"),
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )
    estilo_celda = ParagraphStyle(
        "CeldaIncidencias",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        wordWrap="CJK",
    )
    estilo_encabezado = ParagraphStyle(
        "EncabezadoIncidencias",
        parent=estilo_celda,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    columnas = (
        ("ID", "id_reporte"),
        ("Laboratorio", "laboratorio"),
        ("Equipo", "equipo"),
        ("Problema", "tipo_problema"),
        ("Prioridad", "prioridad"),
        ("Estado", "estado"),
        ("Técnico", "tecnico_nombre"),
        ("Fecha", "fecha"),
    )
    filas = [[
        Paragraph(escape(encabezado), estilo_encabezado)
        for encabezado, _ in columnas
    ]]
    for incidencia in incidencias:
        fila = []
        for _, campo in columnas:
            valor = incidencia.get(campo)
            if campo == "tecnico_nombre":
                valor = valor or incidencia.get("tecnico") or "Sin asignar"
            texto = "" if valor is None else str(valor)
            texto = CARACTERES_NO_VALIDOS.sub("", texto)
            fila.append(Paragraph(escape(texto), estilo_celda))
        filas.append(fila)

    tabla = Table(
        filas,
        colWidths=[
            documento.width * 0.06,
            documento.width * 0.13,
            documento.width * 0.11,
            documento.width * 0.23,
            documento.width * 0.08,
            documento.width * 0.11,
            documento.width * 0.17,
            documento.width * 0.11,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    estilos_tabla = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_PRIMARIO}")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for numero_fila in range(2, len(filas), 2):
        estilos_tabla.append(
            ("BACKGROUND", (0, numero_fila), (-1, numero_fila), colors.HexColor(f"#{COLOR_CLARO}"))
        )
    tabla.setStyle(TableStyle(estilos_tabla))

    documento.build([
        Paragraph("Reporte de incidencias SIGII", estilo_titulo),
        Paragraph(
            f"Emitido: {datetime.now():%d/%m/%Y %H:%M} · "
            f"Total de registros: {len(incidencias)}",
            estilos["Normal"],
        ),
        Spacer(1, 4 * mm),
        tabla,
    ])
    return str(ruta)


def exportar_publicaciones_excel(
    publicaciones: Sequence[Mapping[str, Any]],
    filename: str | Path,
) -> str:
    """Exporta publicaciones de demostración a un libro independiente."""
    if not publicaciones:
        raise ValueError("No hay publicaciones para exportar.")

    encabezados = ("ID", "ID usuario", "Título", "Contenido")
    campos = ("id", "usuario_id", "titulo", "contenido")
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Publicaciones demo"
    hoja.freeze_panes = "A2"
    hoja.sheet_view.showGridLines = False
    hoja.auto_filter.ref = f"A1:{get_column_letter(len(encabezados))}{len(publicaciones) + 1}"

    for columna, encabezado in enumerate(encabezados, start=1):
        celda = hoja.cell(row=1, column=columna, value=encabezado)
        celda.fill = PatternFill("solid", fgColor=COLOR_PRIMARIO)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.alignment = Alignment(horizontal="center", vertical="center")

    for numero_fila, publicacion in enumerate(publicaciones, start=2):
        for numero_columna, campo in enumerate(campos, start=1):
            valor = publicacion.get(campo)
            if valor is None:
                valor = ""
            if isinstance(valor, str):
                valor = CARACTERES_NO_VALIDOS.sub("", valor)
            celda = hoja.cell(row=numero_fila, column=numero_columna, value=valor)
            if isinstance(valor, str):
                celda.data_type = "s"
            if numero_fila % 2 == 1:
                celda.fill = PatternFill("solid", fgColor=COLOR_CLARO)
            celda.alignment = Alignment(vertical="top", wrap_text=True)

    for columna, campo in enumerate(campos, start=1):
        valores = [encabezados[columna - 1]] + [
            str(publicacion.get(campo) or "")[:120]
            for publicacion in publicaciones[:200]
        ]
        hoja.column_dimensions[get_column_letter(columna)].width = min(
            max(max(map(len, valores)) + 2, 12), 60
        )

    hoja.row_dimensions[1].height = 24
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.oddHeader.center.text = "SIGII | Publicaciones de demostración"
    hoja.oddFooter.right.text = f"Emitido: {datetime.now():%d/%m/%Y %H:%M}"

    ruta = Path(filename)
    libro.save(ruta)
    return str(ruta)


def exportar_publicaciones_pdf(
    publicaciones: Sequence[Mapping[str, Any]],
    filename: str | Path,
) -> str:
    """Exporta publicaciones de demostración recibidas desde la API a PDF."""
    if not publicaciones:
        raise ValueError("No hay publicaciones para exportar.")

    ruta = Path(filename)
    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Publicaciones de demostración",
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloPublicaciones",
        parent=estilos["Title"],
        textColor=colors.HexColor(f"#{COLOR_PRIMARIO}"),
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )
    estilo_celda = ParagraphStyle(
        "CeldaPublicaciones",
        parent=estilos["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="CJK",
    )
    estilo_encabezado = ParagraphStyle(
        "EncabezadoPublicaciones",
        parent=estilo_celda,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    encabezados = ("ID", "ID usuario", "Título", "Contenido")
    campos = ("id", "usuario_id", "titulo", "contenido")
    filas = [[Paragraph(escape(encabezado), estilo_encabezado) for encabezado in encabezados]]
    for publicacion in publicaciones:
        fila = []
        for campo in campos:
            valor = publicacion.get(campo)
            texto = "" if valor is None else str(valor)
            texto = CARACTERES_NO_VALIDOS.sub("", texto)
            fila.append(Paragraph(escape(texto), estilo_celda))
        filas.append(fila)

    tabla = Table(
        filas,
        colWidths=[
            documento.width * 0.07,
            documento.width * 0.10,
            documento.width * 0.28,
            documento.width * 0.55,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )
    estilos_tabla = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{COLOR_PRIMARIO}")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for numero_fila in range(2, len(filas), 2):
        estilos_tabla.append(
            ("BACKGROUND", (0, numero_fila), (-1, numero_fila), colors.HexColor(f"#{COLOR_CLARO}"))
        )
    tabla.setStyle(TableStyle(estilos_tabla))

    documento.build([
        Paragraph("Publicaciones de demostración de la API", estilo_titulo),
        Paragraph(f"Emitido: {datetime.now():%d/%m/%Y %H:%M}", estilos["Normal"]),
        Spacer(1, 4 * mm),
        tabla,
    ])
    return str(ruta)


# Consolidado desde services/carbone_export_service.py: integracion Carbone API.
"""Generación de reportes de incidencias mediante Carbone Cloud API v5."""



PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

CARBONE_API_URL = os.getenv("CARBONE_API_URL", "https://api.carbone.io").strip().rstrip("/")
CARBONE_TIMEOUT_SECONDS = 60
CARBONE_EXPORT_FORMATS = {
    "pdf": ("CARBONE_PDF_TEMPLATE_ID", b"%PDF-"),
    "excel_pdf": ("CARBONE_EXCEL_TEMPLATE_ID", b"%PDF-"),
}


class CarboneExportError(RuntimeError):
    """Configuración, comunicación o respuesta inválida de Carbone."""


def exportar_incidencias_con_carbone(
    incidencias: Sequence[Mapping[str, Any]],
    filename: str | Path,
    formato: str,
) -> str:
    """Renderiza una plantilla con Carbone; la plantilla Excel también sale como PDF."""
    if formato not in CARBONE_EXPORT_FORMATS:
        raise ValueError("El formato debe ser 'pdf' o 'excel_pdf'.")
    if not incidencias:
        raise ValueError("No hay incidencias para exportar.")

    variable_plantilla, firma_salida = CARBONE_EXPORT_FORMATS[formato]
    token = os.getenv("CARBONE_API_TOKEN", "").strip()
    template_id = os.getenv(variable_plantilla, "").strip()
    if not token:
        raise CarboneExportError(
            "Falta CARBONE_API_TOKEN en el archivo .env. Configura tu token de Carbone."
        )
    if not template_id:
        raise CarboneExportError(
            f"Falta {variable_plantilla} en .env. Sube una plantilla a Carbone y configura su ID."
        )

    url = urlsplit(CARBONE_API_URL)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise CarboneExportError("CARBONE_API_URL debe ser una URL HTTPS válida.")

    datos = {
        "data": {"incidencias": list(incidencias), "total": len(incidencias)},
        "convertTo": "pdf",
        "reportName": "Incidencias_SIGII",
    }
    try:
        contenido_json = json.dumps(
            datos,
            ensure_ascii=False,
            default=_serializar_valor,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CarboneExportError(f"No se pudieron preparar los datos del reporte: {error}") from error

    solicitud = Request(
        f"{CARBONE_API_URL}/render/{quote(template_id, safe='')}?download=true",
        data=contenido_json,
        headers={
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "carbone-version": "5",
        },
        method="POST",
    )
    try:
        with urlopen(solicitud, timeout=CARBONE_TIMEOUT_SECONDS) as respuesta:
            contenido = respuesta.read()
            content_type = respuesta.headers.get("Content-Type", "unknown")
    except HTTPError as error:
        detalle = error.read(4096).decode("utf-8", errors="replace")
        try:
            payload = json.loads(detalle)
            mensaje = payload.get("error", {}).get("message") or payload.get("error") or detalle
        except (json.JSONDecodeError, AttributeError):
            mensaje = detalle or f"HTTP {error.code}"
        raise CarboneExportError(
            f"Carbone respondió con HTTP {error.code}: {mensaje}"
        ) from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise CarboneExportError(f"No se pudo conectar con Carbone: {error}") from error

    if not contenido.startswith(firma_salida):
        if "json" in content_type.lower():
            try:
                respuesta_api = json.loads(contenido.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                respuesta_api = {}
            error_api = respuesta_api.get("error")
            if isinstance(error_api, dict):
                error_api = error_api.get("message") or error_api.get("description")
            if error_api:
                raise CarboneExportError(f"Carbone rechazó la generación: {error_api}")
        raise CarboneExportError(
            f"Carbone no devolvió un archivo PDF válido "
            f"(Content-Type: {content_type}). Revisa el formato del token y la plantilla."
        )

    ruta = Path(filename)
    ruta.write_bytes(contenido)
    return str(ruta)


def _serializar_valor(valor: Any):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(f"Tipo de dato no compatible con JSON: {type(valor).__name__}")
