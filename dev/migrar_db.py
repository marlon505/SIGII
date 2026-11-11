import os
import sys

# Agregar ruta raíz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth import get_connection

def migrar():
    conexion = get_connection()
    try:
        cursor = conexion.cursor(dictionary=True)
        
        # 1. Verificar columnas de reporte
        cursor.execute("DESCRIBE reporte")
        columnas = {fila["Field"]: fila for fila in cursor.fetchall()}
        
        if "fecha_confirmado" not in columnas:
            print("Agregando fecha_confirmado...")
            cursor.execute("ALTER TABLE reporte ADD COLUMN fecha_confirmado DATETIME NULL AFTER estado")
            print("Columna fecha_confirmado agregada.")
        else:
            print("fecha_confirmado ya existe.")

        if "reporte_cierre" not in columnas:
            print("Agregando reporte_cierre...")
            cursor.execute("ALTER TABLE reporte ADD COLUMN reporte_cierre TEXT NULL AFTER fecha_resolucion")
            print("Columna reporte_cierre agregada.")
        else:
            print("reporte_cierre ya existe.")
            
        # 2. Verificar ENUM estado
        tipo_estado = columnas.get("estado", {}).get("Type", "")
        print(f"Tipo actual de estado: {tipo_estado}")
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
            print("Actualizando ENUM de estado...")
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
            print("ENUM de estado actualizado exitosamente.")
        else:
            print("ENUM de estado ya está actualizado.")
            
        conexion.commit()
        print("Migración completada con éxito.")
    finally:
        conexion.close()

if __name__ == "__main__":
    migrar()
