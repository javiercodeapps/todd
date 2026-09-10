from odoo import api, fields, models


class ToddRadiusRadacct(models.Model):
    _name = 'todd.radius.radacct'
    _auto = False
    _description = 'Sesiones RADIUS'

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
    connectinfo_start = fields.Char(string='Info Inicio')
    connectinfo_stop = fields.Char(string='Info Fin')
    acctinputoctets = fields.Integer(string='Bytes Entrada')
    acctoutputoctets = fields.Integer(string='Bytes Salida')
    calledstationid = fields.Char(string='Llamado')
    callingstationid = fields.Char(string='Llamante')
    acctterminatecause = fields.Char(string='Causa Fin')
    servicetype = fields.Char(string='Tipo Servicio')
    framedprotocol = fields.Char(string='Protocolo')
    framedipaddress = fields.Char(string='IP Framed')

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_radacct CASCADE")
        try:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radacct AS
                SELECT radacctid AS id, radacctid, acctsessionid, acctuniqueid,
                       username, groupname, realm, nasipaddress, nasportid, nasporttype,
                       acctstarttime, acctstoptime, acctsessiontime, acctauthentic,
                       connectinfo_start, connectinfo_stop, acctinputoctets, acctoutputoctets,
                       calledstationid, callingstationid, acctterminatecause, servicetype,
                       framedprotocol, framedipaddress
                FROM radacct
            """)
        except Exception:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_radacct AS
                SELECT 1 AS id, 1 AS radacctid, NULL::varchar AS acctsessionid,
                       NULL::varchar AS acctuniqueid, NULL::varchar AS username,
                       NULL::varchar AS groupname, NULL::varchar AS realm,
                       NULL::varchar AS nasipaddress, NULL::varchar AS nasportid,
                       NULL::varchar AS nasporttype, NULL::timestamp AS acctstarttime,
                       NULL::timestamp AS acctstoptime, 0 AS acctsessiontime,
                       NULL::varchar AS acctauthentic, NULL::varchar AS connectinfo_start,
                       NULL::varchar AS connectinfo_stop, 0 AS acctinputoctets,
                       0 AS acctoutputoctets, NULL::varchar AS calledstationid,
                       NULL::varchar AS callingstationid, NULL::varchar AS acctterminatecause,
                       NULL::varchar AS servicetype, NULL::varchar AS framedprotocol,
                       NULL::varchar AS framedipaddress
                WHERE FALSE
            """)

    def name_get(self):
        result = []
        for rec in self:
            start = rec.acctstarttime.strftime('%d/%m %H:%M') if rec.acctstarttime else '?'
            result.append((rec.id, f"{rec.username} desde {rec.nasipaddress} el {start}"))
        return result
