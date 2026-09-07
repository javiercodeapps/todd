import os
import logging
from datetime import datetime
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

BATCH_SIZE = 500


class ToddTxtImport(models.Model):
    _name = 'todd.txt.import'
    _description = 'Importación TXT Todd'
    _order = 'create_date desc'

    filename = fields.Char(string='Archivo', required=True, readonly=True)
    filepath = fields.Char(string='Ruta', readonly=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('done', 'Completado'),
        ('error', 'Error')
    ], string='Estado', default='pending', readonly=True)
    fecha_archivo = fields.Datetime(string='Fecha Archivo', readonly=True)
    fecha_importacion = fields.Datetime(string='Fecha Importación', readonly=True)
    total_lineas = fields.Integer(string='Total Líneas', readonly=True)
    lineas_procesadas = fields.Integer(string='Líneas Procesadas', readonly=True)
    lineas_omitidas = fields.Integer(string='Líneas Omitidas', readonly=True)
    facturas_creadas = fields.Integer(string='Facturas Creadas', readonly=True)
    facturas_actualizadas = fields.Integer(string='Facturas Actualizadas', readonly=True)
    partners_creados = fields.Integer(string='Partners Creados', readonly=True)
    usuarios_creados = fields.Integer(string='Usuarios Creados', readonly=True)
    errores = fields.Integer(string='Errores', readonly=True)
    log = fields.Text(string='Log', readonly=True)

    @api.model
    def _get_txt_dir(self):
        config = self.env['ir.config_parameter'].sudo()
        return config.get_param('todd.txt_dir', '/var/logs/data/txts')

    @api.model
    def _get_pdf_dir(self):
        config = self.env['ir.config_parameter'].sudo()
        return config.get_param('todd.pdf_source_dir', '/var/log/odoo/data/facturas')

    @api.model
    def action_escanear_archivos(self):
        txt_dir = self._get_txt_dir()
        _logger.info('TODD: Escaneando directorio %s', txt_dir)
        if not os.path.exists(txt_dir):
            _logger.warning('TODD: Directorio TXT no existe: %s', txt_dir)
            return 0

        archivos_existentes = set(self.search([]).mapped('filename'))
        nuevos = 0
        for filename in sorted(os.listdir(txt_dir)):
            if not filename.endswith('.txt') or filename in archivos_existentes:
                continue
            filepath = os.path.join(txt_dir, filename)
            fecha = datetime.fromtimestamp(os.path.getmtime(filepath))
            self.create({
                'filename': filename,
                'filepath': filepath,
                'fecha_archivo': fecha,
                'state': 'pending',
            })
            nuevos += 1
            _logger.info('TODD: Nuevo archivo detectado: %s', filename)

        _logger.info('TODD: Escaneo completado - %s archivos nuevos', nuevos)
        return nuevos

    def action_escanear_y_procesar(self):
        self.action_escanear_archivos()
        pendiente = self.search(
            [('state', 'in', ('pending', 'processing'))],
            order='fecha_archivo asc',
            limit=1,
        )
        if pendiente:
            pendiente.action_procesar()

    @api.model
    def _procesar_pendientes(self):
        self.action_escanear_archivos()
        pendiente = self.search(
            [('state', 'in', ('pending', 'processing'))],
            order='fecha_archivo asc',
            limit=1,
        )
        if pendiente:
            pendiente.action_procesar()

    @api.model
    def _parse_linea_txt(self, linea, line_num):
        c = [x.strip() for x in linea.split(';')]
        if len(c) < 17:
            return None
        return {
            'nro_socio': c[0],
            'nro_usuario': c[1],
            'periodo': c[2],
            'pto_venta': int(c[3]),
            'nro_fac': int(c[4]),
            'fecha_fac': datetime.strptime(c[5], '%d/%m/%Y').date(),
            'fecha_vto': datetime.strptime(c[6], '%d/%m/%Y').date(),
            'importe': float(c[7].replace(',', '.')),
            'archivo_pdf': c[8],
            'cod_pago_electronico': c[9].strip(),
            'cod_pago_electronico_otros': c[10].strip(),
            'estado_comp': c[11].strip(),
            'domicilio': c[12],
            'nombre': c[13],
            'servicio': c[14],
            'importe_2do_venc': float(c[15].replace(',', '.')) if c[15].strip() else 0,
            'dni': c[17].strip() if len(c) > 17 else '',
            'line_num': line_num,
        }

    @api.model
    def _get_or_create_partner_todd(self, lp):
        partner = self.env['res.partner'].search(
            [('todd_nro_socio', '=', lp['nro_socio'])], limit=1
        )
        created = False
        if not partner:
            dni = lp['dni']
            partner = self.env['res.partner'].create({
                'name': lp['nombre'],
                'todd_nro_socio': lp['nro_socio'],
                'todd_nro_usuario': lp['nro_usuario'],
                'street': lp['domicilio'],
                'vat': dni if dni and dni != '0' else False,
            })
            created = True
        partner.crear_usuario_portal_si_no_tiene()
        return partner, created

    @api.model
    def _crear_o_actualizar_factura(self, lp, source_dir):
        existe = self.env['todd.factura'].search([
            ('partner_id', '=', lp['partner_id']),
            ('archivo_pdf', '=', lp['archivo_pdf']),
        ], limit=1)
        if existe:
            if 'Pagado' in lp['estado_comp'] and existe.estado_pago != 'pagado':
                existe.estado_pago = 'pagado'
                return 'updated', None
            return 'skipped', None

        src = os.path.join(source_dir, lp['archivo_pdf']) if lp['archivo_pdf'] else ''
        pdf_ok = bool(src and os.path.exists(src))
        warning = None if pdf_ok else f"PDF no encontrado: {lp['archivo_pdf']}"

        self.env['todd.factura'].create({
            'partner_id': lp['partner_id'],
            'referencia': lp['nro_socio'],
            'nro_usuario': lp['nro_usuario'],
            'periodo': lp['periodo'],
            'punto_venta': lp['pto_venta'],
            'nro_factura': lp['nro_fac'],
            'fecha_emision': lp['fecha_fac'],
            'fecha_vencimiento': lp['fecha_vto'],
            'importe': lp['importe'],
            'archivo_pdf': lp['archivo_pdf'],
            'cod_pago_electronico': lp['cod_pago_electronico'],
            'cod_pago_electronico_otros': lp['cod_pago_electronico_otros'],
            'estado_pago': 'pagado' if 'Pagado' in lp['estado_comp'] else 'adeudado',
            'domicilio': lp['domicilio'],
            'servicio': lp['servicio'],
            'importe_2do_vencimiento': lp['importe_2do_venc'],
            'dni': lp['dni'],
            'archivo_pdf_ruta': src if pdf_ok else '',
        })
        return 'created', warning

    def _append_log(self, lines):
        prev = self.log or ''
        extra = '\n'.join(lines)
        combined = '\n'.join(x for x in (prev, extra) if x)
        if len(combined) > 80000:
            combined = combined[-80000:]
        return combined

    def action_procesar(self):
        self.ensure_one()
        if self.state not in ('pending', 'processing', 'error'):
            return

        _logger.info('TODD: Iniciando carga de %s (state=%s, offset=%s)',
                     self.filename, self.state, self.lineas_procesadas)
        if self.state != 'processing':
            self.write({
                'state': 'processing',
                'fecha_importacion': fields.Datetime.now(),
            })
            self.env.cr.commit()

        try:
            with open(self.filepath, 'r', encoding='latin-1') as f:
                lineas = f.readlines()
        except Exception as e:
            msg = f'Error leyendo archivo: {e}'
            _logger.exception('TODD: %s', msg)
            self.write({'state': 'error', 'log': self._append_log([msg])})
            return

        if len(lineas) < 2:
            msg = 'Archivo vacío o sin líneas de datos'
            self.write({'state': 'error', 'log': self._append_log([msg])})
            return

        total = len(lineas) - 1
        source_dir = self._get_pdf_dir()
        import_id = self.id

        try:
            while True:
                self = self.env['todd.txt.import'].browse(import_id)
                offset = self.lineas_procesadas or 0
                start = offset + 1
                end = min(start + BATCH_SIZE, len(lineas))
                if start >= len(lineas):
                    self.write({
                        'state': 'done',
                        'total_lineas': total,
                        'log': self._append_log([
                            f'Finalizado {self.filename}: {self.facturas_creadas} creadas, '
                            f'{self.facturas_actualizadas} actualizadas, {self.errores} errores, '
                            f'{self.lineas_omitidas} omitidas'
                        ]),
                    })
                    break

                log = [f'--- Lote líneas {start}-{end - 1} de {total} ---']
                creadas = actualizadas = partners_nuevos = omitidas = errores = 0
                partners_map = {}
                lineas_parseadas = []

                for i in range(start, end):
                    try:
                        parsed = self._parse_linea_txt(lineas[i], i + 1)
                        if not parsed:
                            omitidas += 1
                            cols = len([x for x in lineas[i].split(';')])
                            log.append(f'Línea {i + 1}: omitida (columnas insuficientes: {cols})')
                            continue
                        if parsed['nro_socio'] not in partners_map:
                            try:
                                with self.env.cr.savepoint():
                                    partner, created = self._get_or_create_partner_todd(parsed)
                                    partners_map[parsed['nro_socio']] = partner.id
                                    if created:
                                        partners_nuevos += 1
                            except Exception as e:
                                errores += 1
                                log.append(f"Línea {i + 1}: ERROR partner {parsed['nro_socio']} - {e}")
                                _logger.exception('TODD: partner línea %s de %s', i + 1, self.filename)
                                continue
                        parsed['partner_id'] = partners_map[parsed['nro_socio']]
                        lineas_parseadas.append(parsed)
                    except Exception as e:
                        errores += 1
                        log.append(f'Línea {i + 1}: ERROR parseo - {e}')
                        _logger.exception('TODD: parseo línea %s de %s', i + 1, self.filename)

                for lp in lineas_parseadas:
                    try:
                        with self.env.cr.savepoint():
                            status, warning = self._crear_o_actualizar_factura(lp, source_dir)
                        if status == 'created':
                            creadas += 1
                        elif status == 'updated':
                            actualizadas += 1
                        if warning:
                            log.append(f"Línea {lp['line_num']}: {warning}")
                    except Exception as e:
                        errores += 1
                        log.append(f"Línea {lp['line_num']}: ERROR factura - {e}")
                        _logger.exception('TODD: factura línea %s de %s', lp['line_num'], self.filename)

                vals = {
                    'total_lineas': total,
                    'lineas_procesadas': end - 1,
                    'lineas_omitidas': (self.lineas_omitidas or 0) + omitidas,
                    'facturas_creadas': (self.facturas_creadas or 0) + creadas,
                    'facturas_actualizadas': (self.facturas_actualizadas or 0) + actualizadas,
                    'partners_creados': (self.partners_creados or 0) + partners_nuevos,
                    'errores': (self.errores or 0) + errores,
                }
                if end >= len(lineas):
                    vals['state'] = 'done'
                    log.append(
                        f'Finalizado {self.filename}: {vals["facturas_creadas"]} creadas, '
                        f'{vals["facturas_actualizadas"]} actualizadas, {vals["errores"]} errores, '
                        f'{vals["lineas_omitidas"]} omitidas'
                    )
                    _logger.info(
                        'TODD: Finalizado %s - Creadas: %s, Actualizadas: %s, Errores: %s, Omitidas: %s',
                        self.filename, vals['facturas_creadas'], vals['facturas_actualizadas'],
                        vals['errores'], vals['lineas_omitidas'],
                    )
                else:
                    _logger.info(
                        'TODD: %s lote %s-%s/%s (creadas +%s, errores +%s)',
                        self.filename, start, end - 1, total, creadas, errores,
                    )
                vals['log'] = self._append_log(log)
                self.write(vals)
                self.env.cr.commit()
                self.env.clear()
                if end >= len(lineas):
                    break
        except Exception as e:
            _logger.exception('TODD: falla inesperada procesando %s', self.filename)
            self = self.env['todd.txt.import'].browse(import_id)
            self.write({
                'state': 'error',
                'log': self._append_log([f'ERROR inesperado: {e}']),
            })
