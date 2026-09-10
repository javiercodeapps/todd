from odoo import api, fields, models


class ToddRadiusRadusergroup(models.Model):
    _name = 'todd.radius.radusergroup'
    _auto = False
    _description = 'Grupos de usuario RADIUS'

    username = fields.Char(string='Usuario', index=True, required=True)
    groupname = fields.Char(string='Grupo', required=True)
    priority = fields.Integer(string='Prioridad', default=0)

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radusergroup CASCADE")
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.foreign_tables
                WHERE foreign_table_name = 'radusergroup'
            )
        """)
        fdw_ready = self.env.cr.fetchone()[0]
        if fdw_ready:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radusergroup AS
                SELECT id, username, groupname, priority
                FROM radusergroup
            """)
        else:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radusergroup AS
                SELECT 1 AS id, NULL::varchar AS username, NULL::varchar AS groupname, 0 AS priority
                WHERE FALSE
            """)

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
