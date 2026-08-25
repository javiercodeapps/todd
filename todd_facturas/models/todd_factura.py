import os
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


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
