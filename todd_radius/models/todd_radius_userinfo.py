import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ToddRadiusUserinfo(models.Model):
    _name = 'todd.radius.userinfo'
    _auto = False
    _inherit = ['todd.radius.db']
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
        self.env.cr.execute("DROP TABLE IF EXISTS todd_radius_userinfo CASCADE")
        self.env.cr.execute("""
            CREATE TABLE IF NOT EXISTS todd_radius_userinfo (
                id SERIAL PRIMARY KEY,
                radius_id INTEGER,
                username VARCHAR(255),
                firstname VARCHAR(255),
                lastname VARCHAR(255),
                email VARCHAR(255),
                department VARCHAR(255),
                company VARCHAR(255),
                workphone VARCHAR(255),
                homephone VARCHAR(255),
                mobilephone VARCHAR(255),
                address TEXT,
                notes TEXT,
                city VARCHAR(255),
                state VARCHAR(255),
                country VARCHAR(255),
                zip VARCHAR(255),
                changeuserinfo BOOLEAN,
                enableportallogin BOOLEAN,
                tv BOOLEAN,
                tvuser VARCHAR(255),
                tvpass VARCHAR(255),
                portalloginpassword VARCHAR(255),
                creationdate TIMESTAMP,
                updatedate TIMESTAMP,
                creationby VARCHAR(255),
                updateby VARCHAR(255)
            )
        """)

    def _sync_from_mysql(self):
        _logger.warning('TODD RADIUS: _sync_from_mysql() userinfo - iniciando sync desde MySQL')
        Db = self.env['todd.radius.db']
        try:
            rows = Db._execute("SELECT * FROM userinfo")
        except Exception as e:
            _logger.error('TODD RADIUS: Error syncing userinfo from MySQL: %s', e)
            raise UserError(
                'No se pudieron cargar datos de MySQL.\n\n'
                f'Error: {e}\n\n'
                'Verifique todd.radius.db_* en Parámetros del Sistema.'
            )

        self.env.cr.execute("DELETE FROM todd_radius_userinfo")
        if rows:
            cols = [
                'radius_id', 'username', 'firstname', 'lastname', 'email',
                'department', 'company', 'workphone', 'homephone', 'mobilephone',
                'address', 'notes', 'city', 'state', 'country', 'zip',
                'changeuserinfo', 'enableportallogin', 'tv',
                'tvuser', 'tvpass', 'portalloginpassword',
                'creationdate', 'updatedate', 'creationby', 'updateby',
            ]
            col_names = ', '.join(['id'] + cols)
            placeholders = ', '.join(['%s'] * (len(cols) + 1))
            values = []
            for row in rows:
                values.append(tuple(
                    [row.get('id')] + [row.get(c) for c in cols]
                ))
            self.env.cr.executemany(
                f"INSERT INTO todd_radius_userinfo ({col_names}) VALUES ({placeholders})",
                values,
            )
            _logger.warning('TODD RADIUS: userinfo sync OK - %s registros insertados en PostgreSQL', len(rows))
        else:
            _logger.warning('TODD RADIUS: userinfo sync OK - 0 registros en MySQL, staging vacio')

    def search(self, args, offset=0, limit=None, order=None, count=False):
        _logger.warning('TODD RADIUS: search() userinfo - args=%s limit=%s', args, limit)
        self._sync_from_mysql()
        result = super().search(args, offset=offset, limit=limit, order=order, count=count)
        _logger.warning('TODD RADIUS: search() userinfo - resultado: %s registros', len(result) if not count else result)
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

    @api.model
    def action_diagnostico(self):
        _logger.warning('TODD RADIUS: === INICIO DIAGNOSTICO ===')
        Db = self.env['todd.radius.db']

        try:
            cfg = Db._get_config()
        except Exception as e:
            raise UserError(f'Error leyendo config: {e}')

        try:
            rows = Db._execute("SELECT COUNT(*) AS total FROM userinfo")
            total = rows[0]['total'] if rows else 0
        except Exception as e:
            raise UserError(f'Error consultando MySQL: {e}\n\nConfig: {cfg.get("host")}:{cfg.get("port")}/{cfg.get("database")}')

        try:
            self.env.cr.execute("SELECT COUNT(*) FROM todd_radius_userinfo")
            pg_total = self.env.cr.fetchone()[0]
        except Exception as e:
            pg_total = f'ERROR: {e}'

        try:
            sample = Db._execute("SELECT id, username, firstname, lastname FROM userinfo LIMIT 3")
        except Exception as e:
            sample = []

        msg = (
            f"MySQL: {cfg.get('host')}:{cfg.get('port')}/{cfg.get('database')}\n"
            f"Registros en MySQL: {total}\n"
            f"Registros en PostgreSQL (staging): {pg_total}\n\n"
            f"Muestra MySQL:\n"
        )
        for r in sample:
            msg += f"  {r.get('id')}: {r.get('username')} - {r.get('firstname')} {r.get('lastname')}\n"
        if not sample:
            msg += "  (sin datos)\n"
        _logger.warning('TODD RADIUS: === FIN DIAGNOSTICO ===')
        raise UserError(msg)

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
