# services/incidencia_service.py
# -*- coding: utf-8 -*-
"""
incidencia_service.py

Objetivo:
    Capa de acceso a datos y lógica de negocio para la gestión de incidencias,
    reportes, laboratorios y categorías en el sistema SIGII.

Responsabilidad:
    - Asegurar que los catálogos base (laboratorios y categorías) existan en la BD.
    - Registrar nuevas incidencias vinculadas al carnet/correo del profesor.
    - Consultar reportes e incidencias por profesor o globales para los dashboards.
    - Gestionar cuentas, laboratorios y métricas administrativas.
    - Manejar transacciones y conexiones a MySQL de forma segura.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import re

from mysql.connector import Error as MySQLError
import bcrypt

from services.auth import get_connection

obtener_conexion = get_connection


LABORATORIOS_DEFECTO = [
    ("LAB-01", "Laboratorio FC 1", "Edificio FC - Rc. Tomas Borges 1"),
    ("LAB-02", "Laboratorio FC 2", "Edificio FC - Rc. Tomas Borges 1"),
    ("LAB-03", "Laboratorio FC 3", "Edificio FC - Rc. Tomas Borges 2"),
    ("LAB-04", "Laboratorio FC 4", "Edificio FC - Rc. Tomas Borges 2"),
    ("LAB-05", "Laboratorio FC 5", "Edificio FC - Rc. Tomas Borges 3"),
    ("LAB-06", "Laboratorio FC 6", "Edificio FC - Rc. Tomas Borges 3"),
    ("LAB-07", "Laboratorio FC 7", "Edificio FC - Rc. Tomas Borges 4"),
    ("LAB-08", "Laboratorio FC 8", "Edificio FC - Rc. Tomas Borges 4"),
    ("LAB-09", "Laboratorio FC 9", "Edificio FC - Rc. Tomas Borges 5"),
    ("LAB-10", "Laboratorio FC 10", "Edificio FC - Rc. Tomas Borges 5"),
]

CATEGORIAS_DEFECTO = [
    ("CAT-01", "Falla de encendido / No enciende", "Alta"),
    ("CAT-02", "Pantalla sin señal / Monitor apagado", "Media"),
    ("CAT-03", "Sin conexión a Internet / Falla de red", "Alta"),
    ("CAT-04", "Teclado dañado / Teclas no responden", "Baja"),
    ("CAT-05", "Mouse no responde / Dañado", "Baja"),
    ("CAT-06", "Sistema operativo no inicia / Pantalla azul", "Crítica"),
    ("CAT-07", "Lentitud extrema / Bloqueo del sistema", "Media"),
    ("CAT-08", "Software no abre o error de licencia", "Media"),
    ("CAT-09", "Sin audio / Problema con auriculares o bocinas", "Baja"),
    ("CAT-10", "Puerto USB dañado / No reconoce periféricos", "Baja"),
    ("CAT-11", "Proyector / Cañón no enciende o sin señal", "Media"),
    ("CAT-12", "Sobrecalentamiento / Ruido excesivo de ventilador", "Alta"),
    ("CAT-13", "Infección por virus / Malware", "Crítica"),
    ("CAT-14", "Otro problema", "Media"),
]

def asegurar_catalogos() -> None:
    """
    Verifica e inserta los catálogos base de laboratorios y categorías
    si están vacíos o incompletos en la base de datos.
    """
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        # 1. Asegurar laboratorios
        cursor.execute("SELECT id_laboratorio FROM laboratorio")
        labs_existentes = {fila["id_laboratorio"] for fila in cursor.fetchall()}
        for id_lab, nombre, ubicacion in LABORATORIOS_DEFECTO:
            if id_lab not in labs_existentes:
                cursor.execute(
                    """
                    INSERT INTO laboratorio (id_laboratorio, nombre, ubicacion)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), ubicacion = VALUES(ubicacion)
                    """,
                    (id_lab, nombre, ubicacion)
                )

        # 2. Asegurar categorías
        cursor.execute("SELECT id_categoria FROM categoria")
        cats_existentes = {fila["id_categoria"] for fila in cursor.fetchall()}
        for id_cat, nombre, prioridad in CATEGORIAS_DEFECTO:
            if id_cat not in cats_existentes:
                prio_norm = 'Crítica' if prioridad in ('Critica', 'Crítica') else prioridad
                cursor.execute(
                    """
                    INSERT INTO categoria (id_categoria, nombre, prioridad)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), prioridad = VALUES(prioridad)
                    """,
                    (id_cat, nombre, prio_norm)
                )

        # 3. Asegurar columnas y ENUM en tabla reporte
        try:
            cursor.execute("DESCRIBE reporte")
            columnas_rep = {fila["Field"]: fila for fila in cursor.fetchall()}
            if "fecha_confirmado" not in columnas_rep:
                cursor.execute(
                    "ALTER TABLE reporte ADD COLUMN fecha_confirmado DATETIME NULL AFTER estado"
                )
            if "reporte_cierre" not in columnas_rep:
                cursor.execute(
                    "ALTER TABLE reporte ADD COLUMN reporte_cierre TEXT NULL AFTER fecha_resolucion"
                )
            tipo_estado = columnas_rep.get("estado", {}).get("Type", "")
            estados_reporte = (
                "Pendiente",
                "Confirmado",
                "En reparación",
                "En proceso",
                "Resuelto",
                "Reabierto",
                "Cancelado",
            )
            if (
                any(f"'{estado}'" not in tipo_estado for estado in estados_reporte)
                or "'Reportado'" in tipo_estado
            ):
                cursor.execute(
                    "ALTER TABLE reporte MODIFY COLUMN estado "
                    "ENUM('Reportado','Pendiente','Confirmado','En reparación',"
                    "'En proceso','Resuelto','Reabierto','Cancelado') "
                    "NOT NULL DEFAULT 'Pendiente'"
                )
                cursor.execute(
                    "UPDATE reporte SET estado = 'Pendiente' WHERE estado = 'Reportado'"
                )
                cursor.execute(
                    "ALTER TABLE reporte MODIFY COLUMN estado "
                    "ENUM('Pendiente','Confirmado','En reparación','En proceso','Resuelto','Reabierto','Cancelado') "
                    "NOT NULL DEFAULT 'Pendiente'"
                )
        except Exception:
            conexion.rollback()
            raise

        conexion.commit()
    except MySQLError:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def resolver_carnet_tecnico(correo_o_carnet: str) -> Optional[str]:
    """Obtiene el carnet_tecnico a partir del correo o del mismo carnet."""
    if not correo_o_carnet:
        return None
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT carnet_tecnico FROM tecnico WHERE correo = %s OR carnet_tecnico = %s LIMIT 1",
            (correo_o_carnet, correo_o_carnet)
        )
        fila = cursor.fetchone()
        return fila["carnet_tecnico"] if fila else correo_o_carnet
    except Exception:
        return correo_o_carnet
    finally:
        conexion.close()


def obtener_laboratorios() -> List[Dict[str, str]]:
    """Devuelve la lista de laboratorios disponibles."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id_laboratorio, nombre, ubicacion FROM laboratorio ORDER BY id_laboratorio")
        return cursor.fetchall()
    finally:
        conexion.close()


def obtener_categorias() -> List[Dict[str, str]]:
    """Devuelve la lista de categorías disponibles."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id_categoria, nombre, prioridad FROM categoria ORDER BY id_categoria")
        return cursor.fetchall()
    finally:
        conexion.close()


def _resolver_carnet_profesor(cursor, correo_o_carnet: Optional[str]) -> Optional[str]:
    """Obtiene el carnet del reportante (profesor, administrador o técnico)."""
    if correo_o_carnet:
        cursor.execute(
            "SELECT carnet_profesor FROM profesor WHERE correo = %s OR carnet_profesor = %s LIMIT 1",
            (correo_o_carnet, correo_o_carnet),
        )
        fila = cursor.fetchone()
        if fila:
            return fila["carnet_profesor"]

        # Si quien reporta es un Administrador o Técnico, sincronizar un registro espejo en profesor
        # (con correo interno para no interferir con el login por rol en auth.py)
        for tabla, col_carnet in (("administrador", "carnet_administrador"), ("tecnico", "carnet_tecnico")):
            cursor.execute(
                f"SELECT {col_carnet} AS carnet, nombres, apellidos, contrasena_hash "
                f"FROM {tabla} WHERE correo = %s OR {col_carnet} = %s LIMIT 1",
                (correo_o_carnet, correo_o_carnet),
            )
            usuario = cursor.fetchone()
            if usuario:
                carnet_usr = usuario["carnet"]
                correo_espejo = f"{carnet_usr.lower()}@interno.sigii"
                cursor.execute(
                    """
                    INSERT INTO profesor (carnet_profesor, nombres, apellidos, correo, contrasena_hash, estado_cuenta)
                    VALUES (%s, %s, %s, %s, %s, 'Activo')
                    ON DUPLICATE KEY UPDATE nombres = VALUES(nombres), apellidos = VALUES(apellidos)
                    """,
                    (carnet_usr, usuario["nombres"], usuario["apellidos"], correo_espejo, usuario["contrasena_hash"]),
                )
                return carnet_usr

    cursor.execute("SELECT carnet_profesor FROM profesor ORDER BY carnet_profesor LIMIT 1")
    fila = cursor.fetchone()
    return fila["carnet_profesor"] if fila else None


def _resolver_id_laboratorio(cursor, lab_nombre_o_id: str) -> str:
    """Busca o crea el id_laboratorio para el nombre o id dado."""
    cursor.execute(
        "SELECT id_laboratorio FROM laboratorio WHERE id_laboratorio = %s OR nombre = %s LIMIT 1",
        (lab_nombre_o_id, lab_nombre_o_id)
    )
    fila = cursor.fetchone()
    if fila:
        return fila["id_laboratorio"]

    cursor.execute("SELECT COUNT(*) AS total FROM laboratorio")
    total = cursor.fetchone()["total"]
    nuevo_id = f"LAB-{total + 1:02d}"
    cursor.execute(
        "INSERT INTO laboratorio (id_laboratorio, nombre, ubicacion) VALUES (%s, %s, %s)",
        (nuevo_id, lab_nombre_o_id, "Ubicación general")
    )
    return nuevo_id


def _resolver_id_categoria(cursor, cat_nombre_o_id: str, prioridad: str = "Media") -> str:
    """Busca o crea el id_categoria para el nombre o id dado."""
    cursor.execute(
        "SELECT id_categoria FROM categoria WHERE id_categoria = %s OR nombre = %s LIMIT 1",
        (cat_nombre_o_id, cat_nombre_o_id)
    )
    fila = cursor.fetchone()
    if fila:
        return fila["id_categoria"]

    cursor.execute("SELECT COUNT(*) AS total FROM categoria")
    total = cursor.fetchone()["total"]
    nuevo_id = f"CAT-{total + 1:02d}"
    prio_val = 'Crítica' if prioridad in ('Critica', 'Crítica') else (prioridad if prioridad in ('Baja', 'Media', 'Alta') else 'Media')
    cursor.execute(
        "INSERT INTO categoria (id_categoria, nombre, prioridad) VALUES (%s, %s, %s)",
        (nuevo_id, cat_nombre_o_id, prio_val)
    )
    return nuevo_id


def registrar_incidencia(correo_o_carnet: str, datos: dict, carnet_tecnico: Optional[str] = None) -> dict:
    """
    Registra una nueva incidencia en la tabla reporte vinculada al Gmail/carnet del profesor.
    Si se especifica carnet_tecnico o quien reporta es un técnico, la incidencia queda
    automáticamente asignada a dicho técnico en estado 'Confirmado'.
    """
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        carnet_profesor = _resolver_carnet_profesor(cursor, correo_o_carnet)
        if not carnet_profesor:
            return {
                "exito": False,
                "mensaje": "No se encontró ningún profesor registrado en la base de datos para asociar el reporte.",
                "id_reporte": None
            }

        # Resolver asignación de técnico
        carnet_tecnico_candidato = carnet_tecnico or datos.get("carnet_tecnico")
        carnet_tecnico_asignado = None

        if not carnet_tecnico_candidato:
            # Si quien reporta es un técnico, asignarle la incidencia por defecto
            cursor.execute(
                "SELECT carnet_tecnico FROM tecnico WHERE correo = %s OR carnet_tecnico = %s LIMIT 1",
                (correo_o_carnet, correo_o_carnet)
            )
            fila_tec = cursor.fetchone()
            if fila_tec:
                carnet_tecnico_asignado = fila_tec["carnet_tecnico"]
        else:
            cursor.execute(
                "SELECT carnet_tecnico FROM tecnico WHERE correo = %s OR carnet_tecnico = %s LIMIT 1",
                (carnet_tecnico_candidato, carnet_tecnico_candidato)
            )
            fila_tec = cursor.fetchone()
            if fila_tec:
                carnet_tecnico_asignado = fila_tec["carnet_tecnico"]
            else:
                carnet_tecnico_asignado = carnet_tecnico_candidato

        id_lab = _resolver_id_laboratorio(cursor, datos.get("laboratorio", "Laboratorio FC 1"))
        prioridad = datos.get("prioridad", "Media")
        id_cat = _resolver_id_categoria(cursor, datos.get("tipo_problema", "Otro problema"), prioridad)

        equipo = datos.get("equipo", "PC-01")
        desc_cruda = datos.get("descripcion", "").strip()

        if re.match(r"^\[.*?\]", desc_cruda):
            descripcion_final = desc_cruda
        else:
            descripcion_final = f"[{equipo}] {desc_cruda}" if equipo else desc_cruda

        if len(descripcion_final) > 255:
            descripcion_final = descripcion_final[:252] + "..."

        fecha_str = datos.get("fecha")
        if isinstance(fecha_str, str) and fecha_str:
            try:
                if len(fecha_str) == 10:
                    ahora = datetime.now()
                    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").replace(
                        hour=ahora.hour, minute=ahora.minute, second=ahora.second
                    )
                else:
                    fecha_dt = datetime.fromisoformat(fecha_str)
            except Exception:
                fecha_dt = datetime.now()
        else:
            fecha_dt = datetime.now()

        if carnet_tecnico_asignado:
            estado_inicial = datos.get("estado") or "Confirmado"
            fecha_confirmado = fecha_dt
        else:
            estado_inicial = datos.get("estado") or "Pendiente"
            fecha_confirmado = None

        cursor.execute(
            """
            INSERT INTO reporte
                (carnet_profesor, carnet_tecnico, id_laboratorio, id_categoria, fecha, descripcion, estado, fecha_confirmado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (carnet_profesor, carnet_tecnico_asignado, id_lab, id_cat, fecha_dt, descripcion_final, estado_inicial, fecha_confirmado)
        )

        id_reporte = cursor.lastrowid
        conexion.commit()

        return {
            "exito": True,
            "mensaje": "Incidencia registrada correctamente en la base de datos.",
            "id_reporte": id_reporte
        }
    except MySQLError as error:
        conexion.rollback()
        return {
            "exito": False,
            "mensaje": f"Error al guardar en base de datos: {error}",
            "id_reporte": None
        }
    finally:
        conexion.close()


def _extraer_equipo_y_descripcion(desc: str) -> tuple[str, str]:
    if not desc:
        return "-", ""
    match = re.match(r"^\[(.*?)\]\s*(.*)$", desc)
    if match:
        return match.group(1), match.group(2)
    return "-", desc


def obtener_incidencias_por_profesor(correo_o_carnet: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene los reportes generados por un profesor específico filtrando por su Gmail o carnet.
    """
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        carnet_profesor = None
        if correo_o_carnet:
            carnet_profesor = _resolver_carnet_profesor(cursor, correo_o_carnet)

        query = """
            SELECT 
                r.id_reporte,
                r.fecha,
                r.fecha_confirmado,
                r.fecha_resolucion,
                r.reporte_cierre,
                r.carnet_tecnico,
                r.descripcion,
                r.estado,
                l.nombre AS laboratorio_nombre,
                l.id_laboratorio,
                c.nombre AS categoria_nombre,
                c.prioridad,
                p.carnet_profesor,
                p.correo AS profesor_correo,
                CONCAT(p.nombres, ' ', p.apellidos) AS profesor_nombre,
                CONCAT(t.nombres, ' ', t.apellidos) AS tecnico_nombre
            FROM reporte r
            INNER JOIN laboratorio l ON r.id_laboratorio = l.id_laboratorio
            INNER JOIN categoria c ON r.id_categoria = c.id_categoria
            INNER JOIN profesor p ON r.carnet_profesor = p.carnet_profesor
            LEFT JOIN tecnico t ON r.carnet_tecnico = t.carnet_tecnico
        """
        params = ()
        if carnet_profesor:
            query += " WHERE r.carnet_profesor = %s"
            params = (carnet_profesor,)

        query += " ORDER BY r.fecha DESC, r.id_reporte DESC"

        cursor.execute(query, params)
        filas = cursor.fetchall()

        resultado = []
        for fila in filas:
            equipo, desc_limpia = _extraer_equipo_y_descripcion(fila["descripcion"])
            fecha_val = fila["fecha"]
            fecha_formateada = fecha_val.strftime("%Y-%m-%d") if isinstance(fecha_val, datetime) else str(fecha_val)

            tec_nom = fila["tecnico_nombre"].strip() if fila.get("tecnico_nombre") else None
            tecnico_display = tec_nom if tec_nom else "Sin asignar"
            resultado.append({
                "id_reporte": fila["id_reporte"],
                "carnet_tecnico": fila.get("carnet_tecnico"),
                "laboratorio": fila["laboratorio_nombre"],
                "id_laboratorio": fila["id_laboratorio"],
                "equipo": equipo,
                "tipo_problema": fila["categoria_nombre"],
                "prioridad": fila["prioridad"],
                "estado": fila["estado"],
                "fecha": fecha_formateada,
                "fecha_confirmado": str(fila.get("fecha_confirmado") or ""),
                "fecha_resolucion": str(fila.get("fecha_resolucion") or ""),
                "reporte_cierre": fila.get("reporte_cierre"),
                "descripcion": desc_limpia,
                "profesor": fila["profesor_nombre"],
                "profesor_nombre": fila["profesor_nombre"],
                "correo": fila["profesor_correo"],
                "tecnico": tecnico_display,
                "tecnico_nombre": tecnico_display
            })

        return resultado
    finally:
        conexion.close()


listar_incidencias_del_maestro = obtener_incidencias_por_profesor


def obtener_todas_las_incidencias_admin() -> List[Dict[str, Any]]:
    """Devuelve todas las incidencias del sistema con historial completo para el Administrador."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        query = """
            SELECT 
                r.id_reporte,
                r.fecha,
                r.fecha_confirmado,
                r.fecha_resolucion,
                r.reporte_cierre,
                r.descripcion,
                r.estado,
                r.carnet_tecnico,
                r.carnet_profesor,
                l.id_laboratorio,
                l.nombre AS laboratorio_nombre,
                c.id_categoria,
                c.nombre AS categoria_nombre,
                c.prioridad,
                p.correo AS profesor_correo,
                CONCAT(p.nombres, ' ', p.apellidos) AS profesor_nombre,
                CONCAT(t.nombres, ' ', t.apellidos) AS tecnico_nombre
            FROM reporte r
            INNER JOIN laboratorio l ON r.id_laboratorio = l.id_laboratorio
            INNER JOIN categoria c ON r.id_categoria = c.id_categoria
            LEFT JOIN profesor p ON r.carnet_profesor = p.carnet_profesor
            LEFT JOIN tecnico t ON r.carnet_tecnico = t.carnet_tecnico
            ORDER BY r.fecha DESC, r.id_reporte DESC
        """
        cursor.execute(query)
        filas = cursor.fetchall() or []

        resultado = []
        for fila in filas:
            equipo, desc_limpia = _extraer_equipo_y_descripcion(fila["descripcion"])
            fecha_val = fila["fecha"]
            fecha_formateada = fecha_val.strftime("%Y-%m-%d %H:%M") if isinstance(fecha_val, datetime) else str(fecha_val)
            
            f_conf = fila["fecha_confirmado"]
            f_conf_str = f_conf.strftime("%Y-%m-%d %H:%M") if isinstance(f_conf, datetime) else (str(f_conf) if f_conf else None)
            
            f_res = fila["fecha_resolucion"]
            f_res_str = f_res.strftime("%Y-%m-%d %H:%M") if isinstance(f_res, datetime) else (str(f_res) if f_res else None)

            # Cálculo de vencimiento (+5 días desde fecha_confirmado)
            vencida = False
            if fila["estado"] in ("Confirmado", "En reparación", "En proceso") and isinstance(f_conf, datetime):
                dias = (datetime.now() - f_conf).total_seconds() / 86400.0
                vencida = dias > 5.0

            resultado.append({
                "id_reporte": fila["id_reporte"],
                "laboratorio": fila["laboratorio_nombre"],
                "id_laboratorio": fila["id_laboratorio"],
                "equipo": equipo,
                "tipo_problema": fila["categoria_nombre"],
                "prioridad": fila["prioridad"],
                "estado": fila["estado"],
                "fecha": fecha_formateada,
                "fecha_dt": fecha_val,
                "fecha_confirmado": f_conf_str,
                "fecha_confirmado_dt": f_conf,
                "fecha_resolucion": f_res_str,
                "reporte_cierre": fila["reporte_cierre"],
                "descripcion": desc_limpia,
                "profesor": fila["profesor_nombre"] or "Profesor",
                "profesor_nombre": fila["profesor_nombre"] or "Profesor",
                "correo": fila["profesor_correo"] or "",
                "tecnico": fila["tecnico_nombre"] if fila["tecnico_nombre"] else "Sin asignar",
                "tecnico_nombre": fila["tecnico_nombre"] if fila["tecnico_nombre"] else "Sin asignar",
                "carnet_tecnico": fila["carnet_tecnico"],
                "vencida": vencida,
            })
        return resultado
    finally:
        conexion.close()


def obtener_ultimas_incidencias(limite: int = 10) -> List[Dict[str, Any]]:
    """Obtiene las incidencias más recientes de todo el sistema."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        query = """
            SELECT 
                r.id_reporte,
                r.fecha,
                r.descripcion,
                r.estado,
                l.nombre AS laboratorio_nombre,
                c.nombre AS categoria_nombre,
                c.prioridad,
                CONCAT(p.nombres, ' ', p.apellidos) AS profesor_nombre,
                CONCAT(t.nombres, ' ', t.apellidos) AS tecnico_nombre
            FROM reporte r
            INNER JOIN laboratorio l ON r.id_laboratorio = l.id_laboratorio
            INNER JOIN categoria c ON r.id_categoria = c.id_categoria
            INNER JOIN profesor p ON r.carnet_profesor = p.carnet_profesor
            LEFT JOIN tecnico t ON r.carnet_tecnico = t.carnet_tecnico
            ORDER BY r.fecha DESC, r.id_reporte DESC
            LIMIT %s
        """
        cursor.execute(query, (limite,))
        filas = cursor.fetchall()

        resultado = []
        for fila in filas:
            equipo, desc_limpia = _extraer_equipo_y_descripcion(fila["descripcion"])
            fecha_val = fila["fecha"]
            fecha_formateada = fecha_val.strftime("%Y-%m-%d") if isinstance(fecha_val, datetime) else str(fecha_val)

            resultado.append({
                "id_reporte": fila["id_reporte"],
                "laboratorio": fila["laboratorio_nombre"],
                "equipo": equipo,
                "tipo_problema": fila["categoria_nombre"],
                "prioridad": fila["prioridad"],
                "estado": fila["estado"],
                "tecnico": fila["tecnico_nombre"] if fila["tecnico_nombre"] else "Sin asignar",
                "fecha": fecha_formateada,
                "profesor": fila["profesor_nombre"],
                "descripcion": desc_limpia
            })

        return resultado
    finally:
        conexion.close()


def obtener_ultimos_reportes_cierre(limite: int = 5) -> List[str]:
    """Obtiene los últimos reportes resueltos o cerrados por técnicos."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        query = """
            SELECT 
                r.id_reporte,
                r.fecha,
                r.fecha_resolucion,
                r.descripcion,
                l.nombre AS laboratorio_nombre,
                CONCAT(t.nombres, ' ', t.apellidos) AS tecnico_nombre
            FROM reporte r
            INNER JOIN laboratorio l ON r.id_laboratorio = l.id_laboratorio
            LEFT JOIN tecnico t ON r.carnet_tecnico = t.carnet_tecnico
            WHERE r.estado = 'Resuelto'
            ORDER BY COALESCE(r.fecha_resolucion, r.fecha) DESC
            LIMIT %s
        """
        cursor.execute(query, (limite,))
        filas = cursor.fetchall()

        reportes = []
        for f in filas:
            equipo, _ = _extraer_equipo_y_descripcion(f["descripcion"])
            tecnico = f["tecnico_nombre"] if f["tecnico_nombre"] else "Técnico de guardia"
            fecha_resol = f["fecha_resolucion"] or f["fecha"]
            fecha_str = fecha_resol.strftime("%d/%m/%Y") if isinstance(fecha_resol, datetime) else str(fecha_resol)
            reportes.append(f"{tecnico}  –  {f['laboratorio_nombre']} / {equipo}  –  {fecha_str}")

        return reportes
    finally:
        conexion.close()


def obtener_resumen_estadisticas() -> Dict[str, Any]:
    """Resume laboratorios y equipos identificables en los reportes guardados.

    El esquema no tiene una tabla de inventario de computadoras ni un estado
    operativo del laboratorio. Por eso se cuentan solo entidades respaldadas
    por la base: laboratorios registrados y equipos mencionados en reportes.
    """
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM laboratorio")
        total_labs = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT CASE WHEN r.estado IN ('Pendiente', 'Confirmado', 'En reparación', 'Reabierto')
                    THEN r.id_laboratorio END) AS laboratorios_con_incidencias,
                COUNT(DISTINCT CASE WHEN r.descripcion LIKE '[%]%' 
                    THEN SUBSTRING_INDEX(SUBSTRING_INDEX(r.descripcion, ']', 1), '[', -1) END) AS equipos_identificados,
                COUNT(DISTINCT CASE WHEN r.estado IN ('Pendiente', 'Confirmado', 'En reparación', 'Reabierto')
                    AND r.descripcion LIKE '[%]%'
                    THEN SUBSTRING_INDEX(SUBSTRING_INDEX(r.descripcion, ']', 1), '[', -1) END) AS equipos_con_incidencias
            FROM reporte r
            """
        )
        resumen = cursor.fetchone()

        labs_con_inc = resumen["laboratorios_con_incidencias"] or 0
        equipos_id = resumen["equipos_identificados"] or 0
        equipos_con_inc = resumen["equipos_con_incidencias"] or 0

        return {
            "laboratorios_con_incidencias": labs_con_inc,
            "laboratorios_operativos": max(0, total_labs - labs_con_inc),
            "laboratorios_total": total_labs,
            "equipos_identificados": equipos_id,
            "equipos_con_incidencias": equipos_con_inc,
            "equipos_operativos": max(0, equipos_id - equipos_con_inc),
            "equipos_fuera": equipos_con_inc,
        }
    finally:
        conexion.close()

def actualizar_estado_incidencia(id_reporte: int, nuevo_estado: str) -> dict:
    """Aplica únicamente transiciones válidas del flujo de trabajo técnico."""
    transiciones = {
        "Pendiente": {"Confirmado"},
        "Pendiente": {"Confirmado"},
        "Confirmado": {"En reparación"},
        "En reparación": {"Resuelto"},
        "Resuelto": {"Confirmado"},
    }

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT estado FROM reporte WHERE id_reporte = %s",
            (id_reporte,),
        )
        fila = cursor.fetchone()

        if not fila:
            return {"exito": False, "mensaje": "La incidencia ya no existe."}

        estado_actual = fila["estado"]
        if nuevo_estado not in transiciones.get(estado_actual, set()):
            return {
                "exito": False,
                "mensaje": f"No se permite cambiar de {estado_actual} a {nuevo_estado}.",
            }

        if nuevo_estado == "Resuelto":
            cursor.execute(
                """
                UPDATE reporte
                SET estado = %s, fecha_resolucion = NOW()
                WHERE id_reporte = %s AND estado = %s
                """,
                (nuevo_estado, id_reporte, estado_actual),
            )
        else:
            cursor.execute(
                """
                UPDATE reporte
                SET estado = %s, fecha_resolucion = NULL
                WHERE id_reporte = %s AND estado = %s
                """,
                (nuevo_estado, id_reporte, estado_actual),
            )

        if cursor.rowcount == 0:
            conexion.rollback()
            return {
                "exito": False,
                "mensaje": "La incidencia cambió mientras intentabas actualizarla. Recarga la cola.",
            }

        conexion.commit()
        return {"exito": True, "mensaje": "Estado actualizado correctamente."}
    except MySQLError as error:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error en la base de datos: {error}"}
    finally:
        conexion.close()


def obtener_tecnicos() -> List[Dict[str, Any]]:
    """Devuelve la lista de técnicos disponibles para asignación."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT carnet_tecnico, CONCAT(nombres, ' ', apellidos) AS nombre_completo, correo
                FROM tecnico
                WHERE estado_cuenta = 'Activo'
                ORDER BY nombres ASC, apellidos ASC
                """
            )
            res = cursor.fetchall()
            if res:
                return res
        except Exception:
            pass

        cursor.execute(
            """
            SELECT carnet_tecnico, CONCAT(nombres, ' ', apellidos) AS nombre_completo, correo
            FROM tecnico
            ORDER BY nombres ASC, apellidos ASC
            """
        )
        return cursor.fetchall()
    except Exception as err:
        print(f"Error al obtener técnicos: {err}")
        return []
    finally:
        conexion.close()


def actualizar_incidencia(id_reporte: int, datos: dict) -> dict:
    """Actualiza los datos completos de una incidencia en la base de datos MySQL."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        id_lab = _resolver_id_laboratorio(cursor, datos.get("laboratorio", "Laboratorio FC 1"))
        prioridad = datos.get("prioridad", "Media")
        id_cat = _resolver_id_categoria(cursor, datos.get("tipo_problema", "Otro problema"), prioridad)

        equipo = datos.get("equipo", "PC-01")
        desc_cruda = datos.get("descripcion", "").strip()

        if re.match(r"^\[.*?\]", desc_cruda):
            descripcion_final = desc_cruda
        else:
            descripcion_final = f"[{equipo}] {desc_cruda}" if equipo else desc_cruda

        if len(descripcion_final) > 255:
            descripcion_final = descripcion_final[:252] + "..."

        nuevo_estado = datos.get("estado", "Pendiente")

        # Actualizar en tabla categoria la prioridad si fue modificada
        cursor.execute("UPDATE categoria SET prioridad = %s WHERE id_categoria = %s", (prioridad, id_cat))

        actualizar_tecnico = "carnet_tecnico" in datos
        carnet_tecnico_val = datos.get("carnet_tecnico")
        if carnet_tecnico_val == "" or carnet_tecnico_val is None:
            carnet_tecnico_val = None

        if nuevo_estado == "Resuelto":
            if actualizar_tecnico:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        carnet_tecnico = %s, fecha_resolucion = COALESCE(fecha_resolucion, NOW())
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, carnet_tecnico_val, id_reporte))
            else:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        fecha_resolucion = COALESCE(fecha_resolucion, NOW())
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, id_reporte))
        elif nuevo_estado in ("Confirmado", "En reparación", "En reparacion", "En proceso"):
            if actualizar_tecnico:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        carnet_tecnico = %s, fecha_confirmado = COALESCE(fecha_confirmado, NOW()), fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, carnet_tecnico_val, id_reporte))
            else:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        fecha_confirmado = COALESCE(fecha_confirmado, NOW()), fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, id_reporte))
        elif nuevo_estado == "Pendiente":
            if actualizar_tecnico:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        carnet_tecnico = %s, fecha_confirmado = NULL, fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, carnet_tecnico_val, id_reporte))
            else:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        fecha_confirmado = NULL, fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, id_reporte))
        else:
            if actualizar_tecnico:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, 
                        carnet_tecnico = %s, fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, carnet_tecnico_val, id_reporte))
            else:
                query = """
                    UPDATE reporte 
                    SET id_laboratorio = %s, id_categoria = %s, descripcion = %s, estado = %s, fecha_resolucion = NULL
                    WHERE id_reporte = %s
                """
                cursor.execute(query, (id_lab, id_cat, descripcion_final, nuevo_estado, id_reporte))

        conexion.commit()

        return {
            "exito": True,
            "mensaje": "Incidencia actualizada correctamente en la base de datos."
        }
    except MySQLError as error:
        conexion.rollback()
        return {
            "exito": False,
            "mensaje": f"Error al actualizar en la base de datos: {error}"
        }
    finally:
        conexion.close()


def eliminar_incidencia(id_reporte: int) -> dict:
    """Elimina una incidencia de la base de datos MySQL."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM reporte WHERE id_reporte = %s", (id_reporte,))
        conexion.commit()
        return {"exito": True, "mensaje": "Incidencia cancelada y eliminada correctamente."}
    except MySQLError as error:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error al eliminar en la base de datos: {error}"}
    finally:
        conexion.close()


def eliminar_incidencias(ids_reportes: list[int]) -> dict:
    """Elimina una o varias incidencias de la base de datos MySQL."""
    if not ids_reportes:
        return {"exito": False, "mensaje": "No se seleccionó ninguna incidencia para eliminar."}

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        format_strings = ", ".join(["%s"] * len(ids_reportes))
        cursor.execute(f"DELETE FROM reporte WHERE id_reporte IN ({format_strings})", tuple(ids_reportes))
        conexion.commit()
        filas_afectadas = cursor.rowcount
        return {
            "exito": True,
            "mensaje": f"{filas_afectadas} incidencia(s) eliminada(s) correctamente.",
            "eliminadas": filas_afectadas,
        }
    except MySQLError as error:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error al eliminar en la base de datos: {error}"}
    finally:
        conexion.close()

def obtener_incidencias_disponibles() -> list[dict]:
    """Incidencias visibles en el flujo técnico, incluidas las resueltas que pueden reabrirse."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                r.id_reporte, r.estado, r.descripcion, r.fecha,
                r.fecha_confirmado, r.carnet_tecnico,
                lab.id_laboratorio, lab.nombre AS laboratorio,
                cat.nombre AS tipo_problema, cat.prioridad,
                t.nombres AS tecnico_nombres, t.apellidos AS tecnico_apellidos
            FROM reporte r
            JOIN laboratorio lab ON lab.id_laboratorio = r.id_laboratorio
            JOIN categoria cat ON cat.id_categoria = r.id_categoria
            LEFT JOIN tecnico t ON t.carnet_tecnico = r.carnet_tecnico
            WHERE r.estado IN ('Pendiente', 'Confirmado', 'En reparación', 'En proceso', 'Resuelto')
            ORDER BY r.fecha DESC, r.id_reporte DESC
            """
        )
        filas = cursor.fetchall()
        for fila in filas:
            if fila.get("tecnico_nombres"):
                nom = f"{fila['tecnico_nombres']} {fila['tecnico_apellidos']}".strip()
                fila["tecnico_nombre"] = nom
                fila["tecnico"] = nom
            else:
                fila["tecnico_nombre"] = "Sin asignar"
                fila["tecnico"] = "Sin asignar"
        return filas
    finally:
        conexion.close()


def tomar_tarea(id_reporte: int, carnet_o_correo_tecnico: str) -> dict:
    """Pendiente -> Confirmado. Asignación atómica del técnico a la incidencia."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        if not carnet_o_correo_tecnico:
            return {"exito": False, "mensaje": "No se pudo identificar al técnico conectado."}

        cursor.execute(
            "SELECT carnet_tecnico FROM tecnico WHERE carnet_tecnico = %s OR correo = %s LIMIT 1",
            (carnet_o_correo_tecnico, carnet_o_correo_tecnico)
        )
        fila_t = cursor.fetchone()
        if not fila_t:
            return {"exito": False, "mensaje": "El usuario conectado no tiene un técnico registrado."}
        carnet_tecnico = fila_t["carnet_tecnico"]

        cursor.execute(
            """
            UPDATE reporte
            SET carnet_tecnico = %s,
                estado = 'Confirmado',
                fecha_confirmado = NOW()
            WHERE id_reporte = %s
              AND (carnet_tecnico IS NULL OR carnet_tecnico = '')
              AND estado IN ('Pendiente')
            """,
            (carnet_tecnico, id_reporte),
        )
        conexion.commit()

        if cursor.rowcount == 0:
            return {
                "exito": False,
                "mensaje": "Esta incidencia ya fue tomada por otro técnico o cambió de estado.",
            }
        return {"exito": True}
    except Exception as err:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error al tomar la tarea: {err}"}
    finally:
        conexion.close()


def avanzar_estado_tecnico(id_reporte: int, carnet_o_correo_tecnico: str, nuevo_estado: str) -> dict:
    """Cambia el estado de una incidencia asignada al técnico autenticado."""
    transiciones = {
        "Confirmado": {"En reparación"},
        "En reparación": {"Resuelto"},
        "En proceso": {"Resuelto"},
        "Resuelto": {"Confirmado"},
    }
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT carnet_tecnico FROM tecnico WHERE carnet_tecnico = %s OR correo = %s LIMIT 1",
            (carnet_o_correo_tecnico, carnet_o_correo_tecnico),
        )
        tecnico = cursor.fetchone()
        if not tecnico:
            return {"exito": False, "mensaje": "No se pudo identificar al técnico conectado."}

        carnet = tecnico["carnet_tecnico"]
        cursor.execute(
            "SELECT estado FROM reporte WHERE id_reporte = %s AND carnet_tecnico = %s",
            (id_reporte, carnet),
        )
        reporte = cursor.fetchone()
        if not reporte:
            return {"exito": False, "mensaje": "La incidencia no está asignada a tu usuario."}

        estado_actual = reporte["estado"]
        if nuevo_estado not in transiciones.get(estado_actual, set()):
            return {
                "exito": False,
                "mensaje": f"No se permite cambiar de {estado_actual} a {nuevo_estado}.",
            }

        if nuevo_estado == "Resuelto":
            cursor.execute(
                "UPDATE reporte SET estado = %s, fecha_resolucion = NOW() "
                "WHERE id_reporte = %s AND carnet_tecnico = %s AND estado = %s",
                (nuevo_estado, id_reporte, carnet, estado_actual),
            )
        else:
            cursor.execute(
                "UPDATE reporte SET estado = %s, fecha_resolucion = NULL "
                "WHERE id_reporte = %s AND carnet_tecnico = %s AND estado = %s",
                (nuevo_estado, id_reporte, carnet, estado_actual),
            )
        if cursor.rowcount != 1:
            conexion.rollback()
            return {"exito": False, "mensaje": "La incidencia cambió. Actualiza la cola e inténtalo otra vez."}

        conexion.commit()
        return {"exito": True, "mensaje": "Estado actualizado correctamente."}
    except MySQLError as error:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error en la base de datos: {error}"}
    finally:
        conexion.close()


def obtener_cola_asignaciones_por_tecnico(correo_o_carnet: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene los reportes asignados a un técnico específico (por correo o carnet).
    """
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        carnet_tecnico = None
        if correo_o_carnet:
            cursor.execute(
                "SELECT carnet_tecnico FROM tecnico WHERE correo = %s OR carnet_tecnico = %s LIMIT 1",
                (correo_o_carnet, correo_o_carnet)
            )
            fila_t = cursor.fetchone()
            if fila_t:
                carnet_tecnico = fila_t["carnet_tecnico"]
            else:
                carnet_tecnico = correo_o_carnet

        query = """
            SELECT 
                r.id_reporte,
                r.fecha,
                r.descripcion,
                r.estado,
                r.fecha_resolucion,
                r.carnet_tecnico,
                l.nombre AS laboratorio_nombre,
                l.id_laboratorio,
                c.nombre AS categoria_nombre,
                c.prioridad,
                p.carnet_profesor,
                p.correo AS profesor_correo,
                CONCAT(p.nombres, ' ', p.apellidos) AS profesor_nombre,
                CONCAT(t.nombres, ' ', t.apellidos) AS tecnico_nombre
            FROM reporte r
            INNER JOIN laboratorio l ON r.id_laboratorio = l.id_laboratorio
            INNER JOIN categoria c ON r.id_categoria = c.id_categoria
            LEFT JOIN profesor p ON r.carnet_profesor = p.carnet_profesor
            LEFT JOIN tecnico t ON r.carnet_tecnico = t.carnet_tecnico
        """
        query += " WHERE r.estado != 'Cancelado'"
        params = ()

        query += " ORDER BY r.fecha DESC, r.id_reporte DESC"

        cursor.execute(query, params)
        filas = cursor.fetchall()

        resultado = []
        for fila in filas:
            equipo, desc_limpia = _extraer_equipo_y_descripcion(fila["descripcion"])
            fecha_val = fila["fecha"]
            fecha_formateada = fecha_val.strftime("%Y-%m-%d") if isinstance(fecha_val, datetime) else str(fecha_val)

            tec_nom = fila["tecnico_nombre"].strip() if fila.get("tecnico_nombre") else None
            tecnico_display = tec_nom if tec_nom else "Sin asignar"
            resultado.append({
                "id_reporte": fila["id_reporte"],
                "carnet_tecnico": fila["carnet_tecnico"],
                "laboratorio": fila["laboratorio_nombre"],
                "id_laboratorio": fila["id_laboratorio"],
                "equipo": equipo,
                "tipo_problema": fila["categoria_nombre"],
                "prioridad": fila["prioridad"],
                "estado": fila["estado"],
                "fecha": fecha_formateada,
                "descripcion": desc_limpia,
                "profesor": fila["profesor_nombre"] or "Profesor",
                "profesor_nombre": fila["profesor_nombre"] or "Profesor",
                "correo": fila["profesor_correo"] or "",
                "tecnico": tecnico_display,
                "tecnico_nombre": tecnico_display
            })

        return resultado
    finally:
        conexion.close()


# =============================================================================
# FUNCIONES NOMBRADAS DEL FLUJO TÉCNICO
# Regla: cada transición tiene su propia función con nombre de negocio.
# Prohibido usar actualizar_estado genérico para estas transiciones.
# =============================================================================

def tomar_incidencia(id_reporte: int, carnet_tecnico: str) -> dict:
    """Pendiente → Confirmado. Asignación atómica: sin SELECT previo.

    La precondición (estado = 'Pendiente' AND carnet_tecnico IS NULL) va
    en el WHERE del UPDATE. Si rowcount == 0, otro técnico ganó la carrera.

    Devuelve:
        {"exito": True}  — tomada correctamente.
        {"exito": False, "motivo": "carrera" | "params", "mensaje": str}
    """
    if not id_reporte or not carnet_tecnico:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Faltan parámetros: id_reporte o carnet_tecnico.",
        }

    carnet_valido = resolver_carnet_tecnico(carnet_tecnico) or carnet_tecnico

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE reporte
            SET carnet_tecnico  = %s,
                estado          = 'Confirmado',
                fecha_confirmado = NOW()
            WHERE id_reporte      = %s
              AND carnet_tecnico  IS NULL
              AND estado          = 'Pendiente'
            """,
            (carnet_valido, id_reporte),
        )
        if cursor.rowcount == 1:
            conexion.commit()
            return {"exito": True}

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "carrera",
            "mensaje": "Esta incidencia ya fue tomada por otro técnico.",
        }
    except MySQLError as err:
        conexion.rollback()
        return {
            "exito": False,
            "motivo": "db_error",
            "mensaje": f"Error de base de datos: {err}",
        }
    finally:
        conexion.close()


def iniciar_reparacion(id_reporte: int, carnet_tecnico: str) -> dict:
    """Confirmado → En reparación. Solo si la incidencia pertenece a este técnico.

    Devuelve:
        {"exito": True}
        {"exito": False, "motivo": str, "mensaje": str}
    """
    if not id_reporte or not carnet_tecnico:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Faltan parámetros: id_reporte o carnet_tecnico.",
        }

    carnet_valido = resolver_carnet_tecnico(carnet_tecnico) or carnet_tecnico

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE reporte
            SET estado          = 'En reparación',
                fecha_resolucion = NULL
            WHERE id_reporte    = %s
              AND carnet_tecnico = %s
              AND estado        = 'Confirmado'
            """,
            (id_reporte, carnet_valido),
        )
        if cursor.rowcount == 1:
            conexion.commit()
            return {"exito": True}

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "precondicion",
            "mensaje": (
                "No se pudo iniciar la reparación. "
                "Verifica que la incidencia esté en estado 'Confirmado' "
                "y esté asignada a tu usuario."
            ),
        }
    except MySQLError as err:
        conexion.rollback()
        return {
            "exito": False,
            "motivo": "db_error",
            "mensaje": f"Error de base de datos: {err}",
        }
    finally:
        conexion.close()


def marcar_resuelta(id_reporte: int, carnet_tecnico: str, reporte_cierre: str) -> dict:
    """En reparación → Resuelto. Solo si la incidencia pertenece a este técnico.

    Args:
        id_reporte: identificador de la incidencia.
        carnet_tecnico: carnet del técnico autenticado.
        reporte_cierre: texto del reporte de cierre (obligatorio, max 1000 chars).

    Devuelve:
        {"exito": True}
        {"exito": False, "motivo": str, "mensaje": str}
    """
    if not id_reporte or not carnet_tecnico:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Faltan parámetros: id_reporte o carnet_tecnico.",
        }
    if not reporte_cierre or not reporte_cierre.strip():
        return {
            "exito": False,
            "motivo": "reporte_vacio",
            "mensaje": "El reporte de cierre no puede estar vacío.",
        }

    carnet_valido = resolver_carnet_tecnico(carnet_tecnico) or carnet_tecnico
    reporte_cierre_final = reporte_cierre.strip()[:1000]

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE reporte
            SET estado           = 'Resuelto',
                fecha_resolucion = NOW(),
                reporte_cierre   = %s
            WHERE id_reporte     = %s
              AND carnet_tecnico  = %s
              AND estado         = 'En reparación'
            """,
            (reporte_cierre_final, id_reporte, carnet_valido),
        )
        if cursor.rowcount == 1:
            conexion.commit()
            return {"exito": True}

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "precondicion",
            "mensaje": (
                "No se pudo marcar como resuelta. "
                "Verifica que la incidencia esté 'En reparación' "
                "y asignada a tu usuario."
            ),
        }
    except MySQLError as err:
        conexion.rollback()
        return {
            "exito": False,
            "motivo": "db_error",
            "mensaje": f"Error de base de datos: {err}",
        }
    finally:
        conexion.close()


def reasignar_incidencia(id_reporte: int, nuevo_carnet_tecnico: str) -> dict:
    """Reasigna una incidencia a otro técnico registrado en el sistema.

    Solo permite técnicos registrados en la tabla 'tecnico'.
    """
    if not id_reporte or not nuevo_carnet_tecnico:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Parámetros incompletos para reasignar la incidencia.",
        }

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        # Verificar que el nuevo técnico existe y está registrado en la tabla tecnico
        cursor.execute(
            """
            SELECT carnet_tecnico, CONCAT(nombres, ' ', apellidos) AS nombre_completo
            FROM tecnico
            WHERE (carnet_tecnico = %s OR correo = %s)
            LIMIT 1
            """,
            (nuevo_carnet_tecnico, nuevo_carnet_tecnico),
        )
        tec = cursor.fetchone()
        if not tec:
            return {
                "exito": False,
                "motivo": "no_registrado",
                "mensaje": "El técnico seleccionado no está registrado en el sistema.",
            }

        carnet_real = tec["carnet_tecnico"]
        nombre_tec = tec["nombre_completo"].strip() or carnet_real

        cursor.execute(
            "SELECT id_reporte, estado, carnet_tecnico FROM reporte WHERE id_reporte = %s",
            (id_reporte,),
        )
        rep = cursor.fetchone()
        if not rep:
            return {"exito": False, "motivo": "no_existe", "mensaje": "La incidencia no existe."}

        estado_actual = rep["estado"]
        # Si la incidencia estaba en estado Pendiente, al reasignarla pasa a Confirmado
        if estado_actual == "Pendiente":
            cursor.execute(
                """
                UPDATE reporte
                SET carnet_tecnico = %s,
                    estado = 'Confirmado',
                    fecha_confirmado = COALESCE(fecha_confirmado, NOW())
                WHERE id_reporte = %s
                """,
                (carnet_real, id_reporte),
            )
        else:
            cursor.execute(
                """
                UPDATE reporte
                SET carnet_tecnico = %s
                WHERE id_reporte = %s
                """,
                (carnet_real, id_reporte),
            )

        conexion.commit()
        return {
            "exito": True,
            "mensaje": f"Incidencia #{id_reporte} reasignada exitosamente a {nombre_tec}.",
            "carnet_tecnico": carnet_real,
            "tecnico_nombre": nombre_tec,
        }
    except Exception as err:
        conexion.rollback()
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error al reasignar incidencia: {err}"}
    finally:
        conexion.close()


# Consolidado desde services/cuenta_service.py: gestion de cuentas.
# services/cuenta_service.py
# -*- coding: utf-8 -*-
"""Capa de datos para la gestión y aprobación de cuentas por el Administrador.

Responsabilidad:
    - Listar cuentas por rol (Docente, Técnico, Administrador).
    - Aprobar cuentas pendientes (UPDATE condicionado a 'Pendiente').
    - Rechazar cuentas pendientes (DELETE condicionado a 'Pendiente').
    - Cambiar estado Activo ↔ Inactivo validando auto-desactivación y último admin.
    - Seguridad: Lista blanca de tablas/columnas, consultas parametrizadas (%s),
      sin exponer contrasena_hash ni f-strings con datos de usuario.
"""



logger_cuentas = logging.getLogger(__name__)

# Lista blanca estricta para evitar inyección SQL o acceso a tablas no autorizadas.
TABLAS_ROL_WHITELIST = {
    "Docente": ("profesor", "carnet_profesor"),
    "Técnico": ("tecnico", "carnet_tecnico"),
    "Administrador": ("administrador", "carnet_administrador"),
}

ALIAS_ROL = {
    "docente": "Docente",
    "docentes": "Docente",
    "profesor": "Docente",
    "profesores": "Docente",
    "tecnico": "Técnico",
    "técnico": "Técnico",
    "tecnicos": "Técnico",
    "técnicos": "Técnico",
    "administrador": "Administrador",
    "administradores": "Administrador",
    "admin": "Administrador",
}


def _resolver_rol(rol_nombre: str) -> Optional[tuple[str, str, str]]:
    """Devuelve (rol_estandar, nombre_tabla, columna_pk) o None si no es válido."""
    if not rol_nombre:
        return None
    rol_clave = rol_nombre.strip().lower()
    rol_estandar = ALIAS_ROL.get(rol_clave) or (rol_nombre if rol_nombre in TABLAS_ROL_WHITELIST else None)
    if not rol_estandar or rol_estandar not in TABLAS_ROL_WHITELIST:
        return None
    tabla, col_pk = TABLAS_ROL_WHITELIST[rol_estandar]
    return rol_estandar, tabla, col_pk


def listar_cuentas(rol_nombre: str) -> List[Dict[str, Any]]:
    """Consulta la lista de cuentas para un rol determinado.

    Nunca incluye contrasena_hash en la consulta.
    """
    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        logger_cuentas.error("Intento de listar cuentas con rol no autorizado: %s", rol_nombre)
        return []

    rol_estandar, tabla, col_pk = info_rol
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        col_tel = "numero_t" if tabla == "profesor" else ("telefono" if tabla == "tecnico" else "NULL")
        query = f"""
            SELECT {col_pk} AS carnet, nombres, apellidos, correo, estado_cuenta, {col_tel} AS telefono
            FROM {tabla}
            ORDER BY {col_pk} ASC
        """
        cursor.execute(query)
        filas = cursor.fetchall() or []
        for fila in filas:
            fila["rol"] = rol_estandar
        return filas
    except MySQLError as err:
        logger_cuentas.exception("Error al listar cuentas de %s: %s", rol_estandar, err)
        return []
    finally:
        conexion.close()


def aprobar_cuenta(carnet: str, rol_nombre: str) -> Dict[str, Any]:
    """Aprueba una cuenta cambiando su estado de 'Pendiente' a 'Activo'.

    La precondición va estrictamente en el WHERE (estado_cuenta = 'Pendiente').
    Verifica cursor.rowcount: si es 0, otro admin ya la gestionó.
    """
    if not carnet:
        return {"exito": False, "motivo": "params", "mensaje": "Carnet no especificado."}

    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        return {"exito": False, "motivo": "rol_invalido", "mensaje": "Rol no permitido."}

    _, tabla, col_pk = info_rol
    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        query = f"""
            UPDATE {tabla}
            SET estado_cuenta = 'Activo'
            WHERE {col_pk} = %s AND estado_cuenta = 'Pendiente'
        """
        cursor.execute(query, (carnet,))
        if cursor.rowcount == 1:
            conexion.commit()
            return {"exito": True, "mensaje": "Cuenta aprobada y activada exitosamente."}

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "ya_gestionada",
            "mensaje": "La cuenta ya fue gestionada por otro administrador o ya no está pendiente.",
        }
    except MySQLError as err:
        conexion.rollback()
        logger_cuentas.exception("Error al aprobar cuenta %s en %s: %s", carnet, tabla, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def rechazar_cuenta(carnet: str, rol_nombre: str) -> Dict[str, Any]:
    """Rechaza una cuenta pendiente eliminándola del sistema.

    CONDICIÓN OBLIGATORIA DE SEGURIDAD:
    El DELETE incluye estrictamente estado_cuenta = 'Pendiente'.
    Jamás se puede borrar una cuenta que esté en estado 'Activo' o 'Inactivo'.
    """
    if not carnet:
        return {"exito": False, "motivo": "params", "mensaje": "Carnet no especificado."}

    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        return {"exito": False, "motivo": "rol_invalido", "mensaje": "Rol no permitido."}

    _, tabla, col_pk = info_rol
    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        query = f"""
            DELETE FROM {tabla}
            WHERE {col_pk} = %s AND estado_cuenta = 'Pendiente'
        """
        cursor.execute(query, (carnet,))
        if cursor.rowcount == 1:
            conexion.commit()
            return {"exito": True, "mensaje": "Cuenta rechazada y eliminada correctamente."}

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "no_pendiente",
            "mensaje": "La cuenta no se encuentra en estado pendiente o ya fue gestionada.",
        }
    except MySQLError as err:
        conexion.rollback()
        if getattr(err, "errno", None) == 1451:
            return {
                "exito": False,
                "motivo": "fk_restrict",
                "mensaje": "No se puede eliminar la cuenta porque posee registros o historial asociado.",
            }
        logger_cuentas.exception("Error al rechazar cuenta %s en %s: %s", carnet, tabla, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def cambiar_estado_cuenta(
    carnet: str,
    rol_nombre: str,
    nuevo_estado: str,
    carnet_solicitante: Optional[str] = None,
) -> Dict[str, Any]:
    """Cambia el estado de una cuenta entre 'Activo' e 'Inactivo'.

    Reglas de negocio:
    1. Un administrador no puede desactivarse a sí mismo.
    2. No se puede desactivar al último administrador activo del sistema.
    3. Solo aplica sobre cuentas existentes que no estén pendientes (o Activo <-> Inactivo).
    """
    if not carnet or nuevo_estado not in ("Activo", "Inactivo"):
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Parámetros inválidos para cambiar estado de cuenta.",
        }

    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        return {"exito": False, "motivo": "rol_invalido", "mensaje": "Rol no permitido."}

    rol_estandar, tabla, col_pk = info_rol

    # Regla 1: El administrador no puede desactivarse a sí mismo
    if rol_estandar == "Administrador" and nuevo_estado == "Inactivo":
        if carnet_solicitante and carnet.strip().upper() == carnet_solicitante.strip().upper():
            return {
                "exito": False,
                "motivo": "auto_desactivacion",
                "mensaje": "No puedes desactivar tu propia cuenta de administrador.",
            }

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        # Regla 2: No se puede desactivar al último administrador activo
        if rol_estandar == "Administrador" and nuevo_estado == "Inactivo":
            cursor.execute(
                "SELECT COUNT(*) AS total FROM administrador WHERE estado_cuenta = 'Activo'"
            )
            fila_total = cursor.fetchone()
            total_activos = fila_total["total"] if fila_total else 0
            if total_activos <= 1:
                return {
                    "exito": False,
                    "motivo": "ultimo_admin",
                    "mensaje": "No es posible desactivar al único administrador activo del sistema.",
                }

        # Actualizar estado condicionado a que no esté pendiente (solo Activo <-> Inactivo)
        query = f"""
            UPDATE {tabla}
            SET estado_cuenta = %s
            WHERE {col_pk} = %s AND estado_cuenta IN ('Activo', 'Inactivo')
        """
        cursor.execute(query, (nuevo_estado, carnet))
        if cursor.rowcount == 1:
            conexion.commit()
            return {
                "exito": True,
                "mensaje": f"Estado de la cuenta actualizado a '{nuevo_estado}' exitosamente.",
            }

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "sin_cambios",
            "mensaje": "No se pudo actualizar el estado. La cuenta podría estar en estado 'Pendiente' o ya tener dicho estado.",
        }
    except MySQLError as err:
        conexion.rollback()
        logger_cuentas.exception("Error al cambiar estado de %s (%s): %s", carnet, tabla, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def obtener_perfil_administrador(carnet_o_correo: str) -> Optional[Dict[str, Any]]:
    """Consulta la información pública del perfil del administrador autenticado.

    Nunca incluye contrasena_hash.
    """
    if not carnet_o_correo:
        return None
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT carnet_administrador AS carnet, nombres, apellidos, correo, estado_cuenta
            FROM administrador
            WHERE carnet_administrador = %s OR correo = %s
            LIMIT 1
            """,
            (carnet_o_correo, carnet_o_correo),
        )
        return cursor.fetchone()
    except MySQLError as err:
        logger_cuentas.exception("Error al consultar perfil de administrador: %s", err)
        return None
    finally:
        conexion.close()


def cambiar_contrasena_administrador(
    carnet_o_correo: str,
    contrasena_actual: str,
    contrasena_nueva: str,
) -> Dict[str, Any]:
    """Valida la contraseña actual con bcrypt y actualiza al nuevo hash.

    Nunca registra ni imprime contraseñas en texto plano ni hashes.
    """
    if not carnet_o_correo or not contrasena_actual or not contrasena_nueva:
        return {"exito": False, "mensaje": "Todos los campos de contraseña son requeridos."}

    if len(contrasena_nueva) < 8:
        return {
            "exito": False,
            "mensaje": "La nueva contraseña debe tener al menos 8 caracteres.",
        }

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT carnet_administrador, contrasena_hash
            FROM administrador
            WHERE carnet_administrador = %s OR correo = %s
            LIMIT 1
            """,
            (carnet_o_correo, carnet_o_correo),
        )
        fila = cursor.fetchone()
        if not fila:
            return {"exito": False, "mensaje": "Usuario administrador no encontrado."}

        hash_guardado = fila["contrasena_hash"]
        if not bcrypt.checkpw(contrasena_actual.encode("utf-8"), hash_guardado.encode("utf-8")):
            return {"exito": False, "mensaje": "La contraseña actual es incorrecta."}

        nuevo_hash = bcrypt.hashpw(contrasena_nueva.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        carnet_admin = fila["carnet_administrador"]

        cursor.execute(
            """
            UPDATE administrador
            SET contrasena_hash = %s
            WHERE carnet_administrador = %s
            """,
            (nuevo_hash, carnet_admin),
        )
        conexion.commit()
        return {"exito": True, "mensaje": "Contraseña actualizada exitosamente."}
    except MySQLError as err:
        conexion.rollback()
        logger_cuentas.exception("Error al actualizar contraseña de administrador: %s", err)
        return {"exito": False, "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def actualizar_usuario(
    carnet: str,
    rol_nombre: str,
    nombres: str,
    apellidos: str,
    correo: str,
    telefono: Optional[str] = None,
) -> Dict[str, Any]:
    """Actualiza los datos personales (nombres, apellidos, correo, teléfono) de un usuario."""
    if not carnet:
        return {"exito": False, "motivo": "params", "mensaje": "Carnet no especificado."}

    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        return {"exito": False, "motivo": "rol_invalido", "mensaje": "Rol no permitido."}

    nombres_limpio = (nombres or "").strip()
    apellidos_limpio = (apellidos or "").strip()
    correo_limpio = (correo or "").strip().lower()
    telefono_limpio = (telefono or "").strip() or None

    if not nombres_limpio or not apellidos_limpio:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "Los nombres y apellidos son obligatorios.",
        }

    if not correo_limpio or "@" not in correo_limpio:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El correo electrónico no es válido.",
        }

    rol_estandar, tabla, col_pk = info_rol
    conexion = get_connection()
    try:
        cursor = conexion.cursor()

        # Verificar si el nuevo correo pertenece a otro usuario en la misma tabla
        cursor.execute(
            f"SELECT {col_pk} FROM {tabla} WHERE correo = %s AND {col_pk} != %s",
            (correo_limpio, carnet),
        )
        if cursor.fetchone():
            return {
                "exito": False,
                "motivo": "correo_duplicado",
                "mensaje": f"El correo '{correo_limpio}' ya está registrado para otro usuario.",
            }

        if tabla == "profesor":
            query = f"""
                UPDATE profesor
                SET nombres = %s, apellidos = %s, correo = %s, numero_t = %s
                WHERE carnet_profesor = %s
            """
            cursor.execute(query, (nombres_limpio, apellidos_limpio, correo_limpio, telefono_limpio, carnet))
        elif tabla == "tecnico":
            query = f"""
                UPDATE tecnico
                SET nombres = %s, apellidos = %s, correo = %s, telefono = %s
                WHERE carnet_tecnico = %s
            """
            cursor.execute(query, (nombres_limpio, apellidos_limpio, correo_limpio, telefono_limpio, carnet))
        else:
            query = f"""
                UPDATE administrador
                SET nombres = %s, apellidos = %s, correo = %s
                WHERE carnet_administrador = %s
            """
            cursor.execute(query, (nombres_limpio, apellidos_limpio, correo_limpio, carnet))

        conexion.commit()
        return {
            "exito": True,
            "mensaje": f"Datos de {rol_estandar} ({carnet}) actualizados exitosamente.",
        }
    except MySQLError as err:
        conexion.rollback()
        if getattr(err, "errno", None) == 1062:
            return {
                "exito": False,
                "motivo": "correo_duplicado",
                "mensaje": "El correo electrónico especificado ya se encuentra registrado.",
            }
        logger_cuentas.exception("Error al actualizar usuario %s en %s: %s", carnet, tabla, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def eliminar_cuenta(
    carnet: str,
    rol_nombre: str,
    carnet_solicitante: Optional[str] = None,
) -> Dict[str, Any]:
    """Elimina permanentemente una cuenta de usuario (Docente, Técnico o Administrador).

    Reglas de protección:
    1. Un administrador no puede eliminarse a sí mismo.
    2. No se puede eliminar al último administrador del sistema.
    3. Para docentes con reportes existentes (FK RESTRICT), captura error 1451 con mensaje amigable.
    """
    if not carnet:
        return {"exito": False, "motivo": "params", "mensaje": "Carnet no especificado."}

    info_rol = _resolver_rol(rol_nombre)
    if not info_rol:
        return {"exito": False, "motivo": "rol_invalido", "mensaje": "Rol no permitido."}

    rol_estandar, tabla, col_pk = info_rol

    # Regla 1: Un administrador no puede eliminarse a sí mismo
    if rol_estandar == "Administrador":
        if carnet_solicitante and carnet.strip().upper() == carnet_solicitante.strip().upper():
            return {
                "exito": False,
                "motivo": "auto_eliminacion",
                "mensaje": "No puedes eliminar tu propia cuenta de administrador.",
            }

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)

        # Regla 2: No se puede eliminar al último administrador
        if rol_estandar == "Administrador":
            cursor.execute("SELECT COUNT(*) AS total FROM administrador")
            fila_total = cursor.fetchone()
            total_admins = fila_total["total"] if fila_total else 0
            if total_admins <= 1:
                return {
                    "exito": False,
                    "motivo": "ultimo_admin",
                    "mensaje": "No es posible eliminar al único administrador del sistema.",
                }

        # Eliminar registros de recuperación de contraseña asociados al correo del usuario
        cursor.execute(f"SELECT correo FROM {tabla} WHERE {col_pk} = %s", (carnet,))
        fila_user = cursor.fetchone()
        if fila_user and fila_user.get("correo"):
            cursor.execute("DELETE FROM codigo_recuperacion WHERE correo = %s", (fila_user["correo"],))

        # Eliminar usuario
        cursor.execute(f"DELETE FROM {tabla} WHERE {col_pk} = %s", (carnet,))
        if cursor.rowcount >= 1:
            conexion.commit()
            return {
                "exito": True,
                "mensaje": f"La cuenta de {rol_estandar} ({carnet}) ha sido eliminada exitosamente.",
            }

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "no_encontrado",
            "mensaje": f"No se encontró el registro para eliminar en {tabla}.",
        }
    except MySQLError as err:
        conexion.rollback()
        if getattr(err, "errno", None) == 1451:
            return {
                "exito": False,
                "motivo": "fk_restrict",
                "mensaje": (
                    f"No se puede eliminar a este {rol_estandar.lower()} porque tiene reportes o historiales "
                    "asociados en el sistema. Puedes cambiar su estado a 'Inactivo' en su lugar."
                ),
            }
        logger_cuentas.exception("Error al eliminar cuenta %s en %s: %s", carnet, tabla, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


# Consolidado desde services/laboratorio_service.py: gestion de laboratorios.
# services/laboratorio_service.py
# -*- coding: utf-8 -*-
"""Capa de datos para la gestión (CRUD) de Laboratorios por el Administrador.

Responsabilidad:
    - Listar, crear, actualizar y eliminar laboratorios en la tabla laboratorio.
    - Manejo seguro de errores de MySQL:
        * Error 1062: ID de laboratorio duplicado traducido a mensaje comprensible.
        * Error 1451: FK RESTRICT por reportes vinculados traducido al mensaje exacto:
          "Este laboratorio tiene reportes asociados y no puede eliminarse".
    - Todas las consultas son parametrizadas con %s.
"""



logger_laboratorios = logging.getLogger(__name__)


def listar_laboratorios() -> List[Dict[str, Any]]:
    """Devuelve la lista ordenada de laboratorios registrados."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id_laboratorio, nombre, ubicacion
            FROM laboratorio
            ORDER BY id_laboratorio ASC
            """
        )
        return cursor.fetchall() or []
    except MySQLError as err:
        logger_laboratorios.exception("Error al listar laboratorios: %s", err)
        return []
    finally:
        conexion.close()


def crear_laboratorio(id_laboratorio: str, nombre: str, ubicacion: Optional[str] = None) -> Dict[str, Any]:
    """Inserta un nuevo laboratorio en la base de datos."""
    id_limpio = (id_laboratorio or "").strip().upper()
    nombre_limpio = (nombre or "").strip()
    ubicacion_limpia = (ubicacion or "").strip() or None

    if not id_limpio or not nombre_limpio:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El identificador (ID) y el nombre del laboratorio son obligatorios.",
        }

    if len(id_limpio) > 10:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El ID del laboratorio no puede exceder 10 caracteres.",
        }

    if len(nombre_limpio) > 60:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El nombre del laboratorio no puede exceder 60 caracteres.",
        }

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO laboratorio (id_laboratorio, nombre, ubicacion)
            VALUES (%s, %s, %s)
            """,
            (id_limpio, nombre_limpio, ubicacion_limpia),
        )
        conexion.commit()
        return {
            "exito": True,
            "mensaje": f"Laboratorio '{id_limpio}' registrado exitosamente.",
            "id_laboratorio": id_limpio,
        }
    except MySQLError as err:
        conexion.rollback()
        if getattr(err, "errno", None) == 1062:
            return {
                "exito": False,
                "motivo": "id_duplicado",
                "mensaje": f"El identificador '{id_limpio}' ya está registrado. Por favor utiliza un ID distinto.",
            }
        logger_laboratorios.exception("Error al crear laboratorio %s: %s", id_limpio, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def actualizar_laboratorio(id_laboratorio: str, nombre: str, ubicacion: Optional[str] = None) -> Dict[str, Any]:
    """Actualiza los datos de un laboratorio existente."""
    id_limpio = (id_laboratorio or "").strip().upper()
    nombre_limpio = (nombre or "").strip()
    ubicacion_limpia = (ubicacion or "").strip() or None

    if not id_limpio or not nombre_limpio:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El nombre del laboratorio no puede estar vacío.",
        }

    if len(nombre_limpio) > 60:
        return {
            "exito": False,
            "motivo": "params",
            "mensaje": "El nombre del laboratorio no puede exceder 60 caracteres.",
        }

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE laboratorio
            SET nombre = %s, ubicacion = %s
            WHERE id_laboratorio = %s
            """,
            (nombre_limpio, ubicacion_limpia, id_limpio),
        )
        if cursor.rowcount == 0:
            cursor.execute("SELECT 1 FROM laboratorio WHERE id_laboratorio = %s", (id_limpio,))
            if not cursor.fetchone():
                conexion.rollback()
                return {
                    "exito": False,
                    "motivo": "no_encontrado",
                    "mensaje": f"El laboratorio '{id_limpio}' no existe.",
                }

        conexion.commit()
        return {
            "exito": True,
            "mensaje": f"Laboratorio '{id_limpio}' actualizado exitosamente.",
        }
    except MySQLError as err:
        conexion.rollback()
        logger_laboratorios.exception("Error al actualizar laboratorio %s: %s", id_limpio, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


def eliminar_laboratorio(id_laboratorio: str) -> Dict[str, Any]:
    """Elimina un laboratorio si no tiene reportes asociados.

    Si tiene reportes, la restricción de llave foránea (FK RESTRICT) genera
    el error 1451, capturado para emitir el mensaje reglamentario.
    """
    id_limpio = (id_laboratorio or "").strip().upper()
    if not id_limpio:
        return {"exito": False, "motivo": "params", "mensaje": "ID de laboratorio no especificado."}

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            "DELETE FROM laboratorio WHERE id_laboratorio = %s",
            (id_limpio,),
        )
        if cursor.rowcount == 1:
            conexion.commit()
            return {
                "exito": True,
                "mensaje": f"Laboratorio '{id_limpio}' eliminado exitosamente.",
            }

        conexion.rollback()
        return {
            "exito": False,
            "motivo": "no_encontrado",
            "mensaje": f"El laboratorio '{id_limpio}' no existe o ya fue eliminado.",
        }
    except MySQLError as err:
        conexion.rollback()
        if getattr(err, "errno", None) == 1451:
            return {
                "exito": False,
                "motivo": "fk_reportes",
                "mensaje": "Este laboratorio tiene reportes asociados y no puede eliminarse",
            }
        logger_laboratorios.exception("Error al eliminar laboratorio %s: %s", id_limpio, err)
        return {"exito": False, "motivo": "db_error", "mensaje": f"Error en la base de datos: {err}"}
    finally:
        conexion.close()


# Consolidado desde services/estadisticas_service.py: estadisticas.
"""Consultas agregadas para las métricas del dashboard de administración.

Todas las consultas usan el mismo conector MySQL que el resto de la capa de
servicios (``services.auth.get_connection``) y el esquema definido en SQL.
"""




def contar_resueltas_mes() -> int:
    """Cuenta los reportes resueltos durante el mes calendario actual."""
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM reporte
            WHERE estado = 'Resuelto'
              AND fecha_resolucion >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND fecha_resolucion < DATE_ADD(
                    DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH
                  )
            """
        )
        return int(cursor.fetchone()["total"])
    finally:
        conexion.close()


def obtener_dificultades() -> dict[str, int]:
    """Cuenta reportes reabiertos y confirmados fuera del plazo de cinco días.

    El plazo comienza al confirmar/asignar una incidencia (``fecha_confirmado``),
    de acuerdo con la descripción de esa columna en el esquema del proyecto.
    """
    asegurar_catalogos()
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                SUM(CASE
                    WHEN estado IN ('Confirmado', 'En reparación', 'En proceso')
                     AND fecha_confirmado < DATE_SUB(NOW(), INTERVAL 5 DAY)
                    THEN 1 ELSE 0
                END) AS vencidas,
                SUM(CASE WHEN estado = 'Reabierto' THEN 1 ELSE 0 END) AS reabiertas
            FROM reporte
            """
        )
        fila = cursor.fetchone() or {}
        return {
            "vencidas": int(fila.get("vencidas") or 0),
            "reabiertas": int(fila.get("reabiertas") or 0),
        }
    finally:
        conexion.close()


def obtener_tipos_problema(limite: int = 5) -> list[dict[str, Any]]:
    """Devuelve las categorías con más reportes, ordenadas por frecuencia."""
    limite = max(0, int(limite))
    if not limite:
        return []

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT c.nombre AS tipo, COUNT(*) AS cantidad
            FROM reporte r
            INNER JOIN categoria c ON c.id_categoria = r.id_categoria
            GROUP BY c.id_categoria, c.nombre
            ORDER BY cantidad DESC, c.nombre ASC
            LIMIT %s
            """,
            (limite,),
        )
        return [
            {"tipo": fila["tipo"], "cantidad": int(fila["cantidad"])}
            for fila in cursor.fetchall()
        ]
    finally:
        conexion.close()


def obtener_distribucion_mensual() -> list[dict[str, Any]]:
    """Distribución de los estados de reportes creados en el mes actual."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT estado AS etiqueta, COUNT(*) AS cantidad
            FROM reporte
            WHERE fecha >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
              AND fecha < DATE_ADD(
                    DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH
                  )
            GROUP BY estado
            ORDER BY cantidad DESC, estado ASC
            """
        )
        return [
            {"etiqueta": fila["etiqueta"], "cantidad": int(fila["cantidad"])}
            for fila in cursor.fetchall()
        ]
    finally:
        conexion.close()
