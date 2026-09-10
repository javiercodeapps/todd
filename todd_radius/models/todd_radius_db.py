import logging
from contextlib import contextmanager

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_mysql_driver = None


def _get_mysql_driver():
    global _mysql_driver
    if _mysql_driver is not None:
        return _mysql_driver

    for name, mod_name in [
        ('pymysql', 'pymysql'),
        ('mysql.connector', 'mysql.connector'),
        ('MySQLdb', 'MySQLdb'),
    ]:
        try:
            mod = __import__(mod_name, fromlist=['connect'])
            _mysql_driver = (name, mod)
            _logger.warning('TODD RADIUS: MySQL driver encontrado: %s', name)
            return _mysql_driver
        except ImportError:
            continue

    _mysql_driver = ('none', None)
    _logger.error(
        'TODD RADIUS: No hay driver MySQL instalado. '
        'Instale pymysql: pip3 install pymysql'
    )
    return _mysql_driver


class ToddRadiusDb(models.AbstractModel):
    _name = 'todd.radius.db'
    _description = 'Conexión DB RADIUS (MySQL)'

    @api.model
    def _get_config(self):
        config = self.env['ir.config_parameter'].sudo()
        cfg = {
            'host': config.get_param('todd.radius.db_host', '10.0.2.12'),
            'port': int(config.get_param('todd.radius.db_port', '3306')),
            'user': config.get_param('todd.radius.db_user', 'radius-gestion'),
            'password': config.get_param('todd.radius.db_password', 'p4Bl1c'),
            'database': config.get_param('todd.radius.db_name', 'radius'),
        }
        _logger.warning(
            'TODD RADIUS CONFIG: host=%s port=%s user=%s database=%s',
            cfg['host'], cfg['port'], cfg['user'], cfg['database'],
        )
        return cfg

    @contextmanager
    def _get_cursor(self):
        driver_name, driver = _get_mysql_driver()
        if driver is None:
            raise UserError(
                'No hay driver MySQL instalado. '
                'Instale pymysql (pip3 install pymysql) '
                'o python3-mysqldb (apt install python3-mysqldb).'
            )

        cfg = self._get_config()
        _logger.warning(
            'TODD RADIUS: Conectando con %s a %s@%s:%s/%s',
            driver_name, cfg['user'], cfg['host'], cfg['port'], cfg['database'],
        )

        try:
            if driver_name == 'pymysql':
                conn = driver.connect(
                    host=cfg['host'], port=cfg['port'],
                    user=cfg['user'], password=cfg['password'],
                    database=cfg['database'], charset='utf8mb4',
                    cursorclass=driver.cursors.DictCursor,
                    autocommit=False,
                )
            elif driver_name == 'mysql.connector':
                conn = driver.connect(
                    host=cfg['host'], port=cfg['port'],
                    user=cfg['user'], password=cfg['password'],
                    database=cfg['database'], charset='utf8mb4',
                    autocommit=False,
                )
            else:  # MySQLdb
                conn = driver.connect(
                    host=cfg['host'], port=cfg['port'],
                    user=cfg['user'], passwd=cfg['password'],
                    db=cfg['database'], charset='utf8mb4',
                )

            _logger.warning('TODD RADIUS: Conexión MySQL OK con %s', driver_name)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        except UserError:
            raise
        except Exception as e:
            _logger.error(
                'TODD RADIUS: Error de conexión MySQL: %s '
                '(driver=%s, host=%s, port=%s, user=%s, db=%s)',
                e, driver_name, cfg['host'], cfg['port'], cfg['user'], cfg['database'],
            )
            raise UserError(f'Error de conexión a RADIUS ({driver_name}): {e}')

    @api.model
    def _execute(self, query, params=None):
        _logger.warning('TODD RADIUS SQL: %s params=%s', query[:200], params)
        with self._get_cursor() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            _logger.warning('TODD RADIUS SQL: %s filas returned', len(rows))
            return rows

    @api.model
    def _execute_write(self, query, params=None):
        _logger.warning('TODD RADIUS SQL WRITE: %s params=%s', query[:200], params)
        with self._get_cursor() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rowcount = cur.rowcount
            cur.close()
            _logger.warning('TODD RADIUS SQL WRITE: %s filas afectadas', rowcount)
            return rowcount

    @api.model
    def _test_connection(self):
        _logger.warning('TODD RADIUS: Probando conexión...')
        driver_name, _ = _get_mysql_driver()
        _logger.warning('TODD RADIUS: Driver disponible: %s', driver_name)
        try:
            with self._get_cursor() as conn:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchone()
                cur.close()
            _logger.warning('TODD RADIUS: Test de conexión OK')
            return True
        except Exception as e:
            _logger.error('TODD RADIUS: Test de conexión FALLÓ: %s', e)
            return False
