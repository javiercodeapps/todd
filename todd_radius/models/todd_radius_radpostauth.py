import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadpostauth(models.Model):
    _name = 'todd.radius.radpostauth'
    _auto = False
    _description = 'Autenticaciones RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    password = fields.Char(string='Contraseña')
    reply = fields.Char(string='Respuesta')
    authdate = fields.Datetime(string='Fecha Auth')

    def init(self):
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radpostauth CASCADE")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radpostauth AS
            SELECT 1 AS id, NULL::varchar AS username, NULL::varchar AS password,
                   NULL::varchar AS reply, NULL::timestamp AS authdate,
                   NULL::integer AS radius_id
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT id FROM radpostauth WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'username' and leaf[1] == '=':
                query += " AND username = %s"
                params.append(leaf[2])
        if order:
            query += f" ORDER BY {order}"
        if limit:
            query += f" LIMIT {limit}"
        rows = Db._execute(query, tuple(params) if params else None)
        return self.browse([r['id'] for r in rows])

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(f"SELECT * FROM radpostauth WHERE id IN ({placeholders})", tuple(self.ids))
        rows_by_id = {r['id']: r for r in rows}
        return [{'id': rec.id, **rows_by_id.get(rec.id, {})} for rec in self]

    def name_get(self):
        result = []
        for rec in self:
            date = rec.authdate.strftime('%d/%m %H:%M') if rec.authdate else '?'
            result.append((rec.id, f"{rec.username} - {rec.reply} ({date})"))
        return result
