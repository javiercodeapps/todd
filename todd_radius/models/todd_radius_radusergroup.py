import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusRadusergroup(models.Model):
    _name = 'todd.radius.radusergroup'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Grupos de usuario RADIUS'

    username = fields.Char(string='Usuario', index=True, required=True)
    groupname = fields.Char(string='Grupo', required=True)
    priority = fields.Integer(string='Prioridad', default=0)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radusergroup CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radusergroup (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255),
                groupname VARCHAR(255),
                priority INTEGER DEFAULT 0
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() radusergroup - iniciando sync')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radusergroup")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radusergroup from MySQL: %s', e)
            raise UserError(f'No se pudieron cargar datos de radusergroup desde MySQL: {e}')

        self.env.cr.execute("DELETE FROM todd_radius_radusergroup")
        if rows:
            values = [
                (r.get('username'), r.get('groupname'), r.get('priority', 0))
                for r in rows
            ]
            self.env.cr.executemany(
                "INSERT INTO todd_radius_radusergroup (username, groupname, priority) "
                "VALUES (%s, %s, %s)",
                values,
            )
            _logger.warning('TODD RADIUS: radusergroup sync OK - %s registros', len(rows))
        else:
            _logger.warning('TODD RADIUS: radusergroup sync OK - 0 registros en MySQL')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() radusergroup - args=%s', args)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() radusergroup - resultado: %s', len(result) if not count else result)
        return result

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, %s)",
                (vals.get('username'), vals.get('groupname'), vals.get('priority', 0)),
            )
        return self.browse()

    def unlink(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            Db._execute_write(
                "DELETE FROM radusergroup WHERE username = %s AND groupname = %s AND priority = %s",
                (rec.username, rec.groupname, rec.priority),
            )
        return True

    def name_get(self):
        return [(rec.id, f"{rec.username} → {rec.groupname} ({rec.priority})") for rec in self]
