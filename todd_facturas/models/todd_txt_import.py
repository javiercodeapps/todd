import os
import shutil
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
        txt_dir = self._get_txt_dir()
        _logger.warning(f'TODD: Escaneando directorio {txt_dir}')
        if not os.path.exists(txt_dir):
            _logger.warning(f'TODD: Directorio TXT no existe: {txt_dir}')
            return 0

        archivos_existentes = self.search([('filename', 'in', os.listdir(txt_dir))]).mapped('filename')
        nuevos = 0
        for filename in sorted(os.listdir(txt_dir)):
            if not filename.endswith('.txt') or filename in archivos_existentes:
                continue
            filepath = os.path.join(txt_dir, filename)
            fecha = datetime.fromtimestamp(os.path.getmtime(filepath))
            self.create({'filename': filename, 'filepath': filepath, 'fecha_archivo': fecha, 'state': 'pending'})
            nuevos += 1
            _logger.warning(f'TODD: Nuevo archivo detectado: {filename}')

        _logger.warning(f'TODD: Escaneo completado - {nuevos} archivos nuevos')
        return nuevos

    def action_escanear_y_procesar(self):
        self.action_escanear_archivos()
        pendiente = self.search([('state', '=', 'pending')], order='fecha_archivo asc', limit=1)
        if pendiente:
            pendiente.action_procesar()

    @api.model
    def _procesar_pendientes(self):
        self.action_escanear_archivos()
        pendientes = self.search([('state', '=', 'pending')], order='fecha_archivo asc', limit=1)
        if pendientes:
            pendientes.action_procesar()

    def action_procesar(self):
        self.ensure_one()
        if self.state not in ('pending',):
            return

        _logger.warning(f'TODD: Iniciando carga SQL de {self.filename}')
        self.write({'state': 'processing', 'fecha_importacion': fields.Datetime.now()})

        try:
            with open(self.filepath, 'r', encoding='latin-1') as f:
                lineas = f.readlines()
        except Exception as e:
            self.write({'state': 'error', 'log': f'Error leyendo: {e}'})
            return

        if len(lineas) < 2:
            self.write({'state': 'error', 'log': 'Archivo vacío'})
            return

        total = len(lineas) - 1
        offset = self.lineas_procesadas or 0
        _logger.warning(f'TODD: {self.filename} - Total: {total}, desde línea {offset + 1}')

        config = self.env['ir.config_parameter'].sudo()
        source_dir = config.get_param('todd.pdf_source_dir', '/var/logs/data/facturas')
        portal_dir = config.get_param('todd.pdf_portal_dir', '/var/logs/data/facturas_web')
        if not os.path.exists(portal_dir):
            try: os.makedirs(portal_dir)
            except: pass

        journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        if not journal:
            self.write({'state': 'error', 'log': 'No hay diario de ventas'})
            return

        log = []
        creadas = self.facturas_creadas or 0
        actualizadas = self.facturas_actualizadas or 0
        partners_nuevos = self.partners_creados or 0
        usuarios_nuevos = self.usuarios_creados or 0
        errores = self.errores or 0

        fin = min(offset + BATCH_SIZE, total)
        batch_partners = {}
        batch_users = {}
        batch_moves = []

        for i in range(offset + 1, fin):
            linea = lineas[i]
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
                estado_comp = c[11].strip()
                domicilio = c[12]
                nombre = c[13]
                servicio = c[14]
                dni = c[17].strip() if len(c) > 17 else ''

                # Verificar si ya existe
                existe = self.env.cr.execute(
                    "SELECT id FROM account_move WHERE partner_id IN (SELECT id FROM res_partner WHERE todd_nro_socio=%s) AND todd_archivo_pdf=%s LIMIT 1",
                    (nro_socio, archivo_pdf)
                )
                if self.env.cr.fetchone():
                    if 'Pagado' in estado_comp:
                        self.env.cr.execute(
                            "UPDATE account_move SET todd_estado_pago='pagado' WHERE partner_id IN (SELECT id FROM res_partner WHERE todd_nro_socio=%s) AND todd_archivo_pdf=%s AND todd_estado_pago != 'pagado'",
                            (nro_socio, archivo_pdf)
                        )
                        actualizadas += 1
                    continue

                # Partners
                if nro_socio not in batch_partners:
                    self.env.cr.execute("SELECT id FROM res_partner WHERE todd_nro_socio=%s", (nro_socio,))
                    row = self.env.cr.fetchone()
                    if row:
                        batch_partners[nro_socio] = row[0]
                    else:
                        vat = dni if dni and dni != '0' else False
                        self.env.cr.execute(
                            "INSERT INTO res_partner (name, todd_nro_socio, todd_nro_usuario, street, vat, is_company, customer_rank) VALUES (%s,%s,%s,%s,%s,false,1) RETURNING id",
                            (nombre, nro_socio, nro_usuario, domicilio, vat)
                        )
                        batch_partners[nro_socio] = self.env.cr.fetchone()[0]
                        partners_nuevos += 1

                partner_id = batch_partners[nro_socio]

                # Usuarios portal
                if nro_socio not in batch_users:
                    login = dni if dni and dni != '0' else nro_socio
                    self.env.cr.execute("SELECT id FROM res_users WHERE login=%s", (login,))
                    if not self.env.cr.fetchone():
                        self.env.cr.execute(
                            "INSERT INTO res_users (name, login, password, partner_id, share) VALUES (%s,%s,%s,%s,true) RETURNING id",
                            (nombre, login, login, partner_id)
                        )
                        uid = self.env.cr.fetchone()[0]
                        portal_gid = self.env.ref('base.group_portal').id
                        self.env.cr.execute(
                            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (portal_gid, uid)
                        )
                        batch_users[nro_socio] = True
                        usuarios_nuevos += 1

                # Factura
                numero = f'{pto_venta:04d}-{nro_fac:08d}'
                servicio_nombre = {'E': 'Energía', 'A': 'Agua', 'T': 'Telefonía', 'I': 'Internet', 'S': 'Sepelio', 'N': 'Nichos'}.get(servicio, servicio)
                estado_pago = 'pagado' if 'Pagado' in estado_comp else 'adeudado'

                self.env.cr.execute(
                    """INSERT INTO account_move (move_type, partner_id, invoice_date, invoice_date_due, journal_id,
                       todd_archivo_pdf, todd_nro_socio, todd_servicio, todd_periodo, ref, name,
                       todd_estado_pago, state, company_id, currency_id, payment_state, invoice_origin)
                       VALUES ('out_invoice',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'posted',1,1,'not_paid','')
                       RETURNING id""",
                    (partner_id, fecha_fac, fecha_vto, journal.id, archivo_pdf, nro_socio,
                     servicio, periodo, numero, numero, estado_pago)
                )
                move_id = self.env.cr.fetchone()[0]

                # Línea de factura
                account = self.env['account.account'].search([('account_type', '=', 'income')], limit=1)
                if account:
                    self.env.cr.execute(
                        """INSERT INTO account_move_line (move_id, name, quantity, price_unit, account_id, debit, credit, date, company_id, currency_id)
                           VALUES (%s,%s,1,%s,%s,%s,%s,CURRENT_DATE,1,1)""",
                        (move_id, f'{servicio_nombre} - {periodo}', importe, account.id, importe, 0)
                    )

                # Copiar PDF
                if os.path.exists(source_dir) and os.path.exists(portal_dir):
                    src = os.path.join(source_dir, archivo_pdf)
                    if os.path.exists(src):
                        try: shutil.copy2(src, portal_dir)
                        except: pass

                creadas += 1
            except Exception as e:
                errores += 1
                log.append(f'Línea {i + 1}: ERROR - {e}')
                _logger.error(f'TODD: Error línea {i + 1}: {e}')
                self.env.cr.rollback()

        _logger.warning(f'TODD: {self.filename} - Batch {offset + 1}-{fin}/{total} ({creadas} creadas, {actualizadas} actualizadas)')

        self.env.cr.commit()

        self.write({
            'total_lineas': total,
            'lineas_procesadas': fin,
            'facturas_creadas': creadas,
            'facturas_actualizadas': actualizadas,
            'partners_creados': partners_nuevos,
            'usuarios_creados': usuarios_nuevos,
            'errores': errores,
            'log': '\n'.join(log[-50:])
        })

        if fin >= total:
            self.write({'state': 'done'})
            _logger.warning(f'TODD: Finalizado {self.filename} - Creadas: {creadas}, Partners: {partners_nuevos}, Usuarios: {usuarios_nuevos}, Errores: {errores}')
        else:
            _logger.warning(f'TODD: {self.filename} pendiente - quedan {total - fin} líneas')
