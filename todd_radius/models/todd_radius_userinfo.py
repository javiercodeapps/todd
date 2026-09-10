import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FDW_TABLES = [
    'userinfo', 'radcheck', 'radreply', 'radusergroup',
    'radacct', 'radpostauth', 'nas', 'radippool',
]


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
        self.env.cr.execute("DROP VIEW IF EXISTS todd_radius_userinfo CASCADE")
        try:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_userinfo AS
                SELECT id AS radius_id, username, firstname, lastname, email, department, company,
                       workphone, homephone, mobilephone, address, notes, city, state, country, zip,
                       changeuserinfo::boolean, enableportallogin::boolean, tv::boolean,
                       tvuser, tvpass, portalloginpassword,
                       creationdate, updatedate, creationby, updateby
                FROM userinfo
            """)
        except Exception:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW todd_radius_userinfo AS
                SELECT 1 AS radius_id, NULL::varchar AS username, NULL::varchar AS firstname,
                       NULL::varchar AS lastname, NULL::varchar AS email, NULL::varchar AS department,
                       NULL::varchar AS company, NULL::varchar AS workphone, NULL::varchar AS homephone,
                       NULL::varchar AS mobilephone, NULL::text AS address, NULL::text AS notes,
                       NULL::varchar AS city, NULL::varchar AS state, NULL::varchar AS country,
                       NULL::varchar AS zip, FALSE AS changeuserinfo, FALSE AS enableportallogin,
                       FALSE AS tv, NULL::varchar AS tvuser, NULL::varchar AS tvpass,
                       NULL::varchar AS portalloginpassword, NULL::timestamp AS creationdate,
                       NULL::timestamp AS updatedate, NULL::varchar AS creationby, NULL::varchar AS updateby
                WHERE FALSE
            """)

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

    @api.model
    def action_setup_fdw(self):
        config = self.env['ir.config_parameter'].sudo()
        host = config.get_param('todd.radius.db_host', '10.0.2.12')
        port = config.get_param('todd.radius.db_port', '3306')
        user = config.get_param('todd.radius.db_user', 'radius-gestion')
        password = config.get_param('todd.radius.db_password', 'p4Bl1c')
        database = config.get_param('todd.radius.db_name', 'radius')

        try:
            self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS mysql_fdw")
        except Exception as e:
            raise UserError(f'No se pudo crear mysql_fdw. Ejecute como superuser:\nCREATE EXTENSION IF NOT EXISTS mysql_fdw;\n\nError: {e}')

        try:
            self.env.cr.execute("DROP SERVER IF EXISTS radius_mysql CASCADE")
            self.env.cr.execute("""
                CREATE SERVER radius_mysql
                FOREIGN DATA WRAPPER mysql_fdw
                OPTIONS (host %s, port %s)
            """, (host, port))
        except Exception as e:
            raise UserError(f'Error creando server FDW: {e}')

        try:
            self.env.cr.execute("DROP USER MAPPING IF EXISTS CURRENT_USER SERVER radius_mysql")
            self.env.cr.execute("""
                CREATE USER MAPPING FOR CURRENT_USER
                SERVER radius_mysql
                OPTIONS (username %s, password %s)
            """, (user, password))
        except Exception as e:
            raise UserError(f'Error creando user mapping: {e}')

        try:
            self.env.cr.execute(f"""
                IMPORT FOREIGN SCHEMA {database}
                LIMIT TO ({', '.join(FDW_TABLES)})
                FROM SERVER radius_mysql
                INTO public
            """)
        except Exception as e:
            _logger.warning('TODD RADIUS: IMPORT FOREIGN SCHEMA falló (puede que ya existan): %s', e)

        _logger.warning('TODD RADIUS: FDW setup completado')
        raise UserError('FDW configurado correctamente. Las tablas MySQL están disponibles como tablas PostgreSQL.')

    def action_test_connection(self):
        ok = self.env['todd.radius.db']._test_connection()
        raise UserError('Conexión MySQL OK' if ok else 'Fallo conexión. Revise todd.radius.db_* en Parámetros del Sistema')

    @api.model
    def action_diagnostico(self):
        _logger.warning('TODD RADIUS: === INICIO DIAGNOSTICO ===')
        Db = self.env['todd.radius.db']

        try:
            cfg = Db._get_config()
            _logger.warning('TODD RADIUS: Config: %s', cfg)
        except Exception as e:
            _logger.error('TODD RADIUS: Error leyendo config: %s', e)
            raise UserError(f'Error config: {e}')

        try:
            rows = Db._execute("SELECT COUNT(*) AS total FROM userinfo")
            total = rows[0]['total'] if rows else 0
            _logger.warning('TODD RADIUS: Total usuarios en MySQL: %s', total)
        except Exception as e:
            _logger.error('TODD RADIUS: Error consultando MySQL: %s', e)
            raise UserError(f'Error MySQL: {e}')

        try:
            sample = Db._execute("SELECT id, username, firstname, lastname FROM userinfo LIMIT 5")
            _logger.warning('TODD RADIUS: Muestra: %s', sample)
        except Exception as e:
            _logger.error('TODD RADIUS: Error en muestra: %s', e)
            sample = []

        msg = f"Config: {cfg.get('host')}:{cfg.get('port')}/{cfg.get('database')}\nTotal usuarios: {total}\n\nMuestra:\n"
        for r in sample:
            msg += f"  {r.get('id')}: {r.get('username')} - {r.get('firstname')} {r.get('lastname')}\n"
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
