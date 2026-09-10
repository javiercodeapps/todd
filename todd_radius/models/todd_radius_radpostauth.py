import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadpostauth(models.Model):
    _name = 'todd.radius.radpostauth'
    _auto = False
    _description = 'Autenticaciones RADIUS (radpostauth) - Solo lectura'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    password = fields.Char(string='Contraseña')
    reply = fields.Char(string='Respuesta')
    authdate = fields.Datetime(string='Fecha Auth')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_radpostauth CASCADE;
            CREATE TABLE todd_radius_radpostauth (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(64),
                password VARCHAR(128),
                reply VARCHAR(255),
                authdate TIMESTAMP
            );
            CREATE INDEX idx_todd_radius_radpostauth_username ON todd_radius_radpostauth(username);
        """)

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_radpostauth")
        rows = self.env['todd.radius.db']._execute(
            "SELECT * FROM radpostauth ORDER BY authdate DESC LIMIT 10000"
        )
        if not rows:
            return
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radpostauth (radius_id, username, password, reply, authdate)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                row.get('id'), row.get('username'), row.get('password'),
                row.get('reply'), row.get('authdate'),
            ))
        _logger.info('TODD RADIUS: Sincronizadas %d autenticaciones', len(rows))

    def name_get(self):
        result = []
        for rec in self:
            date = rec.authdate.strftime('%Y-%m-%d %H:%M') if rec.authdate else '?'
            result.append((rec.id, f"{rec.username} - {rec.reply} ({date})"))
        return result
