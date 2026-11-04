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

    def test_home_con_vista_traducida(self):
        """La herencia del portal no debe depender del texto traducido (arch_db)."""
        lang = self.env['res.lang'].search(
            [('code', 'in', ('es_ES', 'es_AR', 'es_419'))], limit=1)
        if not lang:
            self.skipTest('No hay idioma español instalado en la base')
        self.portal_user.lang = lang.code
        self.authenticate('portal_seguridad_test', 'portal_seguridad_test')
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Cambio de Contraseña', response.text)

    def test_home_tarjeta_facturas_apunta_a_mis_facturas(self):
        """La tarjeta de facturas del inicio lleva a /my/facturas."""
        self.authenticate('portal_seguridad_test', 'portal_seguridad_test')
        html = self.url_open('/my/home').text
        self.assertIn('href="/my/facturas"', html)
        self.assertNotIn('href="/my/invoices?filterby=invoices"', html)

    def test_facturas_muestra_nombre_usuario(self):
        """/my/facturas muestra el nombre del usuario como encabezado."""
        self.authenticate('portal_seguridad_test', 'portal_seguridad_test')
        response = self.url_open('/my/facturas')
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.text, r'<h2 class="mb-4">\s*Portal Seguridad\s*</h2>')

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
