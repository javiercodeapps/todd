from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestToddApiCliente(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'PUCHIK NICOLAS',
            'vat': '30111222',
            'todd_nro_socio': '107482',
            'todd_nro_usuario': '010001904',
        })
        cls.factura = cls.env['todd.factura'].create({
            'partner_id': cls.partner.id,
            'referencia': '107482',
            'nro_usuario': '010001904',
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

    @patch('odoo.addons.todd_facturas.models.res_partner.requests.get')
    def test_estado_cliente_incluye_facturas_y_radius(self, mock_get):
        self.env['ir.config_parameter'].sudo().set_param('todd.radius_api_key', 'radius-key')
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'plan': '10mb', 'estado': 'activo'}
        mock_get.return_value = mock_resp
        data = self.env['res.partner'].todd_api_estado_cliente('107482')
        self.assertEqual(data['partner']['nro_socio'], '107482')
        self.assertEqual(len(data['facturas']), 1)
        self.assertEqual(data['facturas'][0]['numero'], '0001-00000123')
        self.assertEqual(data['facturas'][0]['servicio_nombre'], 'Internet')
        self.assertEqual(data['radius']['estado'], 'activo')
        self.assertFalse(data['radius_error'])
        mock_get.assert_called_once()
