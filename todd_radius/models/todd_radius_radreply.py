import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadreply(models.Model):
    _name = 'todd.radius.radreply'
    _auto = False
    _description = 'Respuestas RADIUS (radreply)'

    radius_id = fields.Integer(string='ID RADIUS', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    attribute = fields.Char(string='Atributo')
    op = fields.Char(string='Operador')
    value = fields.Char(string='Valor')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_radreply CASCADE;
            CREATE TABLE todd_radius_radreply (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(64),
                attribute VARCHAR(128),
                op VARCHAR(32),
                value VARCHAR(255)
            );
            CREATE INDEX idx_todd_radius_radreply_username ON todd_radius_radreply(username);
        """)

    def sync_for_user(self, username):
        self.env.cr.execute("DELETE FROM todd_radius_radreply WHERE username = %s", (username,))
        rows = self.env['todd.radius.db']._execute(
            "SELECT * FROM radreply WHERE username = %s", (username,)
        )
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radreply (radius_id, username, attribute, op, value)
                VALUES (%s, %s, %s, %s, %s)
            """, (row.get('id'), row.get('username'), row.get('attribute'), row.get('op'), row.get('value')))

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_radreply")
        rows = self.env['todd.radius.db']._execute("SELECT * FROM radreply")
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radreply (radius_id, username, attribute, op, value)
                VALUES (%s, %s, %s, %s, %s)
            """, (row.get('id'), row.get('username'), row.get('attribute'), row.get('op'), row.get('value')))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.env['todd.radius.db']._execute_write(
                "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (vals.get('username'), vals.get('attribute'), vals.get('op'), vals.get('value'))
            )
        if vals_list:
            self.sync_for_user(vals_list[0].get('username'))
        return self.search([('username', '=', vals_list[0].get('username'))]) if vals_list else self.browse()

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.username}: {rec.attribute} = {rec.value}"))
        return result
