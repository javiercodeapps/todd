import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusUserinfo(models.Model):
    _name = 'todd.radius.userinfo'
    _auto = False
    _description = 'Usuario RADIUS'
    _order = 'username'

    radius_id = fields.Integer(string='ID RADIUS', readonly=True)
    username = fields.Char(string='Usuario', required=True, index=True)
    firstname = fields.Char(string='Nombre')
    lastname = fields.Char(string='Apellido')
    email = fields.Char(string='Email')
    department = fields.Char(string='Departamento')
    company = fields.Char(string='Empresa')
    workphone = fields.Char(string='Tel. Trabajo')
    homephone = fields.Char(string='Tel. Casa')
    mobilephone = fields.Char(string='Móvil')
    address = fields.Text(string='Dirección')
    notes = fields.Text(string='Notas')
    city = fields.Char(string='Ciudad')
    state = fields.Char(string='Estado')
    country = fields.Char(string='País')
    zip = fields.Char(string='Cód. Postal')
    changeuserinfo = fields.Boolean(string='Cambiar Info')
    enableportallogin = fields.Boolean(string='Login Portal')
    tv = fields.Boolean(string='TV')
    tvuser = fields.Char(string='Usuario TV')
    tvpass = fields.Char(string='Pass TV')
    portalloginpassword = fields.Char(string='Pass Portal')
    creationdate = fields.Datetime(string='Creación')
    updatedate = fields.Datetime(string='Modificación')
    creationby = fields.Char(string='Creado por')
    updateby = fields.Char(string='Modificado por')

    password = fields.Char(string='Contraseña', compute='_compute_password', inverse='_inverse_password')
    groups_display = fields.Char(string='Grupos', compute='_compute_groups')
    ip_address = fields.Char(string='IP Asignada', compute='_compute_ip')
    is_online = fields.Boolean(string='Online', compute='_compute_online')

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW todd_radius_userinfo AS
            SELECT 1 AS id, NULL::varchar AS username, NULL::varchar AS firstname,
                   NULL::varchar AS lastname, NULL::varchar AS email,
                   NULL::varchar AS department, NULL::varchar AS company,
                   NULL::varchar AS workphone, NULL::varchar AS homephone,
                   NULL::varchar AS mobilephone, NULL::text AS address,
                   NULL::text AS notes, NULL::varchar AS city, NULL::varchar AS state,
                   NULL::varchar AS country, NULL::varchar AS zip,
                   NULL::varchar AS radius_id, NULL::boolean AS changeuserinfo,
                   NULL::boolean AS enableportallogin, NULL::boolean AS tv,
                   NULL::varchar AS tvuser, NULL::varchar AS tvpass,
                   NULL::varchar AS portalloginpassword, NULL::timestamp AS creationdate,
                   NULL::timestamp AS updatedate, NULL::varchar AS creationby,
                   NULL::varchar AS updateby
            WHERE FALSE
        """)

    def search(self, args=None, offset=0, limit=None, order=None):
        args = args or []
        Db = self.env['todd.radius.db']
        query = "SELECT id FROM userinfo WHERE 1=1"
        params = []
        for leaf in args:
            if leaf[0] == 'username' and leaf[1] == 'ilike':
                query += " AND username LIKE %s"
                params.append(f'%{leaf[2]}%')
            elif leaf[0] == 'firstname' and leaf[1] == 'ilike':
                query += " AND firstname LIKE %s"
                params.append(f'%{leaf[2]}%')
            elif leaf[0] == 'lastname' and leaf[1] == 'ilike':
                query += " AND lastname LIKE %s"
                params.append(f'%{leaf[2]}%')
            elif leaf[0] == 'company' and leaf[1] == 'ilike':
                query += " AND company LIKE %s"
                params.append(f'%{leaf[2]}%')
        if order:
            query += f" ORDER BY {order}"
        if limit:
            query += f" LIMIT {limit}"
        if offset:
            query += f" OFFSET {offset}"
        rows = Db._execute(query, tuple(params) if params else None)
        ids = [r['id'] for r in rows]
        return self.browse(ids)

    def read(self, fields=None, load='_classic_read'):
        if not self.ids:
            return []
        Db = self.env['todd.radius.db']
        placeholders = ','.join(['%s'] * len(self.ids))
        rows = Db._execute(f"SELECT * FROM userinfo WHERE id IN ({placeholders})", tuple(self.ids))
        rows_by_id = {r['id']: r for r in rows}
        result = []
        for rec in self:
            data = rows_by_id.get(rec.id, {})
            data['id'] = rec.id
            result.append(data)
        return result

    def _compute_password(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            rows = Db._execute(
                "SELECT value FROM radcheck WHERE username = %s AND attribute = 'Cleartext-Password' LIMIT 1",
                (rec.username,),
            )
            rec.password = rows[0]['value'] if rows else ''

    def _inverse_password(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            if not rec.username:
                continue
            Db._execute_write(
                "DELETE FROM radcheck WHERE username = %s AND attribute = 'Cleartext-Password'",
                (rec.username,),
            )
            if rec.password:
                Db._execute_write(
                    "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, 'Cleartext-Password', ':=', %s)",
                    (rec.username, rec.password),
                )

    def _compute_groups(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            rows = Db._execute(
                "SELECT groupname FROM radusergroup WHERE username = %s ORDER BY priority",
                (rec.username,),
            )
            rec.groups_display = ', '.join(r['groupname'] for r in rows) if rows else ''

    def _compute_ip(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            rows = Db._execute(
                "SELECT value FROM radreply WHERE username = %s AND attribute = 'Framed-IP-Address' LIMIT 1",
                (rec.username,),
            )
            rec.ip_address = rows[0]['value'] if rows else ''

    def _compute_online(self):
        Db = self.env['todd.radius.db']
        for rec in self:
            rows = Db._execute(
                "SELECT 1 FROM radacct WHERE username = %s AND acctstoptime IS NULL LIMIT 1",
                (rec.username,),
            )
            rec.is_online = bool(rows)

    def action_test_connection(self):
        ok = self.env['todd.radius.db']._test_connection()
        raise UserError('Conexión MySQL OK' if ok else 'Fallo conexión. Revise todd.radius.db_* en Parámetros del Sistema')

    def create(self, vals_list):
        Db = self.env['todd.radius.db']
        for vals in vals_list:
            username = vals.get('username')
            if not username:
                raise ValueError('El usuario es obligatorio')
            existing = Db._execute("SELECT id FROM userinfo WHERE username = %s", (username,))
            if existing:
                raise ValueError(f'El usuario {username} ya existe')
            Db._execute_write(
                """INSERT INTO userinfo (username, firstname, lastname, email, department, company,
                   workphone, homephone, mobilephone, address, notes, city, state, country, zip,
                   changeuserinfo, enableportallogin, tv, tvuser, tvpass, portalloginpassword,
                   creationdate, updateby, creationby)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s,%s)""",
                (
                    username, vals.get('firstname'), vals.get('lastname'), vals.get('email'),
                    vals.get('department'), vals.get('company'),
                    vals.get('workphone'), vals.get('homephone'), vals.get('mobilephone'),
                    vals.get('address'), vals.get('notes'),
                    vals.get('city'), vals.get('state'), vals.get('country'), vals.get('zip'),
                    1 if vals.get('changeuserinfo') else 0,
                    1 if vals.get('enableportallogin') else 0,
                    1 if vals.get('tv') else 0,
                    vals.get('tvuser'), vals.get('tvpass'), vals.get('portalloginpassword'),
                    self.env.user.login, self.env.user.login,
                ),
            )
        row = Db._execute("SELECT id FROM userinfo WHERE username = %s", (vals_list[0]['username'],))
        return self.browse([row[0]['id']]) if row else self.browse()

    def write(self, vals):
        Db = self.env['todd.radius.db']
        for rec in self:
            sets, params = [], []
            mapping = {
                'firstname': 'firstname', 'lastname': 'lastname', 'email': 'email',
                'department': 'department', 'company': 'company',
                'workphone': 'workphone', 'homephone': 'homephone', 'mobilephone': 'mobilephone',
                'address': 'address', 'notes': 'notes',
                'city': 'city', 'state': 'state', 'country': 'country', 'zip': 'zip',
                'changeuserinfo': 'changeuserinfo', 'enableportallogin': 'enableportallogin',
                'tv': 'tv', 'tvuser': 'tvuser', 'tvpass': 'tvpass',
                'portalloginpassword': 'portalloginpassword',
            }
            for odoo_field, mysql_col in mapping.items():
                if odoo_field in vals:
                    val = vals[odoo_field]
                    if odoo_field in ('changeuserinfo', 'enableportallogin', 'tv'):
                        val = 1 if val else 0
                    sets.append(f"{mysql_col} = %s")
                    params.append(val)
            if sets:
                sets.append("updatedate = NOW()")
                params.append(rec.username)
                Db._execute_write(
                    f"UPDATE userinfo SET {', '.join(sets)} WHERE username = %s", tuple(params),
                )
        return True

    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        return self.search([
            '|', '|', '|',
            ('username', operator, name),
            ('firstname', operator, name),
            ('lastname', operator, name),
            ('company', operator, name),
        ] + args, limit=limit).name_get()

    def name_get(self):
        result = []
        for rec in self:
            name = rec.username or f'id:{rec.id}'
            if rec.firstname or rec.lastname:
                name = f"{rec.username} - {rec.firstname or ''} {rec.lastname or ''}".strip()
            result.append((rec.id, name))
        return result
