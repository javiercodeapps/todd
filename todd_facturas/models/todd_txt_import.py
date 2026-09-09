import os
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


class ToddTxtImport(models.Model):
    _name = 'todd.txt.import'
    _description = 'Importación TXT Todd'
    _rec_name = 'filename'
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
        pendientes = self.search(
            [('state', '=', 'pending')],
            order='fecha_archivo asc',
        )
        for rec in pendientes:
            rec.action_procesar()

    @api.model
    def _procesar_pendientes(self):
        self.action_escanear_archivos()
        pendientes = self.search(
            [('state', '=', 'pending')],
            order='fecha_archivo asc',
        )
        for rec in pendientes:
            rec.action_procesar()

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
        Partner = self.env['res.partner']
        partner = Partner.search([('todd_nro_socio', '=', lp['nro_socio'])], limit=1)
        created = False
        if not partner:
            dni = lp['dni']
            vals = {
                'name': lp['nombre'],
                'todd_nro_socio': lp['nro_socio'],
                'todd_nro_usuario': lp['nro_usuario'],
                'street': lp['domicilio'],
                'vat': dni if dni and dni != '0' else False,
            }
            try:
                with self.env.cr.savepoint():
                    partner = Partner.create(vals)
                    created = True
            except Exception:
                partner = Partner.search([('todd_nro_socio', '=', lp['nro_socio'])], limit=1)
                if not partner:
                    raise
        partner.crear_usuario_portal_si_no_tiene()
        return partner, created

    @api.model
    def _pdf_ruta(self, source_dir, archivo_pdf):
        src = os.path.join(source_dir, archivo_pdf) if archivo_pdf else ''
        return src if src and os.path.exists(src) else ''

    @api.model
    def _crear_o_actualizar_factura(self, lp, source_dir):
        numero = f"{lp['pto_venta']:04d}-{lp['nro_fac']:08d}"
        existe = self.env['todd.factura'].search([
            ('numero_completo', '=', numero),
        ], limit=1)
        nuevo_estado = 'pagado' if 'Pagado' in lp['estado_comp'] else 'adeudado'
        pdf_ruta = self._pdf_ruta(source_dir, lp['archivo_pdf'])

        if existe:
            vals = {}
            if existe.estado_pago != nuevo_estado:
                vals['estado_pago'] = nuevo_estado
            if pdf_ruta and existe.archivo_pdf_ruta != pdf_ruta:
                vals['archivo_pdf'] = lp['archivo_pdf']
                vals['archivo_pdf_ruta'] = pdf_ruta
            if vals:
                existe.write(vals)
                return 'updated'
            return 'skipped'

        limite = date.today() - relativedelta(years=1)
        if lp['fecha_fac'] and lp['fecha_fac'] < limite:
            return 'skipped'

        try:
            with self.env.cr.savepoint():
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
                    'estado_pago': nuevo_estado,
                    'domicilio': lp['domicilio'],
                    'servicio': lp['servicio'],
                    'importe_2do_vencimiento': lp['importe_2do_venc'],
                    'dni': lp['dni'],
                    'archivo_pdf_ruta': pdf_ruta,
                })
            return 'created'
        except Exception:
            existe = self.env['todd.factura'].search([
                ('numero_completo', '=', numero),
            ], limit=1)
            if not existe:
                raise
            return 'skipped'

    def _append_log(self, lines):
        prev = self.log or ''
        extra = '\n'.join(lines)
        combined = '\n'.join(x for x in (prev, extra) if x)
        if len(combined) > 80000:
            combined = combined[-80000:]
        return combined

    def _marcar_error(self, msg):
        self.write({
            'state': 'error',
            'log': self._append_log([msg]),
        })

    def _sumar_progreso(self, lineas_lote, omitidas, creadas, actualizadas, partners_nuevos, errores, log_lines, total):
        self.ensure_one()
        extra = '\n'.join(log_lines) if log_lines else ''
        self.env.cr.execute(
            """
            UPDATE todd_txt_import SET
                lineas_procesadas = COALESCE(lineas_procesadas, 0) + %s,
                lineas_omitidas = COALESCE(lineas_omitidas, 0) + %s,
                facturas_creadas = COALESCE(facturas_creadas, 0) + %s,
                facturas_actualizadas = COALESCE(facturas_actualizadas, 0) + %s,
                partners_creados = COALESCE(partners_creados, 0) + %s,
                errores = COALESCE(errores, 0) + %s,
                log = CASE
                    WHEN %s = '' THEN log
                    ELSE RIGHT(CONCAT_WS(E'\n', NULLIF(log, ''), %s), 80000)
                END,
                write_date = (now() AT TIME ZONE 'UTC')
            WHERE id = %s
            RETURNING lineas_procesadas
            """,
            (
                lineas_lote, omitidas, creadas, actualizadas, partners_nuevos, errores,
                extra, extra, self.id,
            ),
        )
        procesadas = self.env.cr.fetchone()[0]
        self.invalidate_recordset()
        if procesadas >= total:
            self.write({
                'state': 'done',
                'log': self._append_log([
                    f'Finalizado {self.filename}: {self.facturas_creadas} creadas, '
                    f'{self.facturas_actualizadas} actualizadas, {self.errores} errores, '
                    f'{self.lineas_omitidas} omitidas'
                ]),
            })
            _logger.info(
                'TODD: Finalizado %s - Creadas: %s, Actualizadas: %s, Errores: %s, Omitidas: %s',
                self.filename, self.facturas_creadas, self.facturas_actualizadas,
                self.errores, self.lineas_omitidas,
            )

    @api.model
    def _cola_disponible(self):
        if 'queue.job' not in self.env:
            return False
        self.env.cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'queue_job_function' AND column_name = 'on_fail_method'
            """
        )
        return bool(self.env.cr.fetchone())

    def _rangos_lote(self, total):
        start = 1
        file_len = total + 1
        while start < file_len:
            end = min(start + BATCH_SIZE, file_len)
            yield start, end
            start = end

    def action_procesar(self):
        self.ensure_one()
        if self.state == 'processing':
            return True
        if self.state not in ('pending', 'error'):
            return True

        try:
            with open(self.filepath, 'r', encoding='latin-1') as f:
                total = max(len(f.readlines()) - 1, 0)
        except Exception as e:
            msg = f'Error leyendo archivo: {e}'
            _logger.exception('TODD: %s', msg)
            self._marcar_error(msg)
            return True

        if total < 1:
            self._marcar_error('Archivo vacío o sin líneas de datos')
            return True

        self.write({
            'state': 'processing',
            'fecha_importacion': fields.Datetime.now(),
            'total_lineas': total,
            'lineas_procesadas': 0,
            'lineas_omitidas': 0,
            'facturas_creadas': 0,
            'facturas_actualizadas': 0,
            'partners_creados': 0,
            'errores': 0,
            'log': False,
        })

        rangos = list(self._rangos_lote(total))
        if self._cola_disponible():
            for start, end in rangos:
                self.with_delay(
                    channel='root.todd_import',
                    identity_key=f'todd.txt.import.{self.id}.{start}.{end}',
                    description=f'Todd {self.filename} líneas {start}-{end - 1}',
                )._procesar_lote(start, end, total)
            _logger.info('TODD: Encolados %s lotes para %s (%s líneas)', len(rangos), self.filename, total)
        else:
            _logger.warning('TODD: queue_job no está actualizado, proceso sincrónico de %s', self.filename)
            for start, end in rangos:
                self._procesar_lote(start, end, total)
        return True

    def _procesar_lote(self, start, end, total):
        self.ensure_one()
        _logger.info('TODD: Lote %s líneas %s-%s/%s', self.filename, start, end - 1, total)
        try:
            self._procesar_lote_body(start, end, total)
        except Exception as e:
            _logger.exception('TODD: falla lote %s-%s de %s', start, end - 1, self.filename)
            self._marcar_error(f'ERROR lote {start}-{end - 1}: {e}')
            raise

    def _procesar_lote_body(self, start, end, total):
        try:
            with open(self.filepath, 'r', encoding='latin-1') as f:
                lineas = f.readlines()
        except Exception as e:
            self._marcar_error(f'Error leyendo archivo: {e}')
            return

        end = min(end, len(lineas))
        source_dir = self._get_pdf_dir()
        log = [f'--- Lote líneas {start}-{end - 1} de {total} ---']
        creadas = actualizadas = partners_nuevos = omitidas = errores = 0
        partners_map = {}
        lineas_parseadas = []

        for i in range(start, end):
            try:
                parsed = self._parse_linea_txt(lineas[i], i + 1)
                if not parsed:
                    omitidas += 1
                    cols = len(lineas[i].split(';'))
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
                    status = self._crear_o_actualizar_factura(lp, source_dir)
                if status == 'created':
                    creadas += 1
                elif status == 'updated':
                    actualizadas += 1
            except Exception as e:
                errores += 1
                log.append(f"Línea {lp['line_num']}: ERROR factura - {e}")
                _logger.exception('TODD: factura línea %s de %s', lp['line_num'], self.filename)

        self._sumar_progreso(
            end - start, omitidas, creadas, actualizadas, partners_nuevos, errores, log, total,
        )
