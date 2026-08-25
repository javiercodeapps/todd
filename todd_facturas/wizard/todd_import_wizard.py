import base64
import os
import shutil
import logging
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddImportWizard(models.TransientModel):
    _name = 'todd.import.wizard'
    _description = 'Importar Facturas Todd'

    archivo_txt = fields.Binary(string='Archivo TXT', required=True)
    archivo_nombre = fields.Char(string='Nombre')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Listo')], default='draft')
    log = fields.Text(string='Log', readonly=True)
    total = fields.Integer(readonly=True)
    ok = fields.Integer(readonly=True)
    errores = fields.Integer(readonly=True)

    def action_importar(self):
        self.ensure_one()
        if not self.archivo_txt:
            raise UserError('Seleccione un TXT')

        contenido = base64.b64decode(self.archivo_txt).decode('latin-1')
        lineas = contenido.strip().split('\n')
        if len(lineas) < 2:
            raise UserError('TXT vacío')

        log = []
        total = ok = errores = 0

        for i, linea in enumerate(lineas[1:], 2):
            total += 1
            try:
                c = [x.strip() for x in linea.split(';')]
                if len(c) < 17:
                    continue

                nro_socio = c[0]
                nro_usuario = c[1]
                periodo = c[2]
                pto_venta = int(c[3])
                nro_fac = int(c[4])
                fecha_fac = datetime.strptime(c[5], '%d/%m/%Y').date()
                fecha_vto = datetime.strptime(c[6], '%d/%m/%Y').date()
                importe = float(c[7].replace(',', '.'))
                archivo_pdf = c[8]
                cod_pago = c[9].strip()
                cod_pago_otros = c[10].strip()
                estado_comp = c[11].strip()
                domicilio = c[12]
                nombre = c[13]
                servicio = c[14]
                importe_2do = float(c[15].replace(',', '.')) if c[15].strip() else 0
                dni = c[17].strip() if len(c) > 17 else ''

                # Partner
                partner = self.env['res.partner'].search([('todd_nro_socio', '=', nro_socio)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': nombre, 'todd_nro_socio': nro_socio, 'todd_nro_usuario': nro_usuario,
                        'street': domicilio, 'vat': dni if dni and dni != '0' else False
                    })
                partner.crear_usuario_portal_si_no_tiene()

                # PDF
                config = self.env['ir.config_parameter'].sudo()
                source_dir = config.get_param('todd.pdf_source_dir', '/var/log/odoo/data/facturas')
                portal_dir = config.get_param('todd.pdf_portal_dir', '/var/log/odoo/data/facturas_web')
                pdf_ruta = ''
                if os.path.exists(source_dir) and os.path.exists(portal_dir):
                    src = os.path.join(source_dir, archivo_pdf)
                    if os.path.exists(src):
                        try:
                            shutil.copy2(src, portal_dir)
                            pdf_ruta = os.path.join(portal_dir, archivo_pdf)
                        except: pass

                estado_pago = 'pagado' if 'Pagado' in estado_comp else 'adeudado'

                # Verificar duplicada
                existe = self.env.cr.execute(
                    "SELECT id FROM todd_factura WHERE partner_id=%s AND archivo_pdf=%s LIMIT 1",
                    (partner.id, archivo_pdf)
                )
                if self.env.cr.fetchone():
                    if 'Pagado' in estado_comp:
                        self.env.cr.execute(
                            "UPDATE todd_factura SET estado_pago='pagado' WHERE partner_id=%s AND archivo_pdf=%s",
                            (partner.id, archivo_pdf)
                        )
                    continue

                self.env.cr.execute(
                    """INSERT INTO todd_factura (partner_id, referencia, nro_usuario, periodo, punto_venta, nro_factura,
                       numero_completo, fecha_emision, fecha_vencimiento, importe, archivo_pdf, cod_pago_electronico,
                       cod_pago_electronico_otros, estado_pago, domicilio, servicio, importe_2do_vencimiento, dni,
                       archivo_pdf_ruta)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (partner.id, nro_socio, nro_usuario, periodo, pto_venta, nro_fac,
                     f'{pto_venta:04d}-{nro_fac:08d}', fecha_fac, fecha_vto, importe, archivo_pdf,
                     cod_pago, cod_pago_otros, estado_pago, domicilio, servicio, importe_2do,
                     dni, pdf_ruta)
                )
                ok += 1
            except Exception as e:
                errores += 1
                log.append(f'Línea {i}: ERROR - {e}')

        self.env.cr.commit()

        self.write({'state': 'done', 'log': '\n'.join(log), 'total': total, 'ok': ok, 'errores': errores})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'todd.factura',
            'view_mode': 'list',
            'target': 'current',
            'context': {'create': False}
        }
