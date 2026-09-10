from odoo import api, fields, models


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
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radippool AS
            SELECT id AS radius_id, id, pool_name, framedipaddress, nasipaddress,
                   calledstationid, callingstationid, expiry_time, username, pool_key
            FROM radippool
        """)

    def name_get(self):
        return [(rec.id, f"{rec.pool_name}: {rec.framedipaddress}") for rec in self]
