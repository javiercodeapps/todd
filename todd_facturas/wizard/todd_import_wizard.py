import base64
import logging
from odoo import models, fields
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
    actualizadas = fields.Integer(readonly=True)
    errores = fields.Integer(readonly=True)
    omitidas = fields.Integer(readonly=True)

    def action_importar(self):
        self.ensure_one()
        if not self.archivo_txt:
            raise UserError('Seleccione un TXT')

        contenido = base64.b64decode(self.archivo_txt).decode('latin-1')
        lineas = contenido.split('\n')
        if len(lineas) < 2:
            raise UserError('TXT vacío')

        importer = self.env['todd.txt.import']
        source_dir = importer._get_pdf_dir()
        log = []
        total = ok = actualizadas = errores = omitidas = 0
        partners_map = {}

        for i, linea in enumerate(lineas[1:], 2):
            if not linea.strip():
                continue
            total += 1
            try:
                parsed = importer._parse_linea_txt(linea, i)
                if not parsed:
                    omitidas += 1
                    cols = len(linea.split(';'))
                    log.append(f'Línea {i}: omitida (columnas insuficientes: {cols})')
                    continue
                if parsed['nro_socio'] not in partners_map:
                    with self.env.cr.savepoint():
                        partner, _created = importer._get_or_create_partner_todd(parsed)
                        partners_map[parsed['nro_socio']] = partner.id
                parsed['partner_id'] = partners_map[parsed['nro_socio']]
                with self.env.cr.savepoint():
                    status = importer._crear_o_actualizar_factura(parsed, source_dir)
                if status == 'created':
                    ok += 1
                elif status == 'updated':
                    actualizadas += 1
            except Exception as e:
                errores += 1
                log.append(f'Línea {i}: ERROR - {e}')
                _logger.exception('TODD wizard: línea %s', i)

        if not log:
            log.append(
                f'OK: {ok} creadas, {actualizadas} actualizadas, {errores} errores, {omitidas} omitidas'
            )
        else:
            log.append(
                f'--- Resumen: {ok} creadas, {actualizadas} actualizadas, {errores} errores, {omitidas} omitidas ---'
            )

        self.write({
            'state': 'done',
            'log': '\n'.join(log),
            'total': total,
            'ok': ok,
            'actualizadas': actualizadas,
            'errores': errores,
            'omitidas': omitidas,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'todd.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
