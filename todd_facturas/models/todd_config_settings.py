import os
from odoo import models, fields, api
from odoo.exceptions import UserError


class ToddConfigSettings(models.TransientModel):
    _name = 'todd.config.settings'
    _description = 'Configuración Todd Facturas'

    pdf_source_dir = fields.Char(
        string='Directorio Origen PDFs',
        default='/mnt/extra-addons/todd/facturas'
    )
    pdf_portal_dir = fields.Char(
        string='Directorio PDFs Web',
        default='/mnt/extra-addons/todd/facturas_web'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['ir.config_parameter'].sudo()
        res['pdf_source_dir'] = config.get_param('todd.pdf_source_dir', '/mnt/extra-addons/todd/facturas')
        res['pdf_portal_dir'] = config.get_param('todd.pdf_portal_dir', '/mnt/extra-addons/todd/facturas_web')
        return res

    def action_guardar(self):
        self.ensure_one()
        config = self.env['ir.config_parameter'].sudo()
        config.set_param('todd.pdf_source_dir', self.pdf_source_dir)
        config.set_param('todd.pdf_portal_dir', self.pdf_portal_dir)
        if not os.path.exists(self.pdf_portal_dir):
            try:
                os.makedirs(self.pdf_portal_dir)
            except OSError:
                pass

    def action_verificar(self):
        self.ensure_one()
        if os.path.exists(self.pdf_source_dir):
            pdfs = [f for f in os.listdir(self.pdf_source_dir) if f.endswith('.pdf')]
            raise UserError(f'PDFs encontrados: {len(pdfs)}')
        raise UserError(f'No existe: {self.pdf_source_dir}')