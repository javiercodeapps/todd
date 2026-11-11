from unittest import mock

from odoo.tests import TransactionCase

from odoo.addons.queue_job.tests.common import trap_jobs
from odoo.addons.todd_helpdesk_sync.models import (
    todd_helpdesk_sync_client as client_mod,
)
from odoo.addons.todd_helpdesk_sync.models.helpdesk_ticket import (
    TODD_SYNC_SKIP_CONTEXT,
)

CLIENT_PATH = "odoo.addons.todd_helpdesk_sync.models.helpdesk_ticket.RemoteOdoo"


class TestToddHelpdeskSync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._configure(enabled=True)

    @classmethod
    def _configure(cls, enabled=True, **overrides):
        params = {
            "todd_helpdesk_sync.enabled": "True" if enabled else "False",
            "todd_helpdesk_sync.remote_url": "https://remote.example.com",
            "todd_helpdesk_sync.remote_db": "remote_db",
            "todd_helpdesk_sync.remote_user": "sync@example.com",
            "todd_helpdesk_sync.remote_key": "secret-key",
            "todd_helpdesk_sync.timeout": "15",
        }
        params.update(overrides)
        icp = cls.env["ir.config_parameter"].sudo()
        for key, value in params.items():
            icp.set_param(key, value)

    def _ticket_vals(self, **extra):
        vals = {
            "name": "Corte de servicio",
            "description": "<p>Sin conexión desde ayer</p>",
            "partner_name": "Juan Pérez",
            "partner_email": "juan@example.com",
        }
        vals.update(extra)
        return vals

    def _create_ticket(self, **extra):
        # Se atrapan los jobs para no dejar registros queue.job en la BD de test.
        with trap_jobs():
            return self.env["helpdesk.ticket"].create(self._ticket_vals(**extra))

    def _mock_remote(self, existing=None, created=4242, related=None):
        """Sustituye RemoteOdoo por un cliente XML-RPC simulado."""
        related = related or {}
        client = mock.MagicMock()

        def execute(model, method, args, kwargs=None):
            if method == "search":
                if model == "helpdesk.ticket":
                    return existing or []
                return related.get(model, [])
            if method == "create":
                return created
            raise AssertionError(f"Llamada remota inesperada: {model}.{method}")

        client.execute.side_effect = execute
        return client

    # ------------------------------------------------------------------
    # Encolado al crear
    # ------------------------------------------------------------------

    def test_create_enqueues_job_when_enabled(self):
        with trap_jobs() as trap:
            ticket = self.env["helpdesk.ticket"].create(self._ticket_vals())
        trap.assert_jobs_count(1)
        call = trap.calls[0]
        self.assertEqual(call.method.__name__, "_todd_sync_push_remote")
        self.assertEqual(
            call.properties["identity_key"],
            f"todd_helpdesk_sync.ticket.{ticket.id}",
        )
        self.assertEqual(ticket.todd_sync_state, "pending")

    def test_no_job_when_disabled(self):
        self._configure(enabled=False)
        with trap_jobs() as trap:
            ticket = self.env["helpdesk.ticket"].create(self._ticket_vals())
        trap.assert_jobs_count(0)
        self.assertEqual(ticket.todd_sync_state, "none")

    def test_no_job_when_skip_context(self):
        # Evita bucles si el remoto también tiene instalado este módulo.
        with trap_jobs() as trap:
            ticket = (
                self.env["helpdesk.ticket"]
                .with_context(**{TODD_SYNC_SKIP_CONTEXT: True})
                .create(self._ticket_vals())
            )
        trap.assert_jobs_count(0)
        self.assertEqual(ticket.todd_sync_state, "none")

    # ------------------------------------------------------------------
    # Payload y envío
    # ------------------------------------------------------------------

    def test_payload_contains_basic_fields(self):
        ticket = self._create_ticket()
        payload = ticket._todd_sync_payload()
        self.assertEqual(payload["name"], "Corte de servicio")
        self.assertEqual(payload["partner_email"], "juan@example.com")
        self.assertEqual(payload["number"], ticket.number)
        self.assertEqual(payload["origin_id"], ticket.id)
        self.assertTrue(payload["company_name"])

    def test_push_remote_success(self):
        ticket = self._create_ticket()
        client = self._mock_remote()
        with mock.patch(CLIENT_PATH, return_value=client):
            ticket._todd_sync_push_remote()

        self.assertEqual(ticket.todd_sync_state, "done")
        self.assertEqual(ticket.todd_sync_remote_id, 4242)
        self.assertEqual(ticket.todd_sync_attempts, 1)
        self.assertFalse(ticket.todd_sync_error)

        create_calls = [
            call for call in client.execute.call_args_list if call.args[1] == "create"
        ]
        self.assertEqual(len(create_calls), 1)
        vals = create_calls[0].args[2][0]
        self.assertEqual(vals["number"], ticket.number)
        self.assertEqual(vals["name"], "Corte de servicio")
        self.assertEqual(vals["partner_email"], "juan@example.com")
        self.assertTrue(
            create_calls[0].args[3]["context"][TODD_SYNC_SKIP_CONTEXT]
        )

    def test_existing_remote_ticket_is_not_duplicated(self):
        ticket = self._create_ticket()
        client = self._mock_remote(existing=[777])
        with mock.patch(CLIENT_PATH, return_value=client):
            ticket._todd_sync_push_remote()

        self.assertEqual(ticket.todd_sync_state, "done")
        self.assertEqual(ticket.todd_sync_remote_id, 777)
        self.assertFalse(
            any(
                call.args[1] == "create"
                for call in client.execute.call_args_list
            )
        )

    def test_related_models_are_resolved_by_name(self):
        ticket = self._create_ticket()
        client = self._mock_remote(related={"res.company": [9]})
        with mock.patch(CLIENT_PATH, return_value=client):
            ticket._todd_sync_push_remote()

        create_calls = [
            call for call in client.execute.call_args_list if call.args[1] == "create"
        ]
        self.assertEqual(create_calls[0].args[2][0]["company_id"], 9)

    # ------------------------------------------------------------------
    # Errores y reintentos
    # ------------------------------------------------------------------

    def test_missing_config_marks_error_without_retry(self):
        self._configure(
            enabled=True, **{"todd_helpdesk_sync.remote_url": ""}
        )
        ticket = self._create_ticket()
        with trap_jobs() as trap:
            ticket._todd_sync_push_remote()
        self.assertEqual(ticket.todd_sync_state, "error")
        self.assertTrue(ticket.todd_sync_error)
        trap.assert_jobs_count(0)

    def test_remote_failure_marks_error_and_enqueues_retry(self):
        ticket = self._create_ticket()
        client = self._mock_remote()
        client.execute.side_effect = RuntimeError("connection refused")
        with mock.patch(CLIENT_PATH, return_value=client), trap_jobs() as trap:
            ticket._todd_sync_push_remote()

        self.assertEqual(ticket.todd_sync_state, "error")
        self.assertIn("connection refused", ticket.todd_sync_error)
        self.assertEqual(ticket.todd_sync_attempts, 1)
        trap.assert_jobs_count(1)
        self.assertEqual(trap.calls[0].properties.get("eta"), 60)

    def test_no_retry_after_max_attempts(self):
        ticket = self._create_ticket()
        ticket.sudo().write({"todd_sync_attempts": 5})
        client = self._mock_remote()
        client.execute.side_effect = RuntimeError("down")
        with mock.patch(CLIENT_PATH, return_value=client), trap_jobs() as trap:
            ticket._todd_sync_push_remote()
        trap.assert_jobs_count(0)

    def test_retry_button_resets_state(self):
        ticket = self._create_ticket()
        ticket.sudo().write(
            {
                "todd_sync_state": "error",
                "todd_sync_attempts": 3,
                "todd_sync_error": "boom",
            }
        )
        with trap_jobs() as trap:
            ticket.action_todd_sync_retry()
        trap.assert_jobs_count(1)
        self.assertEqual(ticket.todd_sync_state, "pending")
        self.assertEqual(ticket.todd_sync_attempts, 0)
        self.assertFalse(ticket.todd_sync_error)

    # ------------------------------------------------------------------
    # Capa XML-RPC (sin red)
    # ------------------------------------------------------------------

    def test_remote_odoo_authenticate_and_execute(self):
        proxy = mock.MagicMock()
        proxy.authenticate.return_value = 7
        proxy.execute_kw.return_value = 99
        config = {
            "url": "https://remote.example.com",
            "db": "remote_db",
            "user": "sync@example.com",
            "key": "secret-key",
            "timeout": 15,
        }
        with mock.patch.object(client_mod, "_server_proxy", return_value=proxy):
            client = client_mod.RemoteOdoo(config)
            self.assertEqual(client.uid, 7)
            self.assertEqual(client.execute("helpdesk.ticket", "create", [{}]), 99)
        proxy.execute_kw.assert_called_once()

    def test_bad_credentials_raise_config_error(self):
        proxy = mock.MagicMock()
        proxy.authenticate.return_value = False
        config = {
            "url": "https://remote.example.com",
            "db": "remote_db",
            "user": "sync@example.com",
            "key": "wrong",
            "timeout": 15,
        }
        with mock.patch.object(client_mod, "_server_proxy", return_value=proxy):
            with self.assertRaises(client_mod.ToddSyncConfigError):
                client_mod.RemoteOdoo(config)
