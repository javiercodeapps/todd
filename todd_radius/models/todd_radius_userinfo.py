import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusUserinfo(models.Model):
    _name = 'todd.radius.userinfo'
    _auto = False
    _description = 'Usuario RADIUS (userinfo)'
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
    zip = fields.Char(string='Código Postal')
    changeuserinfo = fields.Boolean(string='Cambiar Info', default=False)
    enableportallogin = fields.Boolean(string='Login Portal', default=False)
    tv = fields.Boolean(string='TV', default=False)
    tvuser = fields.Char(string='Usuario TV')
    tvpass = fields.Char(string='Pass TV')
    portalloginpassword = fields.Char(string='Pass Portal')
    creationdate = fields.Datetime(string='Fecha Creación')
    updatedate = fields.Datetime(string='Fecha Actualización')
    creationby = fields.Char(string='Creado por')
    updateby = fields.Char(string='Actualizado por')

    password = fields.Char(string='Contraseña', compute='_compute_password', inverse='_inverse_password')
    groups_display = fields.Char(string='Grupos', compute='_compute_groups')
    ip_address = fields.Char(string='IP Asignada', compute='_compute_ip_address')
    is_online = fields.Boolean(string='En línea', compute='_compute_is_online')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_userinfo CASCADE;
            CREATE TABLE todd_radius_userinfo (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(64) NOT NULL,
                firstname VARCHAR(128),
                lastname VARCHAR(128),
                email VARCHAR(255),
                department VARCHAR(128),
                company VARCHAR(255),
                workphone VARCHAR(32),
                homephone VARCHAR(32),
                mobilephone VARCHAR(32),
                address TEXT,
                notes TEXT,
                city VARCHAR(128),
                state VARCHAR(128),
                country VARCHAR(128),
                zip VARCHAR(16),
                changeuserinfo BOOLEAN DEFAULT FALSE,
                enableportallogin BOOLEAN DEFAULT FALSE,
                tv BOOLEAN DEFAULT FALSE,
                tvuser VARCHAR(128),
                tvpass VARCHAR(128),
                portalloginpassword VARCHAR(128),
                creationdate TIMESTAMP,
                updatedate TIMESTAMP,
                creationby VARCHAR(64),
                updateby VARCHAR(64)
            );
            CREATE INDEX idx_todd_radius_userinfo_username ON todd_radius_userinfo(username);
        """)

    def _compute_password(self):
        for rec in self:
            rows = self.env['todd.radius.db']._execute(
                "SELECT value FROM radcheck WHERE username = %s AND attribute = 'Cleartext-Password' LIMIT 1",
                (rec.username,)
            )
            rec.password = rows[0]['value'] if rows else ''

    def _inverse_password(self):
        for rec in self:
            if not rec.username:
                continue
            self.env['todd.radius.db']._execute_write(
                "DELETE FROM radcheck WHERE username = %s AND attribute = 'Cleartext-Password'",
                (rec.username,)
            )
            if rec.password:
                self.env['todd.radius.db']._execute_write(
                    "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, 'Cleartext-Password', ':=', %s)",
                    (rec.username, rec.password)
                )

    def _compute_groups(self):
        for rec in self:
            rows = self.env['todd.radius.db']._execute(
                "SELECT groupname FROM radusergroup WHERE username = %s ORDER BY priority",
                (rec.username,)
            )
            rec.groups_display = ', '.join(r['groupname'] for r in rows) if rows else ''

    def _compute_ip_address(self):
        for rec in self:
            rows = self.env['todd.radius.db']._execute(
                "SELECT value FROM radreply WHERE username = %s AND attribute = 'Framed-IP-Address' LIMIT 1",
                (rec.username,)
            )
            rec.ip_address = rows[0]['value'] if rows else ''

    def _compute_is_online(self):
        for rec in self:
            rows = self.env['todd.radius.db']._execute(
                "SELECT 1 FROM radacct WHERE username = %s AND acctstoptime IS NULL LIMIT 1",
                (rec.username,)
            )
            rec.is_online = bool(rows)

    def sync_from_radius(self):
        self.env.cr.execute("DELETE FROM todd_radius_userinfo")
        rows = self.env['todd.radius.db']._execute("SELECT * FROM userinfo")
        if not rows:
            return
        for row in rows:
            self.env.cr.execute("""
                INSERT INTO todd_radius_userinfo
                    (radius_id, username, firstname, lastname, email, department, company,
                     workphone, homephone, mobilephone, address, notes, city, state, country, zip,
                     changeuserinfo, enableportallogin, tv, tvuser, tvpass, portalloginpassword,
                     creationdate, updatedate, creationby, updateby)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row.get('id'), row.get('username'), row.get('firstname'), row.get('lastname'),
                row.get('email'), row.get('department'), row.get('company'),
                row.get('workphone'), row.get('homephone'), row.get('mobilephone'),
                row.get('address'), row.get('notes'),
                row.get('city'), row.get('state'), row.get('country'), row.get('zip'),
                row.get('changeuserinfo') in ('1', 1, True),
                row.get('enableportallogin') in ('1', 1, True),
                row.get('tv') in ('1', 1, True),
                row.get('tvuser'), row.get('tvpass'), row.get('portalloginpassword'),
                row.get('creationdate'), row.get('updatedate'),
                row.get('creationby'), row.get('updateby'),
            ))
        _logger.info('TODD RADIUS: Sincronizados %d usuarios userinfo', len(rows))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            username = vals.get('username')
            if not username:
                raise ValueError('El usuario es obligatorio')
            existing = self.env['todd.radius.db']._execute(
                "SELECT id FROM userinfo WHERE username = %s", (username,)
            )
            if existing:
                raise ValueError(f'El usuario {username} ya existe en RADIUS')
            self.env['todd.radius.db']._execute_write("""
                INSERT INTO userinfo (username, firstname, lastname, email, department, company,
                    workphone, homephone, mobilephone, address, notes, city, state, country, zip,
                    changeuserinfo, enableportallogin, tv, tvuser, tvpass, portalloginpassword,
                    creationdate, updatedate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                username, vals.get('firstname'), vals.get('lastname'), vals.get('email'),
                vals.get('department'), vals.get('company'),
                vals.get('workphone'), vals.get('homephone'), vals.get('mobilephone'),
                vals.get('address'), vals.get('notes'),
                vals.get('city'), vals.get('state'), vals.get('country'), vals.get('zip'),
                1 if vals.get('changeuserinfo') else 0,
                1 if vals.get('enableportallogin') else 0,
                1 if vals.get('tv') else 0,
                vals.get('tvuser'), vals.get('tvpass'), vals.get('portalloginpassword'),
            ))
        self.sync_from_radius()
        record = self.search([('username', '=', vals_list[0]['username'])], limit=1)
        return record

    def write(self, vals):
        for rec in self:
            sets = []
            params = []
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
                self.env['todd.radius.db']._execute_write(
                    f"UPDATE userinfo SET {', '.join(sets)} WHERE username = %s", tuple(params)
                )
        self.sync_from_radius()
        return True

    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = [
            '|', '|', '|',
            ('username', operator, name),
            ('firstname', operator, name),
            ('lastname', operator, name),
            ('company', operator, name),
        ]
        return self.search(domain + args, limit=limit).name_get()

    def name_get(self):
        result = []
        for rec in self:
            name = rec.username
            if rec.firstname or rec.lastname:
                full = f"{rec.firstname or ''} {rec.lastname or ''}".strip()
                name = f"{rec.username} - {full}"
            result.append((rec.id, name))
        return result
