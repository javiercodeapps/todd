import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadreply(models.Model):
    _name = 'todd.radius.radreply'
    _auto = False
    _inherit = ['todd.radius.db']
    _description = 'Atributos reply RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    attribute = fields.Char(string='Atributo')
    op = fields.Char(string='Operador')
    value = fields.Char(string='Valor')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radreply CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_radreply (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(255),
                attribute VARCHAR(255),
                op VARCHAR(255),
                value VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM radreply")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing radreply from MySQL: %s', e)
            return

        self.env.cr.execute("DELETE FROM todd_radius_radreply")
        if rows:
            values = [
                (r.get('id'), r.get('id'), r.get('username'), r.get('attribute'), r.get('op'), r.get('value'))
                for r in rows
            ]
            self.env.cr.executemany(
                "INSERT INTO todd_radius_radreply (id, radius_id, username, attribute, op, value) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                values,
            )

    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._sync_from_mysql()
        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (vals.get('username'), vals.get('attribute'), vals.get('op'), vals.get('value')),
            )
        if vals_list:
            rows = Db._execute(
                "SELECT id FROM radreply WHERE username = %s ORDER BY id DESC LIMIT %s",
                (vals_list[0]['username'], len(vals_list)),
            )
            return self.browse([r['id'] for r in rows])
        return self.browse()

    def unlink(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            if rec.radius_id:
                Db._execute_write("DELETE FROM radreply WHERE id = %s", (rec.radius_id,))
        return True

    def name_get(self):
        return [(rec.id, f"{rec.username}: {rec.attribute} = {rec.value}") for rec in self]
