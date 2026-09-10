import logging
from contextlib import contextmanager

import pymysql

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
            'charset': 'utf8mb4',
        }
        _logger.warning('TODD RADIUS CONFIG: host=%s port=%s user=%s database=%s',
                        cfg['host'], cfg['port'], cfg['user'], cfg['database'])
        return cfg

    @contextmanager
    def _get_cursor(self):
        cfg = self._get_config()
        _logger.warning('TODD RADIUS: Intentando conectar a MySQL %s@%s:%s/%s',
                        cfg['user'], cfg['host'], cfg['port'], cfg['database'])
        try:
            conn = pymysql.connect(
                host=cfg['host'],
                port=cfg['port'],
                user=cfg['user'],
                password=cfg['password'],
                database=cfg['database'],
                charset=cfg['charset'],
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
            _logger.warning('TODD RADIUS: Conexión MySQL OK')
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
                _logger.warning('TODD RADIUS: Conexión MySQL cerrada')
        except pymysql.Error as e:
            _logger.error('TODD RADIUS: Error de conexión MySQL: %s (host=%s, port=%s, user=%s, db=%s)',
                          e, cfg['host'], cfg['port'], cfg['user'], cfg['database'])
            raise UserError(f'Error de conexión a RADIUS: {e}')
        except Exception as e:
            _logger.error('TODD RADIUS: Error inesperado de conexión: %s', e)
            raise

    @api.model
    def _execute(self, query, params=None):
        _logger.warning('TODD RADIUS SQL: %s params=%s', query[:200], params)
        with self._get_cursor() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                _logger.warning('TODD RADIUS SQL: %s filas returned', len(rows))
                return rows

    @api.model
    def _execute_write(self, query, params=None):
        _logger.warning('TODD RADIUS SQL WRITE: %s params=%s', query[:200], params)
        with self._get_cursor() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rowcount = cur.rowcount
                _logger.warning('TODD RADIUS SQL WRITE: %s filas afectadas', rowcount)
                return rowcount

    @api.model
    def _test_connection(self):
        _logger.warning('TODD RADIUS: Probando conexión...')
        try:
            with self._get_cursor() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    cur.fetchone()
            _logger.warning('TODD RADIUS: Test de conexión OK')
            return True
        except Exception as e:
            _logger.error('TODD RADIUS: Test de conexión FALLÓ: %s', e)
            return False
