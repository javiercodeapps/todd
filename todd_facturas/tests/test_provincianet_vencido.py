import json
from datetime import date, timedelta
from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.todd_facturas.models.todd_factura import (
    decodificar_codigo_pago,
)

POST = 'odoo.addons.todd_facturas.models.todd_factura.requests.post'


def _barcode_30(vencimiento, importe, prefijo='001241770752', cola='05'):
    """Código de 30 dígitos: 12 id + DDMMYY + 10 centavos + 2 verificación."""
    return '%s%s%010d%s' % (
        prefijo,
        vencimiento.strftime('%d%m%y'),
        int(round(importe * 100)),
        cola,
    )


def _barcode_40(venc1, centavos1, venc2, centavos2,
                prefijo='001240481839', cola='01'):
    """Código de 40 dígitos con primer y segundo vencimiento."""
    return '%s%s%07d%s%07d%s' % (
        prefijo,
        venc1.strftime('%d%m%y'), centavos1,
        venc2.strftime('%d%m%y'), centavos2,
        cola,
    )


def _respuesta_ok(url):
    return {
        'status_code': 201,
        'text': json.dumps({'data': {'url': url}, 'message': 'Created'}),
        'json.return_value': {'data': {'url': url}, 'message': 'Created'},
    }


@tagged('post_install', '-at_install')
class TestDecodificarCodigoPago(TransactionCase):

    def test_30_digitos(self):
        self.assertEqual(
            decodificar_codigo_pago('001241793190161126000261516302'),
            [(date(2026, 11, 16), 26151.63)],
        )
        self.assertEqual(
            decodificar_codigo_pago('001241770752151026000170851305'),
            [(date(2026, 10, 15), 17085.13)],
        )

    def test_40_digitos_dos_vencimientos(self):
        self.assertEqual(
            decodificar_codigo_pago('0012404818391812170120164261217012190901'),
            [
                (date(2017, 12, 18), 1201.64),
                (date(2017, 12, 26), 1219.09),
            ],
        )

    def test_codigo_invalido(self):
        for barcode in (
            None, '', 'abc',
            '0012417931901611260002615163',           # largo incorrecto
            '001241793190999926000261516302',         # fecha imposible
            '00124179319016112600026151630X',         # no numérico
        ):
            self.assertEqual(decodificar_codigo_pago(barcode), [], barcode)


@tagged('post_install', '-at_install')
class TestProvincianetVencido(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date.today()
        cls.partner = cls.env['res.partner'].create({
            'name': 'FERMANELLI MARIA ELENA',
            'vat': '18586779',
            'email': 'mail@todd.com.ar',
        })
        cls.factura = cls.env['todd.factura'].create({
            'partner_id': cls.partner.id,
            'periodo': '202611',
            'punto_venta': 1,
            'nro_factura': 619207,
            'fecha_emision': cls.hoy - timedelta(days=10),
            'fecha_vencimiento': cls.hoy + timedelta(days=10),
            'importe': 26151.63,
            'importe_2do_vencimiento': 0,
            'estado_pago': 'adeudado',
            'servicio': 'I',
            'domicilio': 'ESPAÑA 461',
            'cod_pago_electronico_otros': _barcode_30(
                cls.hoy + timedelta(days=10), 26151.63,
            ),
            'dni': '18586779',
        })

    def _amount(self, mock_post):
        payload = json.loads(mock_post.call_args.kwargs['data'])
        return payload['payments'][0]['amount']

    def test_barcode_vigente_no_bloquea_y_postea(self):
        self.assertFalse(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            mock_post.return_value.configure_mock(
                **_respuesta_ok('https://netpagos.example/abc'))
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertEqual(url, 'https://netpagos.example/abc')
        self.assertFalse(error_msg)
        mock_post.assert_called_once()
        self.assertEqual(self._amount(mock_post), '26151.63')

    def test_barcode_vencido_no_postea(self):
        """Es el caso real de la factura 615660 (15/10/2026 ya vencido)."""
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_30(
                self.hoy - timedelta(days=10), 17085.13,
            ),
            'importe': 17085.13,
        })
        self.assertTrue(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertFalse(url)
        self.assertIn('Provincia NET no acepta facturas vencidas', error_msg)
        mock_post.assert_not_called()

    def test_fecha_vencimiento_de_respaldo_sin_barcode(self):
        self.factura.write({
            'cod_pago_electronico_otros': False,
            'fecha_vencimiento': self.hoy - timedelta(days=5),
        })
        self.assertTrue(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertFalse(url)
        self.assertTrue(error_msg)
        mock_post.assert_not_called()

    def test_barcode_vigente_prevalece_sobre_fecha_vencida(self):
        """El proveedor valida el barcode, no la fecha del TXT."""
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_30(
                self.hoy + timedelta(days=5), 26151.63,
            ),
            'fecha_vencimiento': self.hoy - timedelta(days=20),
            'importe_2do_vencimiento': 28000.0,
        })
        self.assertFalse(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            mock_post.return_value.configure_mock(
                **_respuesta_ok('https://netpagos.example/vigente'))
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertEqual(url, 'https://netpagos.example/vigente')
        self.assertFalse(error_msg)
        mock_post.assert_called_once()
        # No se manda el importe del 2do vencimiento: debe coincidir con el barcode.
        self.assertEqual(self._amount(mock_post), '26151.63')

    def test_40_digitos_segundo_vencimiento_vigente(self):
        """Con dos vencimientos se usa el importe del período vigente."""
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_40(
                self.hoy - timedelta(days=5), 2615163,
                self.hoy + timedelta(days=5), 2800000,
            ),
            'fecha_vencimiento': self.hoy - timedelta(days=5),
            'importe_2do_vencimiento': 28000.0,
        })
        self.assertFalse(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            mock_post.return_value.configure_mock(
                **_respuesta_ok('https://netpagos.example/2do'))
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertEqual(url, 'https://netpagos.example/2do')
        self.assertFalse(error_msg)
        mock_post.assert_called_once()
        self.assertEqual(self._amount(mock_post), '28000.00')

    def test_40_digitos_ambos_vencidos(self):
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_40(
                self.hoy - timedelta(days=20), 2615163,
                self.hoy - timedelta(days=5), 2800000,
            ),
        })
        self.assertTrue(self.factura.provincianet_bloqueada())
        with patch(POST) as mock_post:
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertFalse(url)
        self.assertTrue(error_msg)
        mock_post.assert_not_called()

    def test_respuesta_422_devuelve_mensaje_del_proveedor(self):
        """El parser existente sigue informando el error del proveedor."""
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_30(
                self.hoy + timedelta(days=5), 26151.63,
            ),
        })
        with patch(POST) as mock_post:
            mock_post.return_value.status_code = 422
            mock_post.return_value.text = json.dumps({
                'code': 422,
                'data': {'error': 'El servicio se encuentra vencido'},
                'message': 'Unprocessable Entity',
            })
            mock_post.return_value.json.return_value = {
                'code': 422,
                'data': {'error': 'El servicio se encuentra vencido'},
                'message': 'Unprocessable Entity',
            }
            url, error_msg = self.factura.generar_url_provincianet()
        self.assertFalse(url)
        self.assertEqual(error_msg, 'El servicio se encuentra vencido')

    def test_mensaje_incluye_fecha_y_alternativas(self):
        vencido = self.hoy - timedelta(days=10)
        self.factura.write({
            'cod_pago_electronico_otros': _barcode_30(vencido, 17085.13),
        })
        msg = self.factura.provincianet_mensaje_vencido()
        self.assertIn(vencido.strftime('%d/%m/%Y'), msg)
        self.assertIn('billeteras virtuales', msg)
        self.assertIn('cobranzas', msg)


@tagged('post_install', '-at_install')
class TestPortalProvincianetVencido(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hoy = date.today()
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Vencido',
            'login': 'portal_vencido_test',
            'password': 'portal_vencido_test',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })
        cls.factura_vencida = cls._crear_factura(
            615660, cls.hoy - timedelta(days=22),
            cls.hoy - timedelta(days=22), 17085.13,
        )
        cls.factura_vigente = cls._crear_factura(
            626730, cls.hoy + timedelta(days=10),
            cls.hoy + timedelta(days=10), 16939.99,
        )

    @classmethod
    def _crear_factura(cls, nro, fecha_vencimiento, venc_barcode, importe):
        return cls.env['todd.factura'].create({
            'partner_id': cls.portal_user.partner_id.id,
            'periodo': '202610',
            'punto_venta': 1,
            'nro_factura': nro,
            'fecha_emision': cls.hoy - timedelta(days=22),
            'fecha_vencimiento': fecha_vencimiento,
            'importe': importe,
            'estado_pago': 'adeudado',
            'servicio': 'I',
            'domicilio': 'Alberdi 490 casa 1',
            'cod_pago_electronico': '350005308',
            'cod_pago_electronico_otros': _barcode_30(venc_barcode, importe),
            'dni': '06198292',
        })

    def test_boton_oculto_y_aviso_con_alternativas(self):
        self.authenticate('portal_vencido_test', 'portal_vencido_test')
        response = self.url_open(f'/my/factura/{self.factura_vencida.id}/pago')
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertNotIn('/provincianet', html)
        self.assertIn('Provincia NET no acepta facturas vencidas', html)
        self.assertIn('Billeteras Virtuales', html)

    def test_boton_visible_con_barcode_vigente(self):
        self.authenticate('portal_vencido_test', 'portal_vencido_test')
        html = self.url_open(
            f'/my/factura/{self.factura_vigente.id}/pago').text
        self.assertIn(
            f'/my/factura/{self.factura_vigente.id}/provincianet', html)
        self.assertNotIn('Provincia NET no acepta facturas vencidas', html)
