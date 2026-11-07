from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestLoginLimpio(HttpCase):
    """El login del portal solo debe pedir DNI/CUIT y contraseña."""

    def test_login_sin_passkey_ni_restablecer_contrasena(self):
        html = self.url_open('/web/login').text

        # La leyenda DNI/CUIT confirma que la vista heredada se aplicó.
        self.assertIn('DNI/CUIT', html)

        # web.login_oauth genera el "- o -" y el botón "Usa una llave de acceso".
        self.assertNotIn('o_login_auth', html)
        self.assertNotIn('passkey_login_link', html)

        # Enlace "Restablecer contraseña" de auth_signup.login.
        self.assertNotIn('/web/reset_password', html)
