import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusRadcheck(models.Model):
    _name = 'todd.radius.radcheck'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Atributos check RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    attribute = fields.Char(string='Atributo')
    op = fields.Char(string='Operador')
    value = fields.Char(string='Valor')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radcheck CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radcheck (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(255),
                attribute VARCHAR(255),
                op VARCHAR(255),
                value VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() radcheck - iniciando sync')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radcheck")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radcheck from MySQL: %s', e)
            raise UserError(f'No se pudieron cargar datos de radcheck desde MySQL: {e}')

        self.env.cr.execute("DELETE FROM todd_radius_radcheck")
        if rows:
            values = [
                (r.get('id'), r.get('id'), r.get('username'), r.get('attribute'), r.get('op'), r.get('value'))
                for r in rows
            ]
            self.env.cr.executemany(
                "INSERT INTO todd_radius_radcheck (id, radius_id, username, attribute, op, value) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                values,
            )
            _logger.warning('TODD RADIUS: radcheck sync OK - %s registros', len(rows))
        else:
            _logger.warning('TODD RADIUS: radcheck sync OK - 0 registros en MySQL')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() radcheck - args=%s', args)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() radcheck - resultado: %s', len(result) if not count else result)
        return result

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (vals.get('username'), vals.get('attribute'), vals.get('op'), vals.get('value')),
            )
        if vals_list:
            rows = Db._execute(
                "SELECT id FROM radcheck WHERE username = %s ORDER BY id DESC LIMIT %s",
                (vals_list[0]['username'], len(vals_list)),
            )
            return self.browse([r['id'] for r in rows])
        return self.browse()

    def unlink(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            if rec.radius_id:
                Db._execute_write("DELETE FROM radcheck WHERE id = %s", (rec.radius_id,))
        return True

    def name_get(self):
        return [(rec.id, f"{rec.username}: {rec.attribute} = {rec.value}") for rec in self]
