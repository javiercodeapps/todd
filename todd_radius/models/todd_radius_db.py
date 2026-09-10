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
        return {
            'host': config.get_param('todd.radius.db_host', '10.0.2.12'),
            'port': int(config.get_param('todd.radius.db_port', '3306')),
            'user': config.get_param('todd.radius.db_user', 'radius-gestion'),
            'password': config.get_param('todd.radius.db_password', 'p4Bl1c'),
            'database': config.get_param('todd.radius.db_name', 'radius'),
            'charset': 'utf8mb4',
        }

    @contextmanager
    def _get_cursor(self):
        cfg = self._get_config()
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
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        except pymysql.Error as e:
            _logger.error('TODD RADIUS: Error de conexión MySQL: %s', e)
            raise UserError(f'Error de conexión a RADIUS: {e}')

    @api.model
    def _execute(self, query, params=None):
        with self._get_cursor() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    @api.model
    def _execute_write(self, query, params=None):
        with self._get_cursor() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount

    @api.model
    def _test_connection(self):
        try:
            with self._get_cursor() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    cur.fetchone()
            return True
        except Exception:
            return False
