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
        source_dir = config.get_param('todd.pdf_source_dir', '/mnt/extra-addons/todd/facturas')
        portal_dir = config.get_param('todd.pdf_portal_dir', '/mnt/extra-addons/todd/facturas_web')

        if self.copiar_pdfs and not os.path.exists(portal_dir):
            try:
                os.makedirs(portal_dir)
            except OSError:
                pass

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
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('move_type', '=', 'out_invoice'), ('todd_archivo_pdf', '!=', False)],
            'target': 'current'
        }

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
        estado_comp = c[11].strip()
        domicilio = c[12]
        nombre = c[13]
        servicio = c[14]
        dni = c[17] if len(c) > 17 else ''

        partner = self.env['res.partner'].search([('todd_nro_socio', '=', nro_socio)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': nombre, 'todd_nro_socio': nro_socio, 'todd_nro_usuario': nro_usuario,
                'street': domicilio, 'vat': dni if dni and dni != '0' else False
            })

        # Crear usuario portal si no tiene
        if not partner.user_ids:
            portal_group = self.env.ref('base.group_portal')
            password = dni if dni and dni != '0' else nro_usuario
            login = nro_usuario
            # Verificar que el login no exista
            if self.env['res.users'].search([('login', '=', login)], limit=1):
                login = f'{nro_socio}'
            self.env['res.users'].create({
                'name': nombre,
                'login': login,
                'password': password,
                'partner_id': partner.id,
                'groups_id': [(6, 0, [portal_group.id])]
            })
            log.append(f'{nombre}: usuario portal creado (login: {login})')

        existe = self.env['account.move'].search([('partner_id', '=', partner.id), ('todd_archivo_pdf', '=', archivo_pdf)], limit=1)
        if existe:
            if 'Pagado' in estado_comp and existe.todd_estado_pago != 'pagado':
                existe.action_registrar_pago()
                log.append(f'{nombre}: actualizado a Pagado')
            elif 'Adeudado' in estado_comp and existe.todd_estado_pago != 'adeudado':
                existe.todd_estado_pago = 'adeudado'
                log.append(f'{nombre}: actualizado a Adeudado')
            else:
                log.append(f'{nombre}: ya existe sin cambios')
            return

        numero_factura = f'{pto_venta:04d}-{nro_fac:08d}'
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

        move.write({'name': numero_factura})
        move.action_post()

        if 'Pagado' in estado_comp:
            move.action_registrar_pago()

        if self.copiar_pdfs and archivo_pdf and os.path.exists(source_dir):
            src = os.path.join(source_dir, archivo_pdf)
            if os.path.exists(src) and os.path.exists(portal_dir):
                try:
                    shutil.copy2(src, portal_dir)
                except Exception:
                    pass

        log.append(f'{nombre}: factura {numero_factura} - {estado_comp}')