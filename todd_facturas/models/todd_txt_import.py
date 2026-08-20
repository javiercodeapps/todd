import os
import shutil
import logging
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    def action_escanear_archivos(self):
        """Escanear directorio de TXTs y crear registros pendientes"""
        txt_dir = self._get_txt_dir()
        _logger.info(f'TODD: Escaneando directorio {txt_dir}')
        if not os.path.exists(txt_dir):
            _logger.warning(f'TODD: Directorio TXT no existe: {txt_dir}')
            return 0

        archivos_existentes = self.search([('filename', 'in', os.listdir(txt_dir))]).mapped('filename')

        nuevos = 0
        for filename in sorted(os.listdir(txt_dir)):
            if not filename.endswith('.txt'):
                continue
            if filename in archivos_existentes:
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
            _logger.info(f'TODD: Nuevo archivo detectado: {filename}')

        _logger.info(f'TODD: Escaneo completado - {nuevos} archivos nuevos')
        return nuevos

    def action_escanear_y_procesar(self):
        """Escanear y procesar 1 archivo pendiente"""
        self.action_escanear_archivos()
        pendiente = self.search([('state', '=', 'pending')], order='create_date asc', limit=1)
        if pendiente:
            pendiente.action_procesar()

    @api.model
    def _procesar_pendientes(self):
        """Escanear y procesar archivos pendientes"""
        self.action_escanear_archivos()
        pendientes = self.search([('state', '=', 'pending')], order='create_date asc', limit=1)
        if pendientes:
            pendientes.action_procesar()

    def action_procesar(self):
        """Procesar un archivo TXT"""
        self.ensure_one()
        if self.state not in ('pending',):
            return

        _logger.info(f'TODD: Iniciando procesamiento de {self.filename}')
        self.write({'state': 'processing', 'fecha_importacion': fields.Datetime.now()})

        try:
            with open(self.filepath, 'r', encoding='latin-1') as f:
                contenido = f.read()
        except Exception as e:
            _logger.error(f'TODD: Error leyendo {self.filename}: {e}')
            self.write({'state': 'error', 'log': f'Error leyendo archivo: {e}'})
            return

        lineas = contenido.strip().split('\n')
        if len(lineas) < 2:
            self.write({'state': 'error', 'log': 'Archivo vacío o sin datos'})
            return

        _logger.info(f'TODD: {self.filename} tiene {len(lineas) - 1} líneas a procesar')

        config = self.env['ir.config_parameter'].sudo()
        source_dir = config.get_param('todd.pdf_source_dir', '/var/logs/data/facturas')
        portal_dir = config.get_param('todd.pdf_portal_dir', '/var/logs/data/facturas_web')

        if not os.path.exists(portal_dir):
            try:
                os.makedirs(portal_dir)
            except OSError:
                pass

        log = []
        total = 0
        creadas = 0
        actualizadas = 0
        partners_nuevos = 0
        usuarios_nuevos = 0
        errores = 0

        journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        if not journal:
            self.write({'state': 'error', 'log': 'No se encontró diario de ventas'})
            return

        for i, linea in enumerate(lineas[1:], 2):
            total += 1
            try:
                resultado = self._procesar_linea(linea, journal, source_dir, portal_dir)
                if resultado.get('nuevo'):
                    creadas += 1
                elif resultado.get('actualizada'):
                    actualizadas += 1
                if resultado.get('partner_nuevo'):
                    partners_nuevos += 1
                if resultado.get('usuario_creado'):
                    usuarios_nuevos += 1
                if total % 100 == 0:
                    _logger.info(f'TODD: {self.filename} - Procesadas {total} líneas ({creadas} creadas, {actualizadas} actualizadas, {errores} errores)')
            except Exception as e:
                errores += 1
                log.append(f'Línea {i}: ERROR - {e}')
                _logger.error(f'TODD: Error línea {i} en {self.filename}: {e}')

        _logger.info(f'TODD: Finalizado {self.filename} - Total: {total}, Creadas: {creadas}, Actualizadas: {actualizadas}, Partners: {partners_nuevos}, Usuarios: {usuarios_nuevos}, Errores: {errores}')

        self.write({
            'state': 'done',
            'total_lineas': total,
            'facturas_creadas': creadas,
            'facturas_actualizadas': actualizadas,
            'partners_creados': partners_nuevos,
            'usuarios_creados': usuarios_nuevos,
            'errores': errores,
            'log': '\n'.join(log)
        })

    def _procesar_linea(self, linea, journal, source_dir, portal_dir):
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

        resultado = {'nuevo': False, 'actualizada': False, 'partner_nuevo': False, 'usuario_creado': False}

        partner = self.env['res.partner'].search([('todd_nro_socio', '=', nro_socio)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': nombre, 'todd_nro_socio': nro_socio, 'todd_nro_usuario': nro_usuario,
                'street': domicilio, 'vat': dni if dni and dni != '0' else False
            })
            resultado['partner_nuevo'] = True

        portal_group = self.env.ref('base.group_portal')
        users = self.env['res.users'].search([('partner_id', '=', partner.id)])
        tiene_portal = any(portal_group.id in u.groups_id.ids for u in users)

        if not tiene_portal:
            login = partner.vat or partner.todd_nro_socio
            if login and not self.env['res.users'].search([('login', '=', login)], limit=1):
                password = login
                user = self.env['res.users'].create({
                    'name': partner.name,
                    'login': login,
                    'password': password,
                    'partner_id': partner.id,
                    'share': True,
                })
                self.env.cr.execute(
                    "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (portal_group.id, user.id)
                )
                resultado['usuario_creado'] = True

        existe = self.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('todd_archivo_pdf', '=', archivo_pdf)
        ], limit=1)

        if existe:
            if 'Pagado' in estado_comp and existe.todd_estado_pago != 'pagado':
                existe.action_registrar_pago()
                resultado['actualizada'] = True
            elif 'Adeudado' in estado_comp and existe.todd_estado_pago != 'adeudado':
                existe.todd_estado_pago = 'adeudado'
                resultado['actualizada'] = True
            return resultado

        numero_factura = f'{pto_venta:04d}-{nro_fac:08d}'
        servicio_nombre = {'E': 'Energía', 'A': 'Agua', 'T': 'Telefonía', 'I': 'Internet', 'S': 'Sepelio', 'N': 'Nichos'}.get(servicio, servicio)

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fecha_fac,
            'invoice_date_due': fecha_vto,
            'journal_id': journal.id,
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

        if os.path.exists(source_dir) and os.path.exists(portal_dir):
            src = os.path.join(source_dir, archivo_pdf)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, portal_dir)
                except Exception:
                    pass

        resultado['nuevo'] = True
        return resultado