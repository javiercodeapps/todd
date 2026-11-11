"""Cliente XML-RPC mínimo para el Odoo remoto.

Se mantiene separado del modelo para poder cambiar el transporte (REST,
JSON-RPC, ...) sin tocar la lógica de negocio, y para que los tests puedan
sustituir ``RemoteOdoo`` por un mock sin abrir conexiones de red.
"""

import xmlrpc.client


class ToddSyncConfigError(Exception):
    """Configuración incompleta o credenciales inválidas.

    No tiene sentido reintentar: hay que corregir los Ajustes.
    """


class ToddSyncRemoteError(Exception):
    """Fallo transitorio al hablar con el servidor remoto; se reintenta."""


class _TimeoutMixin:
    """Fija un timeout en la conexión HTTP/HTTPS del ServerProxy.

    Sin esto, una llamada de red colgada puede dejar un worker de queue_job
    bloqueado indefinidamente.
    """

    def __init__(self, timeout, **kwargs):
        super().__init__(**kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


class _HttpTimeoutTransport(_TimeoutMixin, xmlrpc.client.Transport):
    pass


class _HttpsTimeoutTransport(_TimeoutMixin, xmlrpc.client.SafeTransport):
    pass


def _server_proxy(url, path, timeout):
    transport_cls = (
        _HttpsTimeoutTransport
        if url.startswith("https://")
        else _HttpTimeoutTransport
    )
    return xmlrpc.client.ServerProxy(
        f"{url}{path}", transport=transport_cls(timeout), allow_none=True
    )


def check_config(config):
    """Valida que exista lo mínimo indispensable para abrir la conexión."""
    labels = {
        "url": "URL del Odoo remoto",
        "db": "base de datos remota",
        "user": "usuario remoto",
        "key": "API key / contraseña",
    }
    missing = [label for key, label in labels.items() if not config.get(key)]
    if missing:
        raise ToddSyncConfigError(
            "Falta configurar en Ajustes > Helpdesk > Réplica a otro servidor: "
            + ", ".join(missing)
            + "."
        )
    if not config["url"].startswith(("http://", "https://")):
        raise ToddSyncConfigError(
            "La URL del Odoo remoto debe empezar por http:// o https://."
        )


class RemoteOdoo:
    """Conexión autenticada contra otro Odoo a través de /xmlrpc/2/."""

    def __init__(self, config):
        check_config(config)
        self.config = config
        common = _server_proxy(config["url"], "/xmlrpc/2/common", config["timeout"])
        try:
            self.uid = common.authenticate(
                config["db"], config["user"], config["key"], {}
            )
        except Exception as err:
            raise ToddSyncRemoteError(
                f"No se pudo contactar {config['url']}/xmlrpc/2/common: {err}"
            ) from err
        if not self.uid:
            raise ToddSyncConfigError(
                f"El servidor remoto rechazó el usuario o la API key "
                f"({config['user']}@{config['db']})."
            )
        self.proxy = _server_proxy(
            config["url"], "/xmlrpc/2/object", config["timeout"]
        )

    def execute(self, model, method, args, kwargs=None):
        """Llama a ``execute_kw`` y normaliza cualquier fallo de red/servidor."""
        try:
            return self.proxy.execute_kw(
                self.config["db"],
                self.uid,
                self.config["key"],
                model,
                method,
                args,
                kwargs or {},
            )
        except Exception as err:
            raise ToddSyncRemoteError(
                f"{model}.{method} en el servidor remoto falló: {err}"
            ) from err
