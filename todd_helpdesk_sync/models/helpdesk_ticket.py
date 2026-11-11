import logging

from odoo import api, fields, models

from .todd_helpdesk_sync_client import (
    RemoteOdoo,
    ToddSyncConfigError,
    check_config,
)

_logger = logging.getLogger(__name__)

# Número máximo de intentos y backoff (segundos) entre ellos.
TODD_SYNC_MAX_ATTEMPTS = 5
TODD_SYNC_BACKOFF = 60

# Contexto que evita bucles si el otro servidor también tiene este módulo.
TODD_SYNC_SKIP_CONTEXT = "todd_helpdesk_sync_skip"

SYNC_STATES = [
    ("none", "No enviado"),
    ("pending", "Pendiente"),
    ("done", "Enviado"),
    ("error", "Error"),
]


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    todd_sync_state = fields.Selection(
        SYNC_STATES,
        string="Réplica en servidor",
        default="none",
        readonly=True,
        copy=False,
    )
    todd_sync_remote_id = fields.Integer(
        string="ID ticket remoto", readonly=True, copy=False
    )
    todd_sync_date = fields.Datetime(
        string="Fecha de réplica", readonly=True, copy=False
    )
    todd_sync_error = fields.Text(
        string="Último error de réplica", readonly=True, copy=False
    )
    todd_sync_attempts = fields.Integer(
        string="Intentos de réplica", default=0, readonly=True, copy=False
    )

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    @api.model
    def _todd_sync_config(self):
        """Lee los parámetros desde ir.config_parameter (valores siempre str)."""
        icp = self.env["ir.config_parameter"].sudo()
        try:
            timeout = max(1, int(icp.get_param("todd_helpdesk_sync.timeout", "15")))
        except (TypeError, ValueError):
            timeout = 15
        enabled = str(
            icp.get_param("todd_helpdesk_sync.enabled", "False")
        ).strip().lower() in ("1", "true", "yes", "on")
        return {
            "enabled": enabled,
            "url": (icp.get_param("todd_helpdesk_sync.remote_url") or "")
            .strip()
            .rstrip("/"),
            "db": (icp.get_param("todd_helpdesk_sync.remote_db") or "").strip(),
            "user": (icp.get_param("todd_helpdesk_sync.remote_user") or "").strip(),
            "key": (icp.get_param("todd_helpdesk_sync.remote_key") or "").strip(),
            "timeout": timeout,
        }

    # ------------------------------------------------------------------
    # Hook de creación
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        tickets._todd_sync_schedule()
        return tickets

    def _todd_sync_schedule(self):
        """Marca los tickets como pendientes y encola un job por ticket."""
        config = self._todd_sync_config()
        if not config["enabled"] or self.env.context.get(TODD_SYNC_SKIP_CONTEXT):
            return
        self.write(
            {
                "todd_sync_state": "pending",
                "todd_sync_error": False,
                "todd_sync_attempts": 0,
            }
        )
        for ticket in self:
            ticket._todd_sync_enqueue()

    def _todd_sync_enqueue(self, eta=None):
        """Encola la copia. El identity_key evita jobs duplicados por ticket.

        Se usa ``sudo()`` porque el ticket pudo crearlo un usuario de portal
        desde el formulario web: el job es una integración de sistema y no debe
        depender de los permisos (ni de las record rules) de quien lo creó.
        """
        self.ensure_one()
        self.sudo().with_delay(
            channel="root",
            identity_key=f"todd_helpdesk_sync.ticket.{self.id}",
            description=f"Replicar ticket {self.number or self.id} al Odoo remoto",
            eta=eta,
        )._todd_sync_push_remote()

    def action_todd_sync_retry(self):
        """Botón 'Reenviar al servidor': reinicia el contador de intentos."""
        self.ensure_one()
        self.sudo().write(
            {
                "todd_sync_state": "pending",
                "todd_sync_error": False,
                "todd_sync_attempts": 0,
            }
        )
        self._todd_sync_enqueue()
        return True

    # ------------------------------------------------------------------
    # Job
    # ------------------------------------------------------------------

    def _todd_sync_push_remote(self):
        """Job de queue_job: copia este ticket al Odoo remoto.

        Los reintentos se encadenan aquí (en vez de usar RetryableJobError)
        porque queue_job hace rollback de todo lo escrito dentro de ``perform``
        cuando reintenta: así el estado y el último error del ticket quedan
        siempre persistidos y visibles en la ficha.
        """
        self.ensure_one()
        ticket = self.sudo()
        if ticket.todd_sync_state == "done" and ticket.todd_sync_remote_id:
            return "Ya replicado"

        attempt = ticket.todd_sync_attempts + 1
        ticket.write(
            {"todd_sync_state": "pending", "todd_sync_attempts": attempt}
        )
        try:
            remote_id = ticket._todd_sync_send()
        except ToddSyncConfigError as err:
            # Error permanente: reintentar no sirve de nada.
            ticket.write(
                {"todd_sync_state": "error", "todd_sync_error": str(err)}
            )
            return f"Error de configuración: {err}"
        except Exception as err:  # fallo de red, del remoto o inesperado
            _logger.warning(
                "Todd sync: fallo al replicar ticket %s (intento %s/%s): %s",
                ticket.number,
                attempt,
                TODD_SYNC_MAX_ATTEMPTS,
                err,
                exc_info=True,
            )
            ticket.write(
                {"todd_sync_state": "error", "todd_sync_error": str(err)}
            )
            if attempt < TODD_SYNC_MAX_ATTEMPTS:
                ticket._todd_sync_enqueue(eta=TODD_SYNC_BACKOFF * attempt)
            return f"Error: {err}"

        ticket.write(
            {
                "todd_sync_state": "done",
                "todd_sync_remote_id": remote_id,
                "todd_sync_error": False,
                "todd_sync_date": fields.Datetime.now(),
            }
        )
        return f"Ticket remoto #{remote_id}"

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------

    def _todd_sync_payload(self):
        """Snapshot de los datos básicos que se copian al otro servidor.

        Se devuelve como dict para que el transporte sea intercambiable: hoy
        se traduce a ``vals`` de ``helpdesk.ticket.create`` en el remoto, pero
        un futuro endpoint REST podría publicar este mismo payload.
        """
        self.ensure_one()
        return {
            "origin_id": self.id,
            "origin_number": self.number,
            "origin_url": self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", ""),
            "number": self.number or "/",
            "name": self.name or "",
            "description": self.description or "",
            "partner_name": self.partner_name or False,
            "partner_email": self.partner_email or False,
            "priority": self.priority or "1",
            "team_name": self.team_id.name or False,
            "category_name": self.category_id.name or False,
            "channel_name": self.channel_id.name or False,
            "stage_name": self.stage_id.name or False,
            "company_name": self.company_id.name or False,
            "create_date": self.create_date
            and fields.Datetime.to_string(self.create_date)
            or False,
            "last_stage_update": self.last_stage_update
            and fields.Datetime.to_string(self.last_stage_update)
            or False,
            "assigned_date": self.assigned_date
            and fields.Datetime.to_string(self.assigned_date)
            or False,
        }

    def _todd_sync_send(self):
        """Crea el ticket en el Odoo remoto y devuelve su id.

        Idempotencia: antes de crear se busca por ``number``; si ya existe se
        devuelve ese id en lugar de duplicar el ticket.
        """
        self.ensure_one()
        config = self._todd_sync_config()
        check_config(config)
        payload = self._todd_sync_payload()
        client = RemoteOdoo(config)

        existing = client.execute(
            "helpdesk.ticket",
            "search",
            [[("number", "=", payload["number"])]],
            {"limit": 1},
        )
        if existing:
            return existing[0]

        vals = {
            "number": payload["number"],
            "name": payload["name"] or "(sin título)",
            "description": payload["description"] or "<p></p>",
            "partner_name": payload["partner_name"],
            "partner_email": payload["partner_email"],
            "priority": payload["priority"],
        }
        for key in ("last_stage_update", "assigned_date"):
            if payload[key]:
                vals[key] = payload[key]

        # Los ids locales no existen en el remoto: se resuelven por nombre.
        # Es best-effort; si no hay coincidencia se deja el default del remoto.
        for name_key, remote_model, remote_field in (
            ("team_name", "helpdesk.ticket.team", "team_id"),
            ("category_name", "helpdesk.ticket.category", "category_id"),
            ("channel_name", "helpdesk.ticket.channel", "channel_id"),
            ("company_name", "res.company", "company_id"),
        ):
            name = payload[name_key]
            if not name:
                continue
            ids = client.execute(
                remote_model, "search", [[("name", "=", name)]], {"limit": 1}
            )
            if ids:
                vals[remote_field] = ids[0]

        # El contexto evita que el remoto (si también tiene este módulo)
        # vuelva a replicar el ticket hacia acá.
        return client.execute(
            "helpdesk.ticket",
            "create",
            [vals],
            {"context": {TODD_SYNC_SKIP_CONTEXT: True}},
        )
