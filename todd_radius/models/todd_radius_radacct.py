import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_radacct AS
            SELECT 1 AS id, NULL::varchar AS acctsessionid, NULL::varchar AS acctuniqueid,
                   NULL::varchar AS username, NULL::varchar AS groupname, NULL::varchar AS realm,
                   NULL::varchar AS nasipaddress, NULL::varchar AS nasportid,
                   NULL::varchar AS nasporttype, NULL::timestamp AS acctstarttime,
                   NULL::timestamp AS acctstoptime, NULL::integer AS acctsessiontime,
                   NULL::varchar AS acctauthentic, NULL::varchar AS connectinfo_start,
                   NULL::varchar AS connectinfo_stop, NULL::integer AS acctinputoctets,
                   NULL::integer AS acctoutputoctets, NULL::varchar AS calledstationid,
                   NULL::varchar AS callingstationid, NULL::varchar AS acctterminatecause,
                   NULL::varchar AS servicetype, NULL::varchar AS framedprotocol,
                   NULL::varchar AS framedipaddress, NULL::integer AS radacctid
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT radacctid AS id FROM radacct WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'username' and leaf[1] == '=':
                query += " AND username = %s"
                params.append(leaf[2])
        if order:
            query += f" ORDER BY {order}"
        if limit:
            query += f" LIMIT {limit}"
        rows = Db._execute(query, tuple(params) if params else None)
        return self.browse([r['id'] for r in rows])

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(
            f"SELECT *, radacctid AS id FROM radacct WHERE radacctid IN ({placeholders})",
            tuple(self.ids),
        )
        rows_by_id = {r['id']: r for r in rows}
        return [{'id': rec.id, **rows_by_id.get(rec.id, {})} for rec in self]

    def name_get(self):
        result = []
        for rec in self:
            start = rec.acctstarttime.strftime('%d/%m %H:%M') if rec.acctstarttime else '?'
            result.append((rec.id, f"{rec.username} desde {rec.nasipaddress} el {start}"))
        return result
