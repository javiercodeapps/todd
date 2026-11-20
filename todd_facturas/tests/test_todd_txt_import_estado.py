from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestToddTxtImportEstado(TransactionCase):
    """Clave compuesta + auditoría completa de cambios de ``estado_pago``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Import = cls.env['todd.txt.import']
        cls.Factura = cls.env['todd.factura']
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Cliente A', 'vat': '30111111111',
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Cliente B', 'vat': '30222222222',
        })
        cls.txt_import = cls.Import.create({'filename': '20260818.txt'})

    def _lp(self, **kw):
        lp = {
            'nro_socio': '1',
            'nro_usuario': '1',
            'periodo': '202608',
            'pto_venta': 11,
            'nro_fac': 123,
            'fecha_fac': date(2026, 8, 5),
            'fecha_vto': date(2026, 8, 20),
            'importe': 100.0,
            'archivo_pdf': '',
            'cod_pago_electronico': '',
            'cod_pago_electronico_otros': '',
            'estado_comp': 'Adeudado',
            'domicilio': '',
            'nombre': 'Cliente',
            'servicio': 'E',
            'importe_2do_venc': 0,
            'dni': '30111111111',
            'usuario': '',
            'line_num': 2,
            'partner_id': self.partner_a.id,
            'servicio_id': False,
        }
        lp.update(kw)
        return lp

    def _factura(self, **kw):
        return self.Factura.create({
            'partner_id': kw.get('partner_id', self.partner_a.id),
            'periodo': kw.get('periodo', '202608'),
            'punto_venta': kw.get('pto_venta', 11),
            'nro_factura': kw.get('nro_fac', 123),
            'fecha_emision': kw.get('fecha_fac', date(2026, 8, 5)),
            'importe': 100.0,
            'estado_pago': kw.get('estado_pago', 'adeudado'),
            'servicio': kw.get('servicio', 'E'),
            'codigo_estado': kw.get('codigo_estado', False),
        })

    def _mensajes_con(self, factura, texto):
        return factura.message_ids.filtered(
            lambda m: texto in (m.body or '')
        )

    def test_clave_compuesta_no_pisa_otra_factura(self):
        """Mismo numero_completo, distinto partner/periodo: antes se pisaba."""
        vigente = self._factura()
        historica = self._factura(
            partner_id=self.partner_b.id, periodo='201403',
        )
        self.assertEqual(vigente.numero_completo, historica.numero_completo)

        status = self.Import._crear_o_actualizar_factura(
            self._lp(partner_id=self.partner_b.id, periodo='201403',
                     estado_comp='Pagado', line_num=7),
            '', txt_nombre='20260818.txt', txt_import_id=self.txt_import.id,
        )

        self.assertEqual(status, 'updated')
        self.assertEqual(historica.estado_pago, 'pagado')
        self.assertEqual(vigente.estado_pago, 'adeudado',
                         'la clave vieja (solo numero) habría pisado la vigente')
        self.assertEqual(vigente.estado_historial_count, 0)
        self.assertEqual(historica.estado_historial_count, 1)

    def test_cambio_normal_registra_txt_en_chatter_e_historial(self):
        factura = self._factura()
        status = self.Import._crear_o_actualizar_factura(
            self._lp(estado_comp='Pagado', line_num=3),
            '', txt_nombre='20260818.txt', txt_import_id=self.txt_import.id,
        )

        self.assertNotEqual(status, 'ambiguo')
        self.assertEqual(factura.estado_pago, 'pagado')
        self.assertEqual(factura.ultimo_txt_estado, '20260818.txt')
        self.assertEqual(factura.ultimo_sentido_estado, 'pago')
        self.assertTrue(factura.fecha_ultimo_cambio_estado)
        self.assertEqual(factura.estado_historial_count, 1)

        h = factura.estado_historial_ids
        self.assertEqual(h.estado_anterior, 'adeudado')
        self.assertEqual(h.estado_nuevo, 'pagado')
        self.assertEqual(h.sentido, 'pago')
        self.assertEqual(h.origen, 'txt')
        self.assertEqual(h.txt_nombre, '20260818.txt')
        self.assertEqual(h.txt_import_id, self.txt_import)
        self.assertEqual(h.linea_txt, 3)
        self.assertEqual(h.estado_comp, 'Pagado')
        self.assertTrue(
            self._mensajes_con(factura, '20260818.txt'),
            'el chatter debe indicar desde qué TXT se cambió el estado',
        )

    def test_reversion_permitida_pero_marcada(self):
        """Pagado -> Adeudado puede pasar, pero queda señalado como excepción."""
        factura = self._factura(estado_pago='pagado')
        status = self.Import._crear_o_actualizar_factura(
            self._lp(estado_comp='Adeudado'),
            '', txt_nombre='20260815.txt',
        )
        self.assertNotEqual(status, 'ambiguo')
        self.assertEqual(factura.estado_pago, 'adeudado')
        self.assertEqual(factura.ultimo_sentido_estado, 'reversion')
        self.assertEqual(factura.ultimo_txt_estado, '20260815.txt')
        h = factura.estado_historial_ids
        self.assertEqual(len(h), 1)
        self.assertEqual(h.sentido, 'reversion')
        self.assertEqual(h.txt_nombre, '20260815.txt')
        self.assertTrue(self._mensajes_con(factura, '20260815.txt'))

    def test_sin_cambio_no_genera_historial_ni_chatter(self):
        factura = self._factura(estado_pago='pagado', codigo_estado='Pagado')
        antes = len(factura.message_ids)
        status = self.Import._crear_o_actualizar_factura(
            self._lp(estado_comp='Pagado'), '', txt_nombre='20260818.txt',
        )
        self.assertEqual(status, 'skipped')
        self.assertEqual(factura.estado_historial_count, 0)
        self.assertEqual(len(factura.message_ids), antes)

    def test_historial_acumula_todos_los_cambios(self):
        factura = self._factura()
        for estado, txt in (
            ('Pagado', 'a.txt'), ('Adeudado', 'b.txt'), ('Pagado', 'c.txt'),
        ):
            self.Import._crear_o_actualizar_factura(
                self._lp(estado_comp=estado), '', txt_nombre=txt,
            )
        self.assertEqual(factura.estado_pago, 'pagado')
        self.assertEqual(factura.estado_historial_count, 3)
        self.assertEqual(
            list(factura.estado_historial_ids.mapped('sentido')),
            ['pago', 'reversion', 'pago'],
        )
        self.assertEqual(
            list(factura.estado_historial_ids.mapped('txt_nombre')),
            ['c.txt', 'b.txt', 'a.txt'],
        )
        self.assertEqual(factura.ultimo_txt_estado, 'c.txt')

    def test_estado_comp_desconocido_no_toca_el_estado(self):
        factura = self._factura(estado_pago='pagado', codigo_estado='Pagado')
        self.Import._crear_o_actualizar_factura(
            self._lp(estado_comp='Raro'), '', txt_nombre='raro.txt',
        )
        self.assertEqual(factura.estado_pago, 'pagado')
        self.assertEqual(factura.estado_historial_count, 0)

    def test_normalizacion_estados(self):
        normalizar = self.Import._normalizar_estado_comp
        self.assertEqual(normalizar('Pagado'), 'pagado')
        self.assertEqual(normalizar('PAGADO'), 'pagado')
        self.assertEqual(normalizar('Adeudado'), 'adeudado')
        self.assertEqual(normalizar('No Pagado'), 'adeudado')
        self.assertIsNone(normalizar('quién sabe'))

    def test_linea_historica_no_toca_factura_vigente(self):
        factura = self._factura()
        status = self.Import._crear_o_actualizar_factura(
            self._lp(periodo='201403', fecha_fac=date(2014, 3, 1),
                     fecha_vto=date(2014, 3, 20), estado_comp='Pagado'),
            '', txt_nombre='20260815 (2).txt',
        )
        self.assertEqual(status, 'skipped')
        self.assertEqual(factura.estado_pago, 'adeudado')
        self.assertEqual(factura.estado_historial_count, 0)

    def test_coincidencia_ambigua_no_elige_al_azar(self):
        f1 = self._factura()
        f2 = self._factura()
        status = self.Import._crear_o_actualizar_factura(
            self._lp(estado_comp='Pagado'), '', txt_nombre='x.txt',
        )
        self.assertEqual(status, 'ambiguo')
        self.assertEqual(f1.estado_pago, 'adeudado')
        self.assertEqual(f2.estado_pago, 'adeudado')

    def test_accion_manual_tambien_queda_auditada(self):
        factura = self._factura()
        factura.action_registrar_pago()
        self.assertEqual(factura.estado_pago, 'pagado')
        self.assertEqual(factura.estado_historial_count, 1)
        self.assertEqual(factura.estado_historial_ids.origen, 'manual')
        self.assertFalse(factura.ultimo_txt_estado)
