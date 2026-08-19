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

    def action_registrar_pago(self):
        """Registrar pago de la factura"""
        self.ensure_one()
        if self.todd_estado_pago == 'pagado':
            return True

        # Registrar el pago
        payment_method = self.env['account.payment.method'].search([
            ('code', '=', 'manual'),
            ('payment_type', '=', 'inbound')
        ], limit=1)

        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': self.amount_total,
            'date': self.invoice_date,
            'ref': f'Pago {self.name}',
            'journal_id': self.journal_id.id,
            'payment_method_id': payment_method.id if payment_method else False,
        })
        payment.action_post()

        # Reconciliar el pago con la factura
        if payment.move_id and payment.move_id.line_ids:
            for line in self.line_ids:
                if line.account_id.account_type == 'asset_receivable':
                    for pml in payment.move_id.line_ids:
                        if pml.account_id.account_type == 'asset_receivable':
                            (line + pml).reconcile()
                            break

        self.todd_estado_pago = 'pagado'
        return True