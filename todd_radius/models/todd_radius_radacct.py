import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusRadacct(models.Model):
    _name = 'todd.radius.radacct'
    _auto = False
    _description = 'Sesiones RADIUS (radacct) - Solo lectura'

    radacctid = fields.Integer(string='ID', readonly=True)
    acctsessionid = fields.Char(string='Sesión')
    acctuniqueid = fields.Char(string='ID Único')
    username = fields.Char(string='Usuario', index=True)
    groupname = fields.Char(string='Grupo')
    realm = fields.Char(string='Realm')
    nasipaddress = fields.Char(string='IP NAS')
    nasportid = fields.Char(string='Puerto NAS')
    nasporttype = fields.Char(string='Tipo Puerto')
    acctstarttime = fields.Datetime(string='Inicio')
    acctstoptime = fields.Datetime(string='Fin')
    acctsessiontime = fields.Integer(string='Duración (s)')
    acctauthentic = fields.Char(string='Autenticación')
    connectinfo_start = fields.Char(string='Info Conexión Inicio')
    connectinfo_stop = fields.Char(string='Info Conexión Fin')
    acctinputoctets = fields.Integer(string='Bytes Entrada')
    acctoutputoctets = fields.Integer(string='Bytes Salida')
    calledstationid = fields.Char(string='Llamado')
    callingstationid = fields.Char(string='Llamante')
    acctterminatecause = fields.Char(string='Causa Fin')
    servicetype = fields.Char(string='Tipo Servicio')
    framedprotocol = fields.Char(string='Protocolo')
    framedipaddress = fields.Char(string='IP Framed')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_radacct CASCADE;
            CREATE TABLE todd_radius_radacct (
                id SERIAL PRIMARY KEY,
                radacctid INTEGER,
                acctsessionid VARCHAR(64),
                acctuniqueid VARCHAR(64),
                username VARCHAR(64),
                groupname VARCHAR(128),
                realm VARCHAR(128),
                nasipaddress VARCHAR(64),
                nasportid VARCHAR(64),
                nasporttype VARCHAR(32),
                acctstarttime TIMESTAMP,
                acctstoptime TIMESTAMP,
                acctsessiontime INTEGER,
                acctauthentic VARCHAR(32),
                connectinfo_start VARCHAR(255),
                connectinfo_stop VARCHAR(255),
                acctinputoctets BIGINT,
                acctoutputoctets BIGINT,
                calledstationid VARCHAR(128),
                callingstationid VARCHAR(128),
                acctterminatecause VARCHAR(32),
                servicetype VARCHAR(32),
                framedprotocol VARCHAR(32),
                framedipaddress VARCHAR(64)
            );
            CREATE INDEX idx_todd_radius_radacct_username ON todd_radius_radacct(username);
        """)

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_radacct")
        rows = self.env['todd.radius.db']._execute(
            "SELECT * FROM radacct ORDER BY acctstarttime DESC LIMIT 10000"
        )
        if not rows:
            return
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_radacct
                    (radacctid, acctsessionid, acctuniqueid, username, groupname, realm,
                     nasipaddress, nasportid, nasporttype, acctstarttime, acctstoptime,
                     acctsessiontime, acctauthentic, connectinfo_start, connectinfo_stop,
                     acctinputoctets, acctoutputoctets, calledstationid, callingstationid,
                     acctterminatecause, servicetype, framedprotocol, framedipaddress)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row.get('radacctid'), row.get('acctsessionid'), row.get('acctuniqueid'),
                row.get('username'), row.get('groupname'), row.get('realm'),
                row.get('nasipaddress'), row.get('nasportid'), row.get('nasporttype'),
                row.get('acctstarttime'), row.get('acctstoptime'),
                row.get('acctsessiontime'), row.get('acctauthentic'),
                row.get('connectinfo_start'), row.get('connectinfo_stop'),
                row.get('acctinputoctets'), row.get('acctoutputoctets'),
                row.get('calledstationid'), row.get('callingstationid'),
                row.get('acctterminatecause'), row.get('servicetype'),
                row.get('framedprotocol'), row.get('framedipaddress'),
            ))
        _logger.info('TODD RADIUS: Sincronizadas %d sesiones radacct', len(rows))

    def name_get(self):
        result = []
        for rec in self:
            start = rec.acctstarttime.strftime('%Y-%m-%d %H:%M') if rec.acctstarttime else '?'
            result.append((rec.id, f"{rec.username} desde {rec.nasipaddress} el {start}"))
        return result
