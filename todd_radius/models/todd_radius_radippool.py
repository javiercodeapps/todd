import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadippool(models.Model):
    _name = 'todd.radius.radippool'
    _auto = False
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
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_radippool CASCADE")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radippool AS
            SELECT 1 AS id, NULL::varchar AS pool_name, NULL::varchar AS framedipaddress,
                   NULL::varchar AS nasipaddress, NULL::varchar AS calledstationid,
                   NULL::varchar AS callingstationid, NULL::timestamp AS expiry_time,
                   NULL::varchar AS username, NULL::varchar AS pool_key,
                   NULL::integer AS radius_id
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT id FROM radippool WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'pool_name' and leaf[1] == '=':
                query += " AND pool_name = %s"
                params.append(leaf[2])
            elif leaf[0] == 'username' and leaf[1] == '=':
                query += " AND username = %s"
                params.append(leaf[2])
        rows = Db._execute(query, tuple(params) if params else None)
        return self.browse([r['id'] for r in rows])

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(f"SELECT * FROM radippool WHERE id IN ({placeholders})", tuple(self.ids))
        rows_by_id = {r['id']: r for r in rows}
        return [{'id': rec.id, **rows_by_id.get(rec.id, {})} for rec in self]

    def name_get(self):
        return [(rec.id, f"{rec.pool_name}: {rec.framedipaddress}") for rec in self]
