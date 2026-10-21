from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestToddApiCliente(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'PUCHIK NICOLAS',
            'vat': '30111222',
        })
        cls.servicio = cls.env['todd.servicio'].create({
            'partner_id': cls.partner.id,
            'tipo': 'I',
            'nro_socio': '107482',
            'nro_usuario': '010001904',
            'nombre_usuario': 'puchiknicolas',
        })
        cls.factura = cls.env['todd.factura'].create({
            'partner_id': cls.partner.id,
            'servicio_id': cls.servicio.id,
            'periodo': '202608',
            'punto_venta': 1,
            'nro_factura': 123,
            'fecha_emision': '2026-08-01',
            'fecha_vencimiento': '2026-08-15',
            'importe': 17287.78,
            'estado_pago': 'adeudado',
            'servicio': 'I',
            'dni': '30111222',
        })

    def test_buscar_por_socio(self):
        partner = self.env['res.partner'].todd_buscar_por_numero('107482')
        self.assertEqual(partner, self.partner)

    def test_buscar_por_usuario(self):
        partner = self.env['res.partner'].todd_buscar_por_numero('010001904')
        self.assertEqual(partner, self.partner)

    def test_buscar_por_dni(self):
        partner = self.env['res.partner'].todd_buscar_por_numero('30111222')
        self.assertEqual(partner, self.partner)

    def test_buscar_inexistente(self):
        partner = self.env['res.partner'].todd_buscar_por_numero('99999999')
        self.assertFalse(partner)

    @patch('odoo.addons.todd_radius.models.todd_radius_userinfo.'
           'ToddRadiusUserinfo.radius_info_usuarios')
    def test_estado_cliente_incluye_facturas_y_radius(self, mock_info):
        mock_info.return_value = {
            'puchiknicolas': {
                'user_id': 42,
                'raduserinfo': {'id': 42, 'username': 'puchiknicolas', 'estado': 'activo'},
                'raduseracct': [],
                'radcheck': [],
                'radgroups': [],
            },
        }
        data = self.env['res.partner'].todd_api_estado_cliente('30111222')
        self.assertEqual(data['partner']['vat'], '30111222')
        self.assertEqual(len(data['servicios']), 1)
        self.assertEqual(data['servicios'][0]['nro_socio'], '107482')
        self.assertEqual(data['servicios'][0]['radius']['raduserinfo']['estado'], 'activo')
        self.assertFalse(data['servicios'][0]['radius_error'])
        self.assertEqual(len(data['facturas']), 1)
        self.assertEqual(data['facturas'][0]['numero'], '0001-00000123')
        self.assertEqual(data['facturas'][0]['servicio_nombre'], 'Internet')
        mock_info.assert_called_once()

    @patch('odoo.addons.todd_radius.models.todd_radius_userinfo.'
           'ToddRadiusUserinfo.radius_info_usuarios')
    def test_estado_cliente_radius_sin_usuario(self, mock_info):
        mock_info.return_value = {}
        data = self.env['res.partner'].todd_api_estado_cliente('30111222')
        self.assertEqual(data['servicios'][0]['radius_error'], 'Cliente no encontrado')
