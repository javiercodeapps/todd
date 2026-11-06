from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestToddTxtImportPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Import = cls.env['todd.txt.import']
        cls.Partner = cls.env['res.partner']
        cls.Servicio = cls.env['todd.servicio']

    @staticmethod
    def _lp(dni):
        """Campos mínimos de una línea de TXT ya parseada."""
        return {
            'dni': dni,
            'nombre': 'CLIENTE PRUEBA',
            'domicilio': 'LAMADRID 250 - VASCA',
            'servicio': 'I',
            'nro_socio': '4259',
            'nro_usuario': '24566',
            'usuario': 'euskaldunakdenakbat',
        }

    def _orphan_id(self):
        partner = self.Partner.create({'name': 'Fantasma'})
        orphan_id = partner.id
        partner.unlink()
        return orphan_id

    def test_browse_no_valida_pero_exists_si(self):
        """browse(id) no consulta la BD; .exists() sí detecta el ID huérfano."""
        orphan_id = self._orphan_id()
        self.assertTrue(self.Partner.browse(orphan_id))
        self.assertFalse(self.Partner.browse(orphan_id).exists())

    def test_cache_dentro_de_savepoint_queda_huerfana(self):
        """Causa raíz: el rollback del savepoint no deshace el dict de Python."""
        partners_map = {}
        try:
            with self.env.cr.savepoint():
                partner = self.Partner.create({'name': 'Fantasma'})
                partners_map['99000001'] = partner.id
                raise RuntimeError('simula falla del flush al cerrar el savepoint')
        except RuntimeError:
            pass

        stale_id = partners_map['99000001']
        self.assertFalse(self.Partner.browse(stale_id).exists())

    def test_resolver_partner_repara_id_huerfano(self):
        """El helper descarta el ID huérfano, re-resuelve y refresca la caché."""
        orphan_id = self._orphan_id()
        lp = self._lp('99000002')
        partners_map = {'99000002': orphan_id}

        partner, created, error = self.Import._resolver_partner_para_linea(
            lp, partners_map,
        )

        self.assertFalse(error)
        self.assertTrue(partner.exists())
        self.assertNotEqual(partner.id, orphan_id)
        self.assertEqual(partners_map['99000002'], partner.id)
        self.assertTrue(created)

    def test_get_or_create_servicio_rechaza_partner_inexistente(self):
        """Antes del INSERT se valida el partner: error claro, sin FK violation."""
        orphan_id = self._orphan_id()
        ghost = self.Partner.browse(orphan_id)

        with self.assertRaises(ValueError):
            self.Import._get_or_create_servicio(ghost, self._lp('99000003'))

        self.assertFalse(self.Servicio.search([('partner_id', '=', orphan_id)]))

    def test_get_or_create_servicio_con_partner_valido(self):
        partner = self.Partner.create({'name': 'Cliente'})
        servicio, created = self.Import._get_or_create_servicio(
            partner, self._lp('99000004'),
        )
        self.assertTrue(created)
        self.assertTrue(servicio.exists())
        self.assertEqual(servicio.partner_id, partner)

    def test_factura_valida_partner_antes_del_insert(self):
        """La verificación previa evita el INSERT con una FK rota."""
        orphan_id = self._orphan_id()
        lp = self._lp('99000005')
        lp.update({
            'partner_id': orphan_id,
            'servicio_id': False,
            'pto_venta': 1,
            'nro_fac': 987654,
            'periodo': '202611',
            'fecha_fac': date.today(),
            'fecha_vto': date.today(),
            'importe': 100.0,
            'archivo_pdf': '',
            'cod_pago_electronico': '',
            'cod_pago_electronico_otros': '',
            'estado_comp': 'Adeudado',
            'importe_2do_venc': 0,
        })
        antes = self.env['todd.factura'].search_count([])

        with self.assertRaises(ValueError):
            self.Import._crear_o_actualizar_factura(lp, '')

        self.assertEqual(self.env['todd.factura'].search_count([]), antes)
