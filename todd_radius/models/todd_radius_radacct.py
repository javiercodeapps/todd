import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusRadacct(models.Model):
    _name = 'todd.radius.radacct'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Sesiones RADIUS'

    radacctid = fields.Integer(string='ID', readonly=True)
    acctsessionid = fields.Char(string='Sesión')
    acctuniqueid = fields.Char(string='ID Único')
    username = fields.Char(string='Usuario', index=True)
    groupname = fields.Char(string='Grupo')
    realm = fields.Char(string='Realm')
    nasipaddress = fields.Char(string='IP NAS')
    nasportid = fields.Char(string='Puerto NAS')
    nasporttype = fields.Char(string='Tipo Puerto')
    acctstarttime = fields.Datetime(string='Inicio')
    acctstoptime = fields.Datetime(string='Fin')
    acctsessiontime = fields.Integer(string='Duración (s)')
    acctauthentic = fields.Char(string='Autenticación')
    connectinfo_start = fields.Char(string='Info Inicio')
    connectinfo_stop = fields.Char(string='Info Fin')
    acctinputoctets = fields.Integer(string='Bytes Entrada')
    acctoutputoctets = fields.Integer(string='Bytes Salida')
    calledstationid = fields.Char(string='Llamado')
    callingstationid = fields.Char(string='Llamante')
    acctterminatecause = fields.Char(string='Causa Fin')
    servicetype = fields.Char(string='Tipo Servicio')
    framedprotocol = fields.Char(string='Protocolo')
    framedipaddress = fields.Char(string='IP Framed')

    def init(self):
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radacct CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radacct (
                id SERIAL PRIMARY KEY,
                radacctid INTEGER,
                acctsessionid VARCHAR(255),
                acctuniqueid VARCHAR(255),
                username VARCHAR(255),
                groupname VARCHAR(255),
                realm VARCHAR(255),
                nasipaddress VARCHAR(255),
                nasportid VARCHAR(255),
                nasporttype VARCHAR(255),
                acctstarttime TIMESTAMP,
                acctstoptime TIMESTAMP,
                acctsessiontime INTEGER,
                acctauthentic VARCHAR(255),
                connectinfo_start VARCHAR(255),
                connectinfo_stop VARCHAR(255),
                acctinputoctets BIGINT,
                acctoutputoctets BIGINT,
                calledstationid VARCHAR(255),
                callingstationid VARCHAR(255),
                acctterminatecause VARCHAR(255),
                servicetype VARCHAR(255),
                framedprotocol VARCHAR(255),
                framedipaddress VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() radacct - iniciando sync')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radacct")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radacct from MySQL: %s', e)
            raise UserError(f'No se pudieron cargar datos de radacct desde MySQL: {e}')

        self.env.cr.execute("DELETE FROM todd_radius_radacct")
        if rows:
            cols = [
                'radacctid', 'acctsessionid', 'acctuniqueid', 'username', 'groupname',
                'realm', 'nasipaddress', 'nasportid', 'nasporttype',
                'acctstarttime', 'acctstoptime', 'acctsessiontime', 'acctauthentic',
                'connectinfo_start', 'connectinfo_stop', 'acctinputoctets', 'acctoutputoctets',
                'calledstationid', 'callingstationid', 'acctterminatecause', 'servicetype',
                'framedprotocol', 'framedipaddress',
            ]
            col_names = ', '.join(['id'] + cols)
            placeholders = ', '.join(['%s'] * (len(cols) + 1))
            values = [
                tuple([r.get('id')] + [r.get(c) for c in cols])
                for r in rows
            ]
            self.env.cr.executemany(
                f"INSERT INTO todd_radius_radacct ({col_names}) VALUES ({placeholders})",
                values,
            )
            _logger.warning('TODD RADIUS: radacct sync OK - %s registros', len(rows))
        else:
            _logger.warning('TODD RADIUS: radacct sync OK - 0 registros en MySQL')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() radacct - args=%s', args)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() radacct - resultado: %s', len(result) if not count else result)
        return result

    def name_get(self):
        result = []
        for rec in self:
            start = rec.acctstarttime.strftime('%d/%m %H:%M') if rec.acctstarttime else '?'
            result.append((rec.id, f"{rec.username} desde {rec.nasipaddress} el {start}"))
        return result
