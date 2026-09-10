from odoo import api, fields, models


class ToddRadiusRadcheck(models.Model):
    _name = 'todd.radius.radcheck'
    _auto = False
    _description = 'Atributos check RADIUS'

    radius_id = fields.Integer(string='ID', readonly=True)
    username = fields.Char(string='Usuario', index=True)
    attribute = fields.Char(string='Atributo')
    op = fields.Char(string='Operador')
    value = fields.Char(string='Valor')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radcheck CASCADE")
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.foreign_tables
                WHERE foreign_table_name = 'radcheck'
            )
        """)
        fdw_ready = self.env.cr.fetchone()[0]
        if fdw_ready:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radcheck AS
                SELECT id AS radius_id, id, username, attribute, op, value
                FROM radcheck
            """)
        else:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radcheck AS
                SELECT 1 AS radius_id, 1 AS id, NULL::varchar AS username,
                       NULL::varchar AS attribute, NULL::varchar AS op, NULL::varchar AS value
                WHERE FALSE
            """)

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
                (vals.get('username'), vals.get('attribute'), vals.get('op'), vals.get('value')),
            )
        if vals_list:
            rows = Db._execute(
                "SELECT id FROM radcheck WHERE username = %s ORDER BY id DESC LIMIT %s",
                (vals_list[0]['username'], len(vals_list)),
            )
            return self.browse([r['id'] for r in rows])
        return self.browse()

    def unlink(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            if rec.radius_id:
                Db._execute_write("DELETE FROM radcheck WHERE id = %s", (rec.radius_id,))
        return True

    def name_get(self):
        return [(rec.id, f"{rec.username}: {rec.attribute} = {rec.value}") for rec in self]
