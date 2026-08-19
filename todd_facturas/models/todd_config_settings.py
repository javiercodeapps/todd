import os
from odoo import models, fields, api
from odoo.exceptions import UserError


class ToddConfigSettings(models.TransientModel):
    _name = 'todd.config.settings'
    _description = 'Configuración Todd Facturas'

    pdf_source_dir = fields.Char(
        string='Directorio Origen PDFs',
        default='/var/logs/data/facturas'
    )
    pdf_portal_dir = fields.Char(
        string='Directorio PDFs Web',
        default='/var/logs/data/facturas_web'
    )
    txt_dir = fields.Char(
        string='Directorio TXTs',
        default='/var/logs/data/txts'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        config = self.env['ir.config_parameter'].sudo()
        res['pdf_source_dir'] = config.get_param('todd.pdf_source_dir', '/var/logs/data/facturas')
        res['pdf_portal_dir'] = config.get_param('todd.pdf_portal_dir', '/var/logs/data/facturas_web')
        res['txt_dir'] = config.get_param('todd.txt_dir', '/var/logs/data/txts')
        return res

    def action_guardar(self):
        self.ensure_one()
        config = self.env['ir.config_parameter'].sudo()
        config.set_param('todd.pdf_source_dir', self.pdf_source_dir)
        config.set_param('todd.pdf_portal_dir', self.pdf_portal_dir)
        config.set_param('todd.txt_dir', self.txt_dir)

        for d in [self.pdf_source_dir, self.pdf_portal_dir, self.txt_dir]:
            if d and not os.path.exists(d):
                try:
                    os.makedirs(d)
                except OSError:
                    pass

    def action_escanear(self):
        """Escanear directorio de TXTs"""
        self.ensure_one()
        txt_dir = self.txt_dir
        if not os.path.exists(txt_dir):
            raise UserError(f'No existe: {txt_dir}')

        from . import todd_txt_import
        nuevos = self.env['todd.txt.import'].action_escanear_archivos()
        raise UserError(f'Se encontraron {nuevos} archivos nuevos')