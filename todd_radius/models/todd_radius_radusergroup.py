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
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_radusergroup CASCADE;
            CREATE TABLE todd_radius_radusergroup (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) NOT NULL,
                groupname VARCHAR(128) NOT NULL,
                priority INTEGER DEFAULT 0
            );
            CREATE INDEX idx_todd_radius_radusergroup_username ON todd_radius_radusergroup(username);
        """)

    def sync_for_user(self, username):
        self.env.cr.execute("DELETE FROM todd_radius_radusergroup WHERE username = %s", (username,))
        rows = self.env['todd.radius.db']._execute(
            "SELECT * FROM radusergroup WHERE username = %s", (username,)
        )
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radusergroup (username, groupname, priority)
                VALUES (%s, %s, %s)
            """, (row.get('username'), row.get('groupname'), row.get('priority', 0)))

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_radusergroup")
        rows = self.env['todd.radius.db']._execute("SELECT * FROM radusergroup")
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radusergroup (username, groupname, priority)
                VALUES (%s, %s, %s)
            """, (row.get('username'), row.get('groupname'), row.get('priority', 0)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.env['todd.radius.db']._execute_write(
                "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, %s)",
                (vals.get('username'), vals.get('groupname'), vals.get('priority', 0))
            )
        if vals_list:
            self.sync_for_user(vals_list[0].get('username'))
        return self.search([
            ('username', '=', vals_list[0].get('username')),
        ]) if vals_list else self.browse()

    def unlink(self):
        for rec in self:
            self.env['todd.radius.db']._execute_write(
                "DELETE FROM radusergroup WHERE username = %s AND groupname = %s AND priority = %s",
                (rec.username, rec.groupname, rec.priority)
            )
            self.env.cr.execute(
                "DELETE FROM todd_radius_radusergroup WHERE username = %s AND groupname = %s AND priority = %s",
                (rec.username, rec.groupname, rec.priority)
            )
        return True

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"{rec.username} → {rec.groupname} ({rec.priority})"))
        return result
