# services/auth.py
"""
auth.py

Objetivo:
    Capa de acceso a datos para autenticación y recuperación de contraseña
    del sistema SIGII. Es la única parte del código que sabe cómo hablar
    con las tablas profesor, tecnico, administrador y codigo_recuperacion.

Responsabilidad:
    - Registrar cuentas nuevas y validar que el correo no exista ya
      en ninguna de las tres tablas de rol.
    - Verificar credenciales de login y devolver el rol + estado de cuenta.
    - Generar y validar códigos de recuperación de contraseña.
    - Nunca expone contraseñas en texto plano ni fuera de este módulo.

Dependencias:
    pip install mysql-connector-python bcrypt python-dotenv --break-system-packages

Relación con otros módulos:
    - LoginWidget llama a login()
    - RegistrarseWidget llama a correo_existe() y registrar()
    - RecuperarWidget usa las funciones de validación y recuperación de este módulo.
      guardar_codigo_reset(), obtener_codigo_reset(), actualizar_contrasena(),
      invalidar_codigo_reset()

Variables de entorno esperadas (.env):
    DB_HOST=localhost
    DB_USER=root
    DB_PASSWORD=...
    DB_NAME=reportes_laboratorio
"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import hmac
import os
import re
import secrets

from dotenv import load_dotenv
from mysql.connector import Error as MySQLError
import bcrypt
import mysql.connector

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Tablas que representan un rol de usuario, en el orden en que se consultan.
# Cada tupla es (nombre_tabla, columna_carnet, nombre_rol_legible)
TABLAS_ROL = [
    ("profesor", "carnet_profesor", "Maestro"),
    ("tecnico", "carnet_tecnico", "Técnico"),
    ("administrador", "carnet_administrador", "Administrador"),
]

PREFIJOS_CARNET = {
    "Maestro": "PROF",
    "Técnico": "TEC",
    "Administrador": "ADM",
}

MINUTOS_VALIDEZ_CODIGO = 15


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def get_connection():
    """Abre una nueva conexión a MySQL usando las credenciales del .env."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "reportes_laboratorio"),
    )


# ---------------------------------------------------------------------------
# Contraseñas (bcrypt: hashing lento a propósito, resistente a fuerza bruta)
# ---------------------------------------------------------------------------

def hashear_password(password: str) -> str:
    """Genera un hash bcrypt de la contraseña en texto plano."""
    hash_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verificar_password(password: str, hash_guardado: str) -> bool:
    """Compara una contraseña en texto plano contra su hash almacenado."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        if not hash_guardado or hash_guardado.startswith(("$2a$", "$2b$", "$2y$")):
            return False
        return hmac.compare_digest(
            password.encode("utf-8"),
            hash_guardado.encode("utf-8"),
        )


def _migrar_hash_heredado(usuario: dict, hash_anterior: str, password: str) -> bool:
    """Reemplaza la clave heredada solo si el valor almacenado no ha cambiado."""
    tabla_por_rol = {
        "Maestro": ("profesor", "carnet_profesor"),
        "Técnico": ("tecnico", "carnet_tecnico"),
        "Administrador": ("administrador", "carnet_administrador"),
    }
    destino = tabla_por_rol.get(usuario["rol"])
    if destino is None:
        return False

    tabla, columna_carnet = destino
    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            f"""
            UPDATE {tabla}
            SET contrasena_hash = %s
            WHERE {columna_carnet} = %s AND contrasena_hash = %s
            """,
            (
                hashear_password(password),
                usuario["carnet"],
                hash_anterior,
            ),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return False
        conexion.commit()
        return True
    except MySQLError:
        conexion.rollback()
        raise
    finally:
        conexion.close()


# ---------------------------------------------------------------------------
# Cuentas
# ---------------------------------------------------------------------------

def correo_existe(correo: str) -> bool:
    """
    Revisa si el correo ya está registrado en profesor, tecnico o administrador.
    Necesario porque UNIQUE en MySQL no puede validar entre tablas distintas.
    """
    return obtener_usuario_por_correo(correo) is not None


def obtener_usuario_por_correo(correo: str) -> Optional[dict]:
    """
    Busca un correo en las tres tablas de rol.
    Devuelve un dict con carnet, correo, contrasena_hash, estado_cuenta y rol,
    o None si no existe en ninguna.
    """
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        for tabla, columna_carnet, rol in TABLAS_ROL:
            cursor.execute(
                f"""
                SELECT {columna_carnet} AS carnet, correo, contrasena_hash, estado_cuenta, nombres, apellidos
                FROM {tabla}
                WHERE correo = %s
                """,
                (correo,),
            )
            fila = cursor.fetchone()
            if fila:
                fila["rol"] = rol
                return fila
        return None
    finally:
        conexion.close()


def _generar_carnet(cursor, tabla: str, columna_carnet: str, rol: str) -> str:
    """
    Genera un carnet correlativo tipo PROF-0001, TEC-0001, ADM-0001.
    Simplificación aceptable para un despliegue de kiosco único (sin
    registros concurrentes reales); no pensado para alta concurrencia.
    """
    cursor.execute(f"SELECT COUNT(*) AS total FROM {tabla}")
    total = cursor.fetchone()["total"]
    prefijo = PREFIJOS_CARNET[rol]
    return f"{prefijo}-{total + 1:04d}"


def registrar(correo: str, contrasena: str, rol: str, nombres: str,
              apellidos: str, numero_t: Optional[str] = None) -> dict:
    """
    Registra una cuenta nueva. rol debe ser 'Maestro', 'Técnico' o 'Administrador'.

    Devuelve:
        {"exito": bool, "mensaje": str}
    """
    tabla_map = {r: (t, c) for t, c, r in TABLAS_ROL}
    if rol not in tabla_map:
        return {"exito": False, "mensaje": "Rol inválido."}

    if correo_existe(correo):
        return {"exito": False, "mensaje": "Este correo ya está registrado."}

    tabla, columna_carnet = tabla_map[rol]
    contrasena_hash = hashear_password(contrasena)
    estado_inicial = "Activo" if rol in ["Maestro", "Técnico"] else "Pendiente"

    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        carnet = _generar_carnet(cursor, tabla, columna_carnet, rol)

        if tabla == "profesor":
            cursor.execute(
                """
                INSERT INTO profesor
                    (carnet_profesor, nombres, apellidos, correo, numero_t,
                     contrasena_hash, estado_cuenta)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (carnet, nombres, apellidos, correo, numero_t,
                 contrasena_hash, estado_inicial),
            )
        elif tabla == "tecnico":
            cursor.execute(
                """
                INSERT INTO tecnico
                    (carnet_tecnico, nombres, apellidos, correo, telefono,
                     contrasena_hash, estado_cuenta)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (carnet, nombres, apellidos, correo, numero_t,
                 contrasena_hash, estado_inicial),
            )
        else:  # administrador
            cursor.execute(
                """
                INSERT INTO administrador
                    (carnet_administrador, nombres, apellidos, correo,
                     contrasena_hash, estado_cuenta)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (carnet, nombres, apellidos, correo,
                 contrasena_hash, estado_inicial),
            )

        conexion.commit()
        return {"exito": True, "mensaje": "Cuenta creada.", "carnet": carnet,
                "estado_cuenta": estado_inicial}
    except MySQLError as error:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error de base de datos: {error}"}
    finally:
        conexion.close()


def registrarse(correo: str, contrasena: str, rol: str = "Maestro", nombres: str = "Usuario",
                apellidos: str = "SIGII", numero_t: Optional[str] = None) -> dict:
    """Helper wrapper for registrar."""
    return registrar(correo, contrasena, rol, nombres, apellidos, numero_t)


def login(correo: str, contrasena: str) -> dict:
    """
    Valida credenciales de login.

    Devuelve:
        {"exito": bool, "status": str, "mensaje": str, "rol": str | None, "carnet": str | None}
    """
    usuario = obtener_usuario_por_correo(correo)

    # Mensaje genérico: nunca revelar si falló el correo o la contraseña.
    mensaje_credenciales_invalidas = "Correo o contraseña incorrectos."

    if usuario is None:
        return {"exito": False, "status": "error", "mensaje": mensaje_credenciales_invalidas,
                "rol": None, "carnet": None}

    hash_guardado = usuario["contrasena_hash"] or ""
    if not verificar_password(contrasena, hash_guardado):
        return {"exito": False, "status": "error", "mensaje": mensaje_credenciales_invalidas,
                "rol": None, "carnet": None}

    if not hash_guardado.startswith(("$2a$", "$2b$", "$2y$")):
        if not _migrar_hash_heredado(usuario, hash_guardado, contrasena):
            return {
                "exito": False,
                "status": "error",
                "mensaje": "La cuenta cambió durante el inicio de sesión. Inténtalo de nuevo.",
                "rol": None,
                "carnet": None,
            }

    if usuario["estado_cuenta"] == "Pendiente":
        return {"exito": False, "status": "pendiente",
                "mensaje": "Tu cuenta está pendiente de aprobación por un administrador.",
                "rol": None, "carnet": None}

    if usuario["estado_cuenta"] == "Inactivo":
        return {"exito": False, "status": "inactivo", "mensaje": "Esta cuenta está inactiva.",
                "rol": None, "carnet": None}

    nombre_completo = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip() or "Usuario SIGII"
    return {"exito": True, "status": "ok", "mensaje": "Login exitoso.",
            "rol": usuario["rol"], "carnet": usuario["carnet"], "correo": usuario["correo"],
            "nombres": usuario.get("nombres"), "apellidos": usuario.get("apellidos"),
            "nombre_completo": nombre_completo}


# ---------------------------------------------------------------------------
# Recuperación de contraseña
# ---------------------------------------------------------------------------

def _hashear_codigo(codigo: str) -> str:
    """
    sha256 para el código de 6 dígitos: a diferencia de la contraseña,
    este valor expira en minutos y no necesita el costo computacional de
    bcrypt para ser seguro.
    """
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def generar_codigo() -> str:
    """Genera un código numérico de 6 dígitos, con ceros a la izquierda si aplica."""
    return f"{secrets.randbelow(1_000_000):06d}"


def guardar_codigo_reset(correo: str) -> str:
    """
    Crea un nuevo código de recuperación para el correo dado y lo guarda
    hasheado. Devuelve el código EN TEXTO PLANO para que quien llame lo
    envíe por correo (EmailWorker) — este es el único punto del sistema
    donde el código plano existe fuera de la memoria del usuario.
    """
    codigo = generar_codigo()
    codigo_hash = _hashear_codigo(codigo)
    fecha_expiracion = datetime.now() + timedelta(minutes=MINUTOS_VALIDEZ_CODIGO)

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        # Invalida códigos anteriores no usados para este correo
        cursor.execute(
            "UPDATE codigo_recuperacion SET usado = TRUE WHERE correo = %s AND usado = FALSE",
            (correo,),
        )
        cursor.execute(
            """
            INSERT INTO codigo_recuperacion (correo, codigo_hash, fecha_expiracion)
            VALUES (%s, %s, %s)
            """,
            (correo, codigo_hash, fecha_expiracion),
        )
        conexion.commit()
        return codigo
    finally:
        conexion.close()


def obtener_codigo_reset(correo: str) -> Optional[dict]:
    """
    Devuelve el código de recuperación más reciente, no usado, para ese
    correo (id, codigo_hash, fecha_expiracion). No valida si ya expiró:
    la validación de expiración se mantiene en este módulo.
    """
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id_codigo, codigo_hash, fecha_expiracion
            FROM codigo_recuperacion
            WHERE correo = %s AND usado = FALSE
            ORDER BY fecha_creacion DESC
            LIMIT 1
            """,
            (correo,),
        )
        return cursor.fetchone()
    finally:
        conexion.close()


def codigo_coincide(codigo_ingresado: str, codigo_hash: str) -> bool:
    """Compara el código ingresado por el usuario contra el hash guardado."""
    return _hashear_codigo(codigo_ingresado) == codigo_hash


def invalidar_codigo_reset(id_codigo: int) -> None:
    """Marca un código como usado para que no pueda reutilizarse."""
    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            "UPDATE codigo_recuperacion SET usado = TRUE WHERE id_codigo = %s",
            (id_codigo,),
        )
        conexion.commit()
    finally:
        conexion.close()


def actualizar_contrasena(correo: str, nueva_contrasena: str) -> bool:
    """
    Actualiza la contraseña del usuario dueño de ese correo, sin importar
    en cuál de las tres tablas de rol esté.
    """
    usuario = obtener_usuario_por_correo(correo)
    if usuario is None:
        return False

    tabla_map = {r: (t, c) for t, c, r in TABLAS_ROL}
    tabla, columna_carnet = tabla_map[usuario["rol"]]
    nuevo_hash = hashear_password(nueva_contrasena)

    conexion = get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            f"UPDATE {tabla} SET contrasena_hash = %s WHERE correo = %s",
            (nuevo_hash, correo),
        )
        conexion.commit()
        return cursor.rowcount > 0
    finally:
        conexion.close()

# Consolidado desde services/password_reset_service.py: validacion de recuperacion de contrasena.
# services/password_reset_service.py

CODE_LENGTH = 6
CODE_TTL_MINUTES = 15
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def correo_es_valido(correo: str) -> bool:
    return bool(EMAIL_REGEX.match(correo))


def generar_codigo_validacion() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))


def hashear_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def calcular_expiracion() -> str:
    return (datetime.now() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()


def codigo_expirado(expira) -> bool:
    if isinstance(expira, datetime):
        return datetime.now() > expira
    if isinstance(expira, str):
        return datetime.now() > datetime.fromisoformat(expira)
    return False


def codigo_es_valido(codigo_ingresado: str, hash_guardado: str, expira) -> bool:
    if codigo_expirado(expira):
        return False
    return hashear_codigo(codigo_ingresado) == hash_guardado