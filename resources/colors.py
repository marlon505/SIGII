"""
Paleta de colores centralizada del proyecto SIGII.
Fuente única de verdad: cualquier cambio de color se hace aquí,
nunca directamente en un widget o archivo .qss individual.
"""

class Colors:
    # Paleta base (documento de estilo visual)
    AZUL = "#1E3A8A"
    BLANCO = "#FFFFFF"
    AMARILLO_MOSTAZA = "#D4A017"
    ROJO = "#DC2626"
    GRIS = "#6B7280"

    # Paleta Verde para Rol Técnico
    VERDE_TECNICO = "#15803D"        # Verde esmeralda principal
    VERDE_TECNICO_OSCURO = "#166534" # Verde hover / acento
    VERDE_TECNICO_CLARO = "#DCFCE7"  # Verde fondos y selecciones

    # Paleta Roja para Rol Administrador
    ROJO_ADMIN = "#DC2626"           # Rojo institucional principal
    ROJO_ADMIN_OSCURO = "#B91C1C"    # Rojo hover / acento fuerte
    ROJO_ADMIN_CLARO = "#FEE2E2"     # Rojo claro selecciones y badges
    ROJO_ADMIN_FONDO = "#FEF2F2"     # Fondo suave administrativo

    # Colores de estado de incidencia (decisión confirmada con el equipo)
    ESTADO_PENDIENTE = "#3B82F6"        # celeste - recién creado, sin revisar
    ESTADO_CONFIRMADO = "#16A34A"       # verde - técnico validó el problema
    ESTADO_EN_REPARACION = AMARILLO_MOSTAZA
    ESTADO_RESUELTO = GRIS
    ESTADO_REABIERTO = ROJO