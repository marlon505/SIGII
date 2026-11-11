"""Cliente JSON para una API externa configurada mediante variables de entorno."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
import json
import os
import socket

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class ExternalAPIError(RuntimeError):
    """Error de configuración, transporte o respuesta de la API externa."""


@dataclass(frozen=True)
class APIConfig:
    base_url: str
    api_key: Optional[str] = field(default=None, repr=False)
    timeout: float = 10.0

    @classmethod
    def from_env(
        cls,
        base_url: Optional[str] = None,
        include_api_key: bool = True,
    ) -> "APIConfig":
        base_url = (
            base_url
            if base_url is not None
            else os.getenv("EXTERNAL_API_BASE_URL", "http://127.0.0.1:8000")
        ).strip()
        if not base_url:
            raise ExternalAPIError(
                "La API externa no está configurada. Define EXTERNAL_API_BASE_URL en .env."
            )

        parsed_url = urlsplit(base_url)
        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ExternalAPIError("EXTERNAL_API_BASE_URL debe ser una URL HTTP(S) válida.")

        if parsed_url.scheme != "https" and parsed_url.hostname not in (
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            raise ExternalAPIError("La API externa debe usar HTTPS fuera de localhost.")

        try:
            timeout = float(os.getenv("EXTERNAL_API_TIMEOUT", "10"))
        except ValueError as error:
            raise ExternalAPIError("EXTERNAL_API_TIMEOUT debe ser un número válido.") from error
        if not 1 <= timeout <= 60:
            raise ExternalAPIError("EXTERNAL_API_TIMEOUT debe estar entre 1 y 60 segundos.")

        return cls(
            base_url=base_url.rstrip("/") + "/",
            api_key=(os.getenv("EXTERNAL_API_KEY") or None) if include_api_key else None,
            timeout=timeout,
        )


def request_json(
    path: str,
    method: str = "GET",
    payload: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    base_url: Optional[str] = None,
) -> Any:
    """Realiza una solicitud JSON a una ruta relativa de la API configurada."""
    config = APIConfig.from_env(
        base_url=base_url,
        include_api_key=base_url is None,
    )
    parsed_path = urlsplit(path or "")
    segmentos = parsed_path.path.split("/")
    if (
        not isinstance(path, str)
        or parsed_path.scheme
        or parsed_path.netloc
        or parsed_path.fragment
        or any(segmento in (".", "..") for segmento in segmentos)
    ):
        raise ValueError("La ruta de la API debe ser relativa y no contener segmentos '..'.")

    url = urljoin(config.base_url, path.lstrip("/"))
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if config.api_key:
        request_headers["Authorization"] = f"Bearer {config.api_key}"

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=config.timeout) as response:
            contenido = response.read()
    except HTTPError as error:
        raise ExternalAPIError(f"La API respondió con HTTP {error.code}.") from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise ExternalAPIError(f"No se pudo completar la solicitud a la API: {error}") from error

    if not contenido:
        return None
    try:
        return json.loads(contenido.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalAPIError("La API no devolvió una respuesta JSON válida.") from error


# Consolidado desde services/jsonplaceholder_service.py: integracion JSONPlaceholder.
"""Acceso de demostración a las publicaciones de JSONPlaceholder.dev."""



BASE_URL = os.getenv(
    "JSONPLACEHOLDER_API_BASE_URL",
    "https://jsonplaceholder.typicode.com",
).strip()


def obtener_publicaciones() -> list[dict[str, Any]]:
    """Obtiene y valida las publicaciones ficticias expuestas por la API."""
    respuesta = request_json("posts", base_url=BASE_URL)
    if not isinstance(respuesta, list):
        raise ExternalAPIError("La API de demostración no devolvió una lista de publicaciones.")

    publicaciones = []
    for indice, publicacion in enumerate(respuesta, start=1):
        if not isinstance(publicacion, dict):
            raise ExternalAPIError(
                f"La publicación número {indice} tiene un formato no válido."
            )
        if not all(campo in publicacion for campo in ("id", "userId", "title", "body")):
            raise ExternalAPIError(
                f"La publicación número {indice} no contiene los campos requeridos."
            )
        if (
            not isinstance(publicacion["id"], int)
            or not isinstance(publicacion["userId"], int)
            or not isinstance(publicacion["title"], str)
            or not isinstance(publicacion["body"], str)
        ):
            raise ExternalAPIError(
                f"La publicación número {indice} contiene valores con formato no válido."
            )

        publicaciones.append({
            "id": publicacion["id"],
            "usuario_id": publicacion["userId"],
            "titulo": publicacion["title"],
            "contenido": publicacion["body"],
        })

    if not publicaciones:
        raise ExternalAPIError("La API de demostración no devolvió publicaciones.")
    return publicaciones
