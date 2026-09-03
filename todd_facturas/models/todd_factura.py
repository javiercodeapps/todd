import json
import logging
import os
from datetime import date

import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

PROVINCIANET_URL = 'https://service-payment.provincianet.com.ar/api/v1/service/preorder'
SERVICIOS = {
    'E': 'Energía',
    'A': 'Agua',
    'T': 'Telefonía',
    'I': 'Internet',
    'S': 'Sepelio',
    'N': 'Nichos',
}


class ToddFactura(models.Model):
    _name = 'todd.factura'
    _description = 'Factura Todd'
    _order = 'fecha_emision desc, referencia'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, index=True)
    referencia = fields.Char(string='Referencia', index=True)
    nro_usuario = fields.Char(string='Nro. Usuario')
    periodo = fields.Char(string='Periodo', size=6)
    punto_venta = fields.Integer(string='Punto de Venta')
    nro_factura = fields.Integer(string='Nro. Factura')
    numero_completo = fields.Char(string='Número', compute='_compute_numero', store=True)
    fecha_emision = fields.Date(string='Fecha Emisión', index=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento')
    importe = fields.Float(string='Importe', digits=(12, 2))
    archivo_pdf = fields.Char(string='Archivo PDF')
    cod_pago_electronico = fields.Char(string='Cód. Pago Electrónico')
    cod_pago_electronico_otros = fields.Char(string='Cód. Pago Electrónico Otros')
    estado_pago = fields.Selection([('pagado', 'Pagado'), ('adeudado', 'Adeudado')], string='Estado', default='adeudado', index=True)
    domicilio = fields.Char(string='Domicilio')
    servicio = fields.Selection([
        ('E', 'Energía'), ('A', 'Agua'), ('T', 'Telefonía'),
        ('I', 'Internet'), ('S', 'Sepelio'), ('N', 'Nichos')
    ], string='Servicio', index=True)
    importe_2do_vencimiento = fields.Float(string='Importe 2do Venc.', digits=(12, 2))
    codigo_estado = fields.Char(string='Código Estado')
    dni = fields.Char(string='DNI')
    archivo_pdf_ruta = fields.Char(string='Ruta PDF')
    pdf_disponible = fields.Boolean(string='PDF Disponible', compute='_compute_pdf_disponible')

    @api.depends('punto_venta', 'nro_factura')
    def _compute_numero(self):
        for r in self:
            r.numero_completo = f'{r.punto_venta:04d}-{r.nro_factura:08d}' if r.punto_venta and r.nro_factura else ''

    def _compute_pdf_disponible(self):
        for r in self:
            r.pdf_disponible = r.archivo_pdf_ruta and os.path.exists(r.archivo_pdf_ruta)

    def action_registrar_pago(self):
        for r in self:
            r.estado_pago = 'pagado'
        return True

    def generar_url_provincianet(self):
        self.ensure_one()
        partner = self.partner_id
        partes = (partner.name or '').split()
        last_name = partes[0] if partes else ''
        first_name = ' '.join(partes[1:]) if len(partes) > 1 else last_name

        hoy = date.today()
        if self.fecha_vencimiento and hoy > self.fecha_vencimiento:
            monto = self.importe_2do_vencimiento or self.importe
        else:
            monto = self.importe

        socio = partner.todd_nro_socio or self.referencia or '0'
        try:
            document_number = '%08d' % int(socio)
        except (TypeError, ValueError):
            document_number = str(socio).zfill(8)

        servicio_nombre = SERVICIOS.get(self.servicio, self.servicio or '')
        periodo = self.periodo or ''
        periodo_fmt = f'{periodo[4:6]}/{periodo[0:4]}' if len(periodo) == 6 else periodo

        payload = {
            'payer': {
                'first_name': first_name,
                'last_name': last_name,
                'email': partner.email or 'mail@todd.com.ar',
                'document_type': '1',
                'document_number': document_number,
                'gender': '1',
                'locked_payer': False,
            },
            'payments': [{
                'barcode': self.cod_pago_electronico_otros or '',
                'amount': f'{monto:.2f}',
                'service': servicio_nombre,
                'detail': f'{periodo_fmt} {servicio_nombre} {self.domicilio or ""}'.strip(),
            }],
        }
        api_key = (self.env['ir.config_parameter'].sudo().get_param(
            'todd.provincianet_api_key',
            'u1kRIYc6d9NSSHDsdbczTMChD4qSaQUPbw3M5ijg52GnW2du2m',
        ) or '').strip()
        try:
            response = requests.post(
                PROVINCIANET_URL,
                headers={'x-api-key': api_key, 'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=30,
            )
            data = response.json()
            url = (data.get('data') or {}).get('url') or ''
            return url.replace('\\', '') or False
        except Exception:
            _logger.exception('Provincia NET preorder failed for factura %s', self.id)
            return False


class ToddResetData(models.TransientModel):
    _name = 'todd.reset'
    _description = 'Limpiar Datos Todd'

    def action_eliminar_todo(self):
        """Eliminar todas las facturas, usuarios portal y partners todd"""
        _logger.warning('TODD: Iniciando limpieza de datos')

        # Eliminar facturas
        self.env.cr.execute("DELETE FROM todd_factura")
        _logger.warning('TODD: Facturas eliminadas')

        # Eliminar usuarios portal creados por todd (que tienen todd_nro_socio)
        self.env.cr.execute("""
            DELETE FROM res_users WHERE id IN (
                SELECT u.id FROM res_users u
                JOIN res_partner p ON u.partner_id = p.id
                WHERE p.todd_nro_socio IS NOT NULL
            )
        """)
        _logger.warning('TODD: Usuarios portal eliminados')

        # Eliminar partners todd
        self.env.cr.execute("DELETE FROM res_partner WHERE todd_nro_socio IS NOT NULL")
        _logger.warning('TODD: Partners eliminados')

        # Eliminar registros de importación
        self.env.cr.execute("DELETE FROM todd_txt_import")
        _logger.warning('TODD: Registros de importación eliminados')

        self.env.cr.commit()
        _logger.warning('TODD: Limpieza completada')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Limpieza Completada',
                'message': 'Se eliminaron todas las facturas, usuarios y partners de Todd',
                'type': 'success',
            }
        }
