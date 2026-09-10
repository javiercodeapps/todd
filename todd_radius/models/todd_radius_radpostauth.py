from odoo import api, fields, models


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
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radpostauth CASCADE")
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.foreign_tables
                WHERE foreign_table_name = 'radpostauth'
            )
        """)
        fdw_ready = self.env.cr.fetchone()[0]
        if fdw_ready:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radpostauth AS
                SELECT id AS radius_id, id, username, password, reply, authdate
                FROM radpostauth
            """)
        else:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radpostauth AS
                SELECT 1 AS radius_id, 1 AS id, NULL::varchar AS username,
                       NULL::varchar AS password, NULL::varchar AS reply,
                       NULL::timestamp AS authdate
                WHERE FALSE
            """)

    def name_get(self):
        result = []
        for rec in self:
            date = rec.authdate.strftime('%d/%m %H:%M') if rec.authdate else '?'
            result.append((rec.id, f"{rec.username} - {rec.reply} ({date})"))
        return result
