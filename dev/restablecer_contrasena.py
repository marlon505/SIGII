"""Restablece localmente la contraseña de una cuenta usando el hash bcrypt."""

import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mysql.connector import Error as MySQLError

from services import auth


TABLAS_CUENTA = {
    "Maestro": ("profesor", "carnet_profesor"),
    "Técnico": ("tecnico", "carnet_tecnico"),
    "Administrador": ("administrador", "carnet_administrador"),
}


def main() -> int:
    correo = input("Correo de la cuenta que deseas restablecer: ").strip()
    if not correo:
        print("El correo es obligatorio.")
        return 1

    try:
        usuario = auth.obtener_usuario_por_correo(correo)
    except MySQLError as error:
        print(f"No se pudo consultar la cuenta en MySQL ({type(error).__name__}).")
        return 1

    if usuario is None:
        print("No se encontró esa cuenta en la base de datos configurada.")
        return 1

    print(f"Cuenta encontrada. Rol: {usuario['rol']}; estado: {usuario['estado_cuenta']}.")
    nueva = getpass.getpass("Nueva contraseña (mínimo 8 caracteres; no se mostrará): ")
    confirmar = getpass.getpass("Confirma la nueva contraseña: ")
    if len(nueva) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        return 1
    if nueva != confirmar:
        print("Las contraseñas no coinciden.")
        return 1

    respuesta = input("¿Confirmas actualizar esta cuenta? [s/N]: ").strip().lower()
    if respuesta not in ("s", "si", "sí"):
        print("Operación cancelada; no se modificó la cuenta.")
        return 0

    tabla, columna_carnet = TABLAS_CUENTA[usuario["rol"]]
    conexion = auth.get_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            f"UPDATE {tabla} SET contrasena_hash = %s WHERE {columna_carnet} = %s",
            (auth.hashear_password(nueva), usuario["carnet"]),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            print("No se pudo actualizar exactamente una cuenta; no se aplicaron cambios.")
            return 1
        conexion.commit()
        print("Contraseña restablecida. Ya puedes iniciar sesión con la nueva contraseña.")
        return 0
    except MySQLError as error:
        conexion.rollback()
        print(f"No se pudo actualizar la contraseña en MySQL ({type(error).__name__}).")
        return 1
    finally:
        conexion.close()


if __name__ == "__main__":
    raise SystemExit(main())
