import base64
import os
import shutil
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError


class ToddImportWizard(models.TransientModel):
    _name = 'todd.import.wizard'
    _description = 'Importar Facturas Todd'

    archivo_txt = fields.Binary(string='Archivo TXT', required=True)
    archivo_nombre = fields.Char(string='Nombre')
    journal_id = fields.Many2one('account.journal', string='Diario', domain="[('type','=','sale')]")
    copiar_pdfs = fields.Boolean(string='Copiar PDFs', default=True)
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Listo')], default='draft')
    log = fields.Text(string='Log', readonly=True)
    total = fields.Integer(readonly=True)
    ok = fields.Integer(readonly=True)
    errores = fields.Integer(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        j = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        if j:
            res['journal_id'] = j.id
        return res

    def action_importar(self):
        self.ensure_one()
        if not self.archivo_txt:
            raise UserError('Seleccione un TXT')

        contenido = base64.b64decode(self.archivo_txt).decode('latin-1')
        lineas = contenido.strip().split('\n')
        if len(lineas) < 2:
            raise UserError('TXT vacío')

        config = self.env['ir.config_parameter'].sudo()
        source_dir = config.get_param('todd.pdf_source_dir', '/home/pepej/Desarrollo/todd/facturas')
        portal_dir = config.get_param('todd.pdf_portal_dir', '/home/pepej/Desarrollo/todd/facturas_web')

        if self.copiar_pdfs and not os.path.exists(portal_dir):
            os.makedirs(portal_dir)

        log = []
        total = ok = errores = 0

        for i, linea in enumerate(lineas[1:], 2):
            total += 1
            try:
                self._procesar(linea, log, source_dir, portal_dir)
                ok += 1
            except Exception as e:
                errores += 1
                log.append(f'Línea {i}: ERROR - {e}')

        self.write({'state': 'done', 'log': '\n'.join(log), 'total': total, 'ok': ok, 'errores': errores})
        return {'type': 'ir.actions.act_window', 'res_model': 'todd.import.wizard', 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def _procesar(self, linea, log, source_dir, portal_dir):
        c = [x.strip() for x in linea.split(';')]
        if len(c) < 17:
            raise ValueError('Campos insuficientes')

        nro_socio, nro_usuario, periodo = c[0], c[1], c[2]
        pto_venta, nro_fac = int(c[3]), int(c[4])
        fecha_fac = datetime.strptime(c[5], '%d/%m/%Y').date()
        fecha_vto = datetime.strptime(c[6], '%d/%m/%Y').date()
        importe = float(c[7].replace(',', '.'))
        archivo_pdf = c[8]
        domicilio = c[12]
        nombre = c[13]
        servicio = c[14]
        dni = c[17] if len(c) > 17 else ''

        # Partner
        partner = self.env['res.partner'].search([('todd_nro_socio', '=', nro_socio)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': nombre, 'todd_nro_socio': nro_socio, 'todd_nro_usuario': nro_usuario,
                'street': domicilio, 'vat': dni if dni and dni != '0' else False
            })

        # Verificar duplicada
        existe = self.env['account.move'].search([('partner_id', '=', partner.id), ('todd_archivo_pdf', '=', archivo_pdf)], limit=1)
        if existe:
            log.append(f'{nombre}: ya existe')
            return

        # Número de factura: punto venta + número
        numero_factura = f'{pto_venta:04d}-{nro_fac:08d}'

        # Crear factura
        servicio_nombre = {'E': 'Energía', 'A': 'Agua', 'T': 'Telefonía', 'I': 'Internet', 'S': 'Sepelio', 'N': 'Nichos'}.get(servicio, servicio)

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fecha_fac,
            'invoice_date_due': fecha_vto,
            'journal_id': self.journal_id.id,
            'todd_archivo_pdf': archivo_pdf,
            'todd_nro_socio': nro_socio,
            'todd_servicio': servicio,
            'todd_periodo': periodo,
            'ref': numero_factura,
            'invoice_line_ids': [(0, 0, {
                'name': f'{servicio_nombre} - {periodo}',
                'quantity': 1,
                'price_unit': importe
            })]
        })

        # Asignar número de factura como nombre
        move.write({'name': numero_factura})

        # Confirmar factura automáticamente
        move.action_post()

        # Copiar PDF
        if self.copiar_pdfs and archivo_pdf:
            src = os.path.join(source_dir, archivo_pdf)
            if os.path.exists(src):
                shutil.copy2(src, portal_dir)

        log.append(f'{nombre}: factura {numero_factura} confirmada')