import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadusergroup(models.Model):
    _name = 'todd.radius.radusergroup'
    _auto = False
    _description = 'Grupos de usuario RADIUS'

    username = fields.Char(string='Usuario', index=True, required=True)
    groupname = fields.Char(string='Grupo', required=True)
    priority = fields.Integer(string='Prioridad', default=0)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radusergroup CASCADE")
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radusergroup CASCADE")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radusergroup AS
            SELECT 1 AS id, NULL::varchar AS username, NULL::varchar AS groupname,
                   NULL::integer AS priority
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT id FROM radusergroup WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'username' and leaf[1] == '=':
                query += " AND username = %s"
                params.append(leaf[2])
            elif leaf[0] == 'groupname' and leaf[1] == '=':
                query += " AND groupname = %s"
                params.append(leaf[2])
        rows = Db._execute(query, tuple(params) if params else None)
        return self.browse([r['id'] for r in rows])

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(f"SELECT * FROM radusergroup WHERE id IN ({placeholders})", tuple(self.ids))
        rows_by_id = {r['id']: r for r in rows}
        return [{'id': rec.id, **rows_by_id.get(rec.id, {})} for rec in self]

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, %s)",
                (vals.get('username'), vals.get('groupname'), vals.get('priority', 0)),
            )
        if vals_list:
            rows = Db._execute(
                "SELECT id FROM radusergroup WHERE username = %s ORDER BY id DESC LIMIT %s",
                (vals_list[0]['username'], len(vals_list)),
            )
            return self.browse([r['id'] for r in rows])
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
