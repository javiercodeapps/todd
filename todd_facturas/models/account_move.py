import os
import shutil
from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    todd_archivo_pdf = fields.Char(string='Archivo PDF')
    todd_nro_socio = fields.Char(string='Nro. Socio')
    todd_servicio = fields.Selection([
        ('E', 'Energía'), ('A', 'Agua'), ('T', 'Telefonía'),
        ('I', 'Internet'), ('S', 'Sepelio'), ('N', 'Nichos')
    ], string='Servicio')
    todd_periodo = fields.Char(string='Periodo', size=6)

    @api.depends('todd_archivo_pdf')
    def _compute_todd_pdf_ruta(self):
        config = self.env['ir.config_parameter'].sudo()
        portal_dir = config.get_param('todd.pdf_portal_dir', '/home/pepej/Desarrollo/todd/facturas_web')
        for record in self:
            record.todd_pdf_ruta = os.path.join(portal_dir, record.todd_archivo_pdf) if record.todd_archivo_pdf else ''

    todd_pdf_ruta = fields.Char(compute='_compute_todd_pdf_ruta')
    todd_pdf_disponible = fields.Boolean(compute='_compute_todd_pdf_disponible')

    @api.depends('todd_pdf_ruta')
    def _compute_todd_pdf_disponible(self):
        for record in self:
            record.todd_pdf_disponible = os.path.exists(record.todd_pdf_ruta) if record.todd_pdf_ruta else False

    def action_copiar_pdf(self):
        self.ensure_one()
        if not self.todd_archivo_pdf:
            raise UserError('No hay PDF configurado')

        config = self.env['ir.config_parameter'].sudo()
        source_dir = config.get_param('todd.pdf_source_dir', '/home/pepej/Desarrollo/todd/facturas')
        portal_dir = config.get_param('todd.pdf_portal_dir', '/home/pepej/Desarrollo/todd/facturas_web')

        source = os.path.join(source_dir, self.todd_archivo_pdf)
        if not os.path.exists(source):
            raise UserError(f'No existe: {source}')

        if not os.path.exists(portal_dir):
            os.makedirs(portal_dir)

        shutil.copy2(source, portal_dir)
        return True