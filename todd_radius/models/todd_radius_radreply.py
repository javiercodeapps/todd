import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadreply(models.Model):
    _name = 'todd.radius.radreply'
    _auto = False
    _description = 'Atributos reply RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    attribute = fields.Char(string='Atributo')
    op = fields.Char(string='Operador')
    value = fields.Char(string='Valor')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radreply CASCADE")
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radreply CASCADE")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radreply AS
            SELECT 1 AS id, NULL::varchar AS username, NULL::varchar AS attribute,
                   NULL::varchar AS op, NULL::varchar AS value, NULL::integer AS radius_id
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT id FROM radreply WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'username' and leaf[1] == '=':
                query += " AND username = %s"
                params.append(leaf[2])
        rows = Db._execute(query, tuple(params) if params else None)
        return self.browse([r['id'] for r in rows])

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(f"SELECT * FROM radreply WHERE id IN ({placeholders})", tuple(self.ids))
        rows_by_id = {r['id']: r for r in rows}
        return [{'id': rec.id, **rows_by_id.get(rec.id, {})} for rec in self]

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
