import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusRadpostauth(models.Model):
    _name = 'todd.radius.radpostauth'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Autenticaciones RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    password = fields.Char(string='Contraseña')
    reply = fields.Char(string='Respuesta')
    authdate = fields.Datetime(string='Fecha Auth')

    def init(self):
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radpostauth CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radpostauth (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(255),
                password VARCHAR(255),
                reply VARCHAR(255),
                authdate TIMESTAMP
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() radpostauth - iniciando sync')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radpostauth")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radpostauth from MySQL: %s', e)
            raise UserError(f'No se pudieron cargar datos de radpostauth desde MySQL: {e}')

        self.env.cr.execute("DELETE FROM todd_radius_radpostauth")
        if rows:
            values = [
                (r.get('id'), r.get('id'), r.get('username'), r.get('password'), r.get('reply'), r.get('authdate'))
                for r in rows
            ]
            self.env.cr.executemany(
                "INSERT INTO todd_radius_radpostauth (id, radius_id, username, password, reply, authdate) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                values,
            )
            _logger.warning('TODD RADIUS: radpostauth sync OK - %s registros', len(rows))
        else:
            _logger.warning('TODD RADIUS: radpostauth sync OK - 0 registros en MySQL')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() radpostauth - args=%s', args)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() radpostauth - resultado: %s', len(result) if not count else result)
        return result

    def name_get(self):
        result = []
        for rec in self:
            date = rec.authdate.strftime('%d/%m %H:%M') if rec.authdate else '?'
            result.append((rec.id, f"{rec.username} - {rec.reply} ({date})"))
        return result
