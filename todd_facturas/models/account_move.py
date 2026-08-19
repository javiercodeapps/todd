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
    todd_estado_pago = fields.Selection([
        ('pagado', 'Pagado'),
        ('adeudado', 'Adeudado')
    ], string='Estado de Pago', default='adeudado')

    @api.depends('todd_archivo_pdf')
    def _compute_todd_pdf_ruta(self):
        config = self.env['ir.config_parameter'].sudo()
        portal_dir = config.get_param('todd.pdf_portal_dir', '/var/logs/data/facturas_web')
        for record in self:
            record.todd_pdf_ruta = os.path.join(portal_dir, record.todd_archivo_pdf) if record.todd_archivo_pdf else ''

    todd_pdf_ruta = fields.Char(compute='_compute_todd_pdf_ruta')
    todd_pdf_disponible = fields.Boolean(compute='_compute_todd_pdf_disponible')

    @api.depends('todd_pdf_ruta')
    def _compute_todd_pdf_disponible(self):
        for record in self:
            record.todd_pdf_disponible = os.path.exists(record.todd_pdf_ruta) if record.todd_pdf_ruta else False

    def action_registrar_pago(self):
        self.ensure_one()
        if self.todd_estado_pago == 'pagado':
            return True

        banco = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        if not banco:
            raise UserError('No se encontró un diario de Banco')

        pml = self.env['account.payment.method.line'].search([
            ('journal_id', '=', banco.id),
            ('payment_method_id.name', 'ilike', '%manual%'),
        ], limit=1)

        if not pml:
            pml = self.env['account.payment.method.line'].search([
                ('journal_id', '=', banco.id),
            ], limit=1)

        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': self.amount_total,
            'date': self.invoice_date,
            'journal_id': banco.id,
        }
        if pml:
            payment_vals['payment_method_line_id'] = pml.id

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()

        if payment.move_id and payment.move_id.line_ids:
            for line in self.line_ids:
                if line.account_id.account_type == 'asset_receivable':
                    for pmove in payment.move_id.line_ids:
                        if pmove.account_id.account_type == 'asset_receivable':
                            (line + pmove).reconcile()
                            break

        self.todd_estado_pago = 'pagado'
        return True