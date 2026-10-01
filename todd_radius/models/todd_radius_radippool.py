import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusRadippool(models.Model):
    _name = 'todd.radius.radippool'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Pool de IPs RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    pool_name = fields.Char(string='Pool', index=True)
    framedipaddress = fields.Char(string='IP')
    nasipaddress = fields.Char(string='IP NAS')
    calledstationid = fields.Char(string='Llamado')
    callingstationid = fields.Char(string='Llamante')
    expiry_time = fields.Datetime(string='Expira')
    username = fields.Char(string='Usuario', index=True)
    pool_key = fields.Char(string='Clave Pool')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radippool CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radippool (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                pool_name VARCHAR(255),
                framedipaddress VARCHAR(255),
                nasipaddress VARCHAR(255),
                calledstationid VARCHAR(255),
                callingstationid VARCHAR(255),
                expiry_time TIMESTAMP,
                username VARCHAR(255),
                pool_key VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() radippool - iniciando sync')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radippool")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radippool from MySQL: %s', e)
            raise UserError(f'No se pudieron cargar datos de radippool desde MySQL: {e}')

        self.env.cr.execute("DELETE FROM todd_radius_radippool")
        if rows:
            cols = [
                'pool_name', 'framedipaddress', 'nasipaddress',
                'calledstationid', 'callingstationid', 'expiry_time', 'username', 'pool_key',
            ]
            col_names = ', '.join(['id'] + cols)
            placeholders = ', '.join(['%s'] * (len(cols) + 1))
            values = [
                tuple([r.get('id')] + [r.get(c) for c in cols])
                for r in rows
            ]
            self.env.cr.executemany(
                f"INSERT INTO todd_radius_radippool ({col_names}) VALUES ({placeholders})",
                values,
            )
            _logger.warning('TODD RADIUS: radippool sync OK - %s registros', len(rows))
        else:
            _logger.warning('TODD RADIUS: radippool sync OK - 0 registros en MySQL')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() radippool - args=%s', args)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() radippool - resultado: %s', len(result) if not count else result)
        return result

    def name_get(self):
        return [(rec.id, f"{rec.pool_name}: {rec.framedipaddress}") for rec in self]
