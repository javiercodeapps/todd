from odoo.fields import Command
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalSoloPassword(HttpCase):
    """El portal solo debe ofrecer el cambio de contraseña."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Seguridad',
            'login': 'portal_seguridad_test',
            'password': 'portal_seguridad_test',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })

    def test_home_acceso_directo_cambio_password(self):
        self.authenticate('portal_seguridad_test', 'portal_seguridad_test')
        html = self.url_open('/my/home').text
        self.assertIn('Cambio de Contraseña', html)
        self.assertIn('Cambie su contraseña de acceso al portal', html)
        self.assertNotIn('Connection &amp; Security', html)
        self.assertNotIn('Conexión y Seguridad', html)

    def test_security_solo_cambio_password(self):
        self.authenticate('portal_seguridad_test', 'portal_seguridad_test')
        html = self.url_open('/my/security').text
        self.assertIn('Cambio de Contraseña', html)
        self.assertIn('portal_change_password', html)
        # El resto de las secciones de la página queda oculto
        self.assertIn("section:not([name='portal_change_password'])", html)
        # Secciones eliminadas directamente del HTML
        self.assertNotIn('Log out from all devices', html)
        self.assertNotIn('portal_deactivate_account_modal', html)
