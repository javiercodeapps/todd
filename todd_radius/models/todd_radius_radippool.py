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
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_radippool CASCADE;
            CREATE TABLE todd_radius_radippool (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                pool_name VARCHAR(128),
                framedipaddress VARCHAR(64),
                nasipaddress VARCHAR(64),
                calledstationid VARCHAR(128),
                callingstationid VARCHAR(128),
                expiry_time TIMESTAMP,
                username VARCHAR(64),
                pool_key VARCHAR(128)
            );
            CREATE INDEX idx_todd_radius_radippool_pool_name ON todd_radius_radippool(pool_name);
            CREATE INDEX idx_todd_radius_radippool_username ON todd_radius_radippool(username);
        """)

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_radippool")
        rows = self.env['todd.radius.db']._execute("SELECT * FROM radippool")
        if not rows:
            return
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radippool
                    (radius_id, pool_name, framedipaddress, nasipaddress, calledstationid,
                     callingstationid, expiry_time, username, pool_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row.get('id'), row.get('pool_name'), row.get('framedipaddress'),
                row.get('nasipaddress'), row.get('calledstationid'),
                row.get('callingstationid'), row.get('expiry_time'),
                row.get('username'), row.get('pool_key'),
            ))
        _logger.info('TODD RADIUS: Sincronizadas %d IPs del pool', len(rows))

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.pool_name}: {rec.framedipaddress}"))
        return result
