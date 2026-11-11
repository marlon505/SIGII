# main.py
import sys
import re
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from ui.login_widget import LoginWidget
from ui.registrarse_widget import RegistrarseWidget
from ui.recuperar_widget import RecuperarWidget
from ui.verificar_codigo_widget import VerificarCodigoWidget
from ui.cerrar_sesion_widget import CerrarSesionWidget

# Dashboards imports
from ui.dashboards.dashboard_maestro_widget import DashboardMaestroWidget
from ui.dashboards.dashboard_tecnico_widget import DashboardTecnicoWidget
from ui.dashboards.dashboard_administrador_widget import DashboardAdministradorWidget

from resources.colors import Colors

# Pantallas de administración
from ui.gestion_cuentas_widget import GestionCuentasWidget
from ui.lista_incidencias_admin_widget import ListaIncidenciasAdminWidget
from ui.configuracion_widget import ConfiguracionWidget
from ui.gestion_laboratorios_widget import GestionLaboratoriosWidget

BASE_DIR = Path(__file__).resolve().parent


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIGII")
        self.resize(1150, 800)
        self.setMinimumSize(900, 650)

        self.rol_real = None
        self.rol_visual = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._build_screens()

    def _build_screens(self):
        # Pantallas
        self.login = LoginWidget()
        self.registrarse = RegistrarseWidget()
        self.recuperar = RecuperarWidget()
        self.verificar_codigo = VerificarCodigoWidget()
        self.cerrar_sesion = CerrarSesionWidget()
        self.dashboard_maestro = DashboardMaestroWidget()
        self.dashboard_tecnico = DashboardTecnicoWidget()
        self.dashboard_admin = DashboardAdministradorWidget()

        # Pantallas del Administrador
        self.pantalla_cuentas = GestionCuentasWidget()
        self.pantalla_incidencias_admin = ListaIncidenciasAdminWidget()
        self.pantalla_configuracion = ConfiguracionWidget()
        self.pantalla_laboratorios = GestionLaboratoriosWidget()

        # Agregar widgets al stack
        self.stack.addWidget(self.login)
        self.stack.addWidget(self.registrarse)
        self.stack.addWidget(self.recuperar)
        self.stack.addWidget(self.verificar_codigo)
        self.stack.addWidget(self.cerrar_sesion)
        self.stack.addWidget(self.dashboard_maestro)
        self.stack.addWidget(self.dashboard_tecnico)
        self.stack.addWidget(self.dashboard_admin)
        self.stack.addWidget(self.pantalla_cuentas)
        self.stack.addWidget(self.pantalla_incidencias_admin)
        self.stack.addWidget(self.pantalla_configuracion)
        self.stack.addWidget(self.pantalla_laboratorios)

        # Conexión de señales: navegación entre pantallas
        self.login.ir_a_registrarse.connect(
            lambda: self.stack.setCurrentWidget(self.registrarse)
        )
        self.login.ir_a_recuperar.connect(
            lambda: self.stack.setCurrentWidget(self.recuperar)
        )
        self.recuperar.ir_a_login.connect(
            lambda: self.stack.setCurrentWidget(self.login)
        )
        self.registrarse.ir_a_login.connect(
            lambda: self.stack.setCurrentWidget(self.login)
        )
        self.recuperar.codigo_enviado.connect(self._on_codigo_enviado)
        self.verificar_codigo.ir_a_login.connect(
            lambda: self.stack.setCurrentWidget(self.login)
        )
        self.login.login_exitoso.connect(self._on_login_exitoso)
        self.dashboard_maestro.cerrar_sesion.connect(self._on_cerrar_sesion)
        self.dashboard_tecnico.cerrar_sesion.connect(self._on_cerrar_sesion)
        self.dashboard_admin.cerrar_sesion.connect(self._on_cerrar_sesion)
        self.dashboard_admin.cambiar_modo_vista.connect(self._on_cambiar_modo_vista_admin)
        self.dashboard_maestro.volver_a_admin.connect(self._on_salir_modo_vista)
        self.dashboard_tecnico.volver_a_admin.connect(self._on_salir_modo_vista)
        # Conexión de botones del panel de Administrador a sus pantallas
        self.dashboard_admin.abrir_registro_usuarios.connect(
            lambda: self.stack.setCurrentWidget(self.pantalla_cuentas)
        )
        self.dashboard_admin.abrir_lista_incidencias.connect(
            lambda: self.stack.setCurrentWidget(self.pantalla_incidencias_admin)
        )
        self.dashboard_admin.abrir_gestion_laboratorios.connect(
            lambda: self.stack.setCurrentWidget(self.pantalla_laboratorios)
        )
        self.dashboard_admin.abrir_configuracion.connect(
            lambda: self.stack.setCurrentWidget(self.pantalla_configuracion)
        )

        # Retorno al dashboard desde cada pantalla de administración
        self.pantalla_cuentas.volver_solicitado.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_admin)
        )
        self.pantalla_incidencias_admin.volver_solicitado.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_admin)
        )
        self.pantalla_configuracion.volver_solicitado.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_admin)
        )
        self.pantalla_configuracion.cambiar_modo_vista.connect(self._on_cambiar_modo_vista_admin)
        self.pantalla_laboratorios.volver_solicitado.connect(
            lambda: self.stack.setCurrentWidget(self.dashboard_admin)
        )
        self.pantalla_laboratorios.laboratorios_modificados.connect(
            self.pantalla_incidencias_admin._cargar_catalogo_laboratorios
        )
        self.pantalla_laboratorios.laboratorios_modificados.connect(
            self.dashboard_admin.cargar_datos
        )
        self.pantalla_laboratorios.laboratorios_modificados.connect(
            self.dashboard_maestro.recargar
        )

        # Sincronización dentro de la misma instancia entre los tres dashboards
        self.dashboard_tecnico.incidencia_actualizada.connect(self.dashboard_maestro.recargar)
        self.dashboard_tecnico.incidencia_actualizada.connect(lambda _: self.dashboard_admin.cargar_datos())
        self.pantalla_incidencias_admin.incidencia_actualizada.connect(self.dashboard_maestro.recargar)
        self.pantalla_incidencias_admin.incidencia_actualizada.connect(lambda _: self.dashboard_tecnico.cargar_datos())
        self.dashboard_admin.incidencia_registrada.connect(self.dashboard_maestro.recargar)
        self.dashboard_admin.incidencia_registrada.connect(lambda _: self.dashboard_tecnico.cargar_datos())
        self.dashboard_maestro.incidencia_registrada.connect(lambda _: self.dashboard_tecnico.cargar_datos())
        self.dashboard_maestro.incidencia_registrada.connect(lambda _: self.dashboard_admin.cargar_datos())
        self.cerrar_sesion.sesion_cerrada.connect(
            lambda: self.stack.setCurrentWidget(self.login)
        )
        self.stack.setCurrentWidget(self.login)

    def _on_login_exitoso(self, rol: str, usuario_info: dict = None):
        self.dashboard_maestro.activar_modo_vista_admin(False)
        self.dashboard_tecnico.activar_modo_vista_admin(False)
        rol_key = rol.lower().strip() if rol else ""
        self.rol_real = rol_key
        self.rol_visual = rol_key
        if usuario_info and rol_key in ["maestro"]:
            self.dashboard_maestro.set_usuario(
                correo=usuario_info.get("correo"),
                carnet=usuario_info.get("carnet")
            )
        if usuario_info and rol_key in ["tecnico", "técnico"]:
            self.dashboard_tecnico.set_usuario(
                correo=usuario_info.get("correo"),
                carnet=usuario_info.get("carnet")
            )
        if usuario_info and rol_key in ["admin", "administrador"]:
            self.dashboard_admin.set_usuario(
                correo=usuario_info.get("correo"),
                carnet=usuario_info.get("carnet")
            )
            self.pantalla_configuracion.set_usuario(
                correo=usuario_info.get("correo"),
                carnet=usuario_info.get("carnet")
            )
            self.pantalla_cuentas.set_usuario(
                correo=usuario_info.get("correo"),
                carnet=usuario_info.get("carnet")
            )

        mapa_dashboards = {
            "maestro": self.dashboard_maestro,
            "tecnico": self.dashboard_tecnico,
            "técnico": self.dashboard_tecnico,
            "admin": self.dashboard_admin,
            "administrador": self.dashboard_admin,
        }
        dashboard = mapa_dashboards.get(rol_key)
        if dashboard is None:
            print(f"Advertencia: rol desconocido recibido: {rol}")
            return
        self.stack.setCurrentWidget(dashboard)
        print(f"Login exitoso como: {rol}")

    def _on_codigo_enviado(self, correo: str):
        self.verificar_codigo.set_correo(correo)
        self.stack.setCurrentWidget(self.verificar_codigo)

    def _on_cambiar_modo_vista_admin(self, modo: str):
        self.rol_visual = modo.lower().strip()
        correo = self.dashboard_admin.usuario_correo
        carnet = self.dashboard_admin.usuario_carnet
        if modo == "Maestro":
            self.dashboard_maestro.activar_modo_vista_admin(True)
            self.dashboard_maestro.set_usuario(correo=correo, carnet=carnet)
            self.stack.setCurrentWidget(self.dashboard_maestro)
        elif modo == "Técnico":
            self.dashboard_tecnico.activar_modo_vista_admin(True)
            self.dashboard_tecnico.set_usuario(correo=correo, carnet=carnet)
            self.stack.setCurrentWidget(self.dashboard_tecnico)

    def _on_salir_modo_vista(self):
        self.rol_visual = self.rol_real
        self.dashboard_maestro.activar_modo_vista_admin(False)
        self.dashboard_tecnico.activar_modo_vista_admin(False)
        self.stack.setCurrentWidget(self.dashboard_admin)

    def _on_cerrar_sesion(self):
        self.rol_real = None
        self.rol_visual = None
        self.pantalla_cuentas.limpiar()
        self.pantalla_incidencias_admin.limpiar()
        self.pantalla_configuracion.limpiar()
        self.pantalla_laboratorios.limpiar()
        self.dashboard_maestro.activar_modo_vista_admin(False)
        self.dashboard_tecnico.activar_modo_vista_admin(False)
        self.stack.setCurrentWidget(self.cerrar_sesion)
        self.cerrar_sesion.iniciar()


def cargar_estilos(app: QApplication, ruta: str | Path | None = None):
    """Carga la hoja QSS y resuelve sus imágenes desde cualquier carpeta actual."""
    ruta_estilos = Path(ruta) if ruta is not None else Path("resources/styles.css")
    if not ruta_estilos.is_absolute():
        ruta_estilos = BASE_DIR / ruta_estilos
    ruta_estilos = ruta_estilos.resolve()
    if not ruta_estilos.is_file():
        raise FileNotFoundError(f"No se encontró la hoja de estilos: {ruta_estilos}")

    estilos = ruta_estilos.read_text(encoding="utf-8")
    estilos = re.sub(
        r"url\((resources/[^)]+)\)",
        lambda coincidencia: (
            f'url("{(BASE_DIR / coincidencia.group(1)).as_posix()}")'
        ),
        estilos,
    )
    app.setStyleSheet(estilos)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    cargar_estilos(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
