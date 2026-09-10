from odoo import api, fields, models


class ToddRadiusNas(models.Model):
    _name = 'todd.radius.nas'
    _auto = False
    _description = 'Dispositivos NAS'

    radius_id = fields.Integer(string='ID', readonly=True)
    nasname = fields.Char(string='Nombre NAS', index=True)
    shortname = fields.Char(string='Nombre Corto')
    type = fields.Char(string='Tipo')
    ports = fields.Integer(string='Puertos')
    secret = fields.Char(string='Secreto')
    server = fields.Char(string='Servidor')
    community = fields.Char(string='Comunidad')
    description = fields.Char(string='Descripción')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_nas CASCADE")
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_nas AS
            SELECT id AS radius_id, id, nasname, shortname, type, ports,
                   secret, server, community, description
            FROM nas
        """)

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            Db._execute_write(
                "INSERT INTO nas (nasname, shortname, type, ports, secret, server, community, description) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (vals.get('nasname'), vals.get('shortname'), vals.get('type'),
                 vals.get('ports'), vals.get('secret'), vals.get('server'),
                 vals.get('community'), vals.get('description')),
            )
        if vals_list:
            row = Db._execute("SELECT id FROM nas WHERE nasname = %s", (vals_list[0]['nasname'],))
            return self.browse([row[0]['id']]) if row else self.browse()
        return self.browse()

    def write(self, vals):
        Db = self.env['todd.radius.db']
        for rec in self:
            sets, params = [], []
            for field in ('nasname', 'shortname', 'type', 'ports', 'secret', 'server', 'community', 'description'):
                if field in vals:
                    sets.append(f"{field} = %s")
                    params.append(vals[field])
            if sets:
                params.append(rec.radius_id)
                Db._execute_write(f"UPDATE nas SET {', '.join(sets)} WHERE id = %s", tuple(params))
        return True

    def name_get(self):
        result = []
        for rec in self:
            label = rec.shortname or rec.nasname or ''
            if rec.nasname and rec.shortname:
                label = f"{rec.shortname} ({rec.nasname})"
            result.append((rec.id, label))
        return result
