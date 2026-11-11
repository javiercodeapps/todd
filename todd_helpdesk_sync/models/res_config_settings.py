from odoo import fields, models
from odoo.exceptions import UserError

from .todd_helpdesk_sync_client import (
    RemoteOdoo,
    ToddSyncConfigError,
    ToddSyncRemoteError,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    todd_helpdesk_sync_enabled = fields.Boolean(
        string="Replicar tickets nuevos a otro servidor",
        config_parameter="todd_helpdesk_sync.enabled",
        default=False,
        help="Al crear un ticket se encola un job queue_job que lo copia al "
        "Odoo remoto por XML-RPC.",
    )
    todd_helpdesk_sync_remote_url = fields.Char(
        string="URL del Odoo remoto",
        config_parameter="todd_helpdesk_sync.remote_url",
        help="Ejemplo: https://odoo.empresa.com (sin barra final).",
    )
    todd_helpdesk_sync_remote_db = fields.Char(
        string="Base de datos remota",
        config_parameter="todd_helpdesk_sync.remote_db",
    )
    todd_helpdesk_sync_remote_user = fields.Char(
        string="Usuario remoto",
        config_parameter="todd_helpdesk_sync.remote_user",
    )
    todd_helpdesk_sync_remote_key = fields.Char(
        string="API key / contraseña",
        config_parameter="todd_helpdesk_sync.remote_key",
        help="Usar una API key con permisos acotados, nunca la contraseña de "
        "administrador ni el admin_passwd. El valor se enmascara en la vista; "
        "como todo ir.config_parameter, sigue siendo legible por ORM.",
    )
    todd_helpdesk_sync_timeout = fields.Integer(
        string="Timeout de conexión (segundos)",
        config_parameter="todd_helpdesk_sync.timeout",
        default=15,
    )

    def action_todd_sync_test_connection(self):
        """Comprueba credenciales contra /xmlrpc/2/common desde los Ajustes."""
        self.ensure_one()
        config = {
            "url": (self.todd_helpdesk_sync_remote_url or "").strip().rstrip("/"),
            "db": (self.todd_helpdesk_sync_remote_db or "").strip(),
            "user": (self.todd_helpdesk_sync_remote_user or "").strip(),
            "key": self.todd_helpdesk_sync_remote_key or "",
            "timeout": self.todd_helpdesk_sync_timeout or 15,
        }
        try:
            client = RemoteOdoo(config)
        except (ToddSyncConfigError, ToddSyncRemoteError) as err:
            raise UserError(f"No se pudo conectar:\n\n{err}") from err
        raise UserError(
            f"Conexión correcta con {config['url']} "
            f"(base {config['db']}), uid remoto {client.uid}."
        )
