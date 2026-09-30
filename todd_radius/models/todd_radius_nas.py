import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusNas(models.Model):
    _name = 'todd.radius.nas'
    _auto = False
    _inherit = ['todd.radius.db']
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
            CREATE TABLE IF NOT EXISTS todd_radius_nas (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                nasname VARCHAR(255),
                shortname VARCHAR(255),
                type VARCHAR(255),
                ports INTEGER,
                secret VARCHAR(255),
                server VARCHAR(255),
                community VARCHAR(255),
                description VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM nas")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing nas from MySQL: %s', e)
            return

        self.env.cr.execute("DELETE FROM todd_radius_nas")
        if rows:
            cols = ['nasname', 'shortname', 'type', 'ports', 'secret', 'server', 'community', 'description']
            col_names = ', '.join(['id'] + cols)
            placeholders = ', '.join(['%s'] * (len(cols) + 1))
            values = [
                tuple([r.get('id')] + [r.get(c) for c in cols])
                for r in rows
            ]
            self.env.cr.executemany(
                f"INSERT INTO todd_radius_nas ({col_names}) VALUES ({placeholders})",
                values,
            )

    def search(self, args, offset=0, limit=None, order=None, count=False):
        self._sync_from_mysql()
        return super().search(args, offset=offset, limit=limit, order=order, count=count)

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
