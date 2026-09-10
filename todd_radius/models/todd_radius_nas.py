import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusNas(models.Model):
    _name = 'todd.radius.nas'
    _auto = False
    _description = 'Dispositivos NAS (nas)'

    radius_id = fields.Integer(string='ID RADIUS', readonly=True)
    nasname = fields.Char(string='Nombre NAS', index=True)
    shortname = fields.Char(string='Nombre Corto')
    type = fields.Char(string='Tipo')
    ports = fields.Integer(string='Puertos')
    secret = fields.Char(string='Secreto')
    server = fields.Char(string='Servidor')
    community = fields.Char(string='Comunidad')
    description = fields.Char(string='Descripción')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_nas CASCADE;
            CREATE TABLE todd_radius_nas (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                nasname VARCHAR(128),
                shortname VARCHAR(32),
                type VARCHAR(32),
                ports INTEGER,
                secret VARCHAR(64),
                server VARCHAR(64),
                community VARCHAR(32),
                description VARCHAR(255)
            );
            CREATE INDEX idx_todd_radius_nas_nasname ON todd_radius_nas(nasname);
        """)

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_nas")
        rows = self.env['todd.radius.db']._execute("SELECT * FROM nas")
        if not rows:
            return
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_nas (radius_id, nasname, shortname, type, ports, secret, server, community, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row.get('id'), row.get('nasname'), row.get('shortname'), row.get('type'),
                row.get('ports'), row.get('secret'), row.get('server'),
                row.get('community'), row.get('description'),
            ))
        _logger.info('TODD RADIUS: Sincronizados %d dispositivos NAS', len(rows))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.env['todd.radius.db']._execute_write(
                "INSERT INTO nas (nasname, shortname, type, ports, secret, server, community, description) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    vals.get('nasname'), vals.get('shortname'), vals.get('type'),
                    vals.get('ports'), vals.get('secret'), vals.get('server'),
                    vals.get('community'), vals.get('description'),
                )
            )
        self.sync_from_radius()
        record = self.search([('nasname', '=', vals_list[0].get('nasname'))], limit=1) if vals_list else self.browse()
        return record

    def write(self, vals):
        for rec in self:
            sets = []
            params = []
            for field in ('nasname', 'shortname', 'type', 'ports', 'secret', 'server', 'community', 'description'):
                if field in vals:
                    sets.append(f"{field} = %s")
                    params.append(vals[field])
            if sets:
                params.append(rec.radius_id)
                self.env['todd.radius.db']._execute_write(
                    f"UPDATE nas SET {', '.join(sets)} WHERE id = %s", tuple(params)
                )
        self.sync_from_radius()
        return True

    def name_get(self):
        result = []
        for rec in self:
            label = rec.shortname or rec.nasname or ''
            if rec.nasname and rec.shortname:
                label = f"{rec.shortname} ({rec.nasname})"
            result.append((rec.id, label))
        return result
