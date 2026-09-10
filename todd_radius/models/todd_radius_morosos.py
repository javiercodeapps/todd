import logging
import subprocess

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ToddRadiusMorosos(models.Model):
    _name = 'todd.radius.morosos'
    _auto = False
    _description = 'Registro de morosos'
    _order = 'fecha desc'

    fecha = fields.Datetime(string='Fecha', required=True)
    fecha_proceso = fields.Datetime(string='Fecha Proceso')
    pendiente = fields.Boolean(string='Pendiente', default=True)
    descripcion = fields.Char(string='Descripción')
    detalle = fields.Text(string='Detalle')
    resultado = fields.Text(string='Resultado')
    usuario_id = fields.Many2one('res.users', string='Responsable')

    def init(self):
        self.env.cr.execute("""
            DROP TABLE IF EXISTS todd_radius_morosos CASCADE;
            CREATE TABLE todd_radius_morosos (
                id SERIAL PRIMARY KEY,
                fecha TIMESTAMP NOT NULL,
                fecha_proceso TIMESTAMP,
                pendiente BOOLEAN DEFAULT TRUE,
                descripcion VARCHAR(255),
                detalle TEXT,
                resultado TEXT,
                usuario_id INTEGER
            );
        """)

    def action_procesar(self):
        radusergroup = self.env['todd.radius.radusergroup']
        for rec in self:
            if not rec.detalle:
                continue
            usernames = [u.strip() for u in rec.detalle.split('\n') if u.strip()]
            resultados = []
            for username in usernames:
                try:
                    existing = radusergroup.search([
                        ('username', '=', username),
                        ('groupname', '=', 'moroso'),
                    ])
                    if existing:
                        existing.unlink()
                        resultados.append(f"{username}: removido de moroso")
                    else:
                        radusergroup.create([{
                            'username': username,
                            'groupname': 'moroso',
                            'priority': 0,
                        }])
                        resultados.append(f"{username}: agregado a moroso")
                except Exception as e:
                    resultados.append(f"{username}: error - {e}")
                    _logger.error('TODD RADIUS: Error procesando moroso %s: %s', username, e)
            rec.write({
                'resultado': '\n'.join(resultados),
                'pendiente': False,
                'fecha_proceso': fields.Datetime.now(),
            })

    def action_desconectar(self, username):
        try:
            subprocess.run(
                ['/opt/todd/scripts/disconnect.sh', username],
                capture_output=True, text=True, timeout=30,
            )
            _logger.info('TODD RADIUS: Desconectado usuario %s', username)
        except Exception as e:
            _logger.error('TODD RADIUS: Error desconectando %s: %s', username, e)
            raise

    def name_get(self):
        result = []
        for rec in self:
            date = rec.fecha.strftime('%Y-%m-%d %H:%M') if rec.fecha else '?'
            state = 'Pendiente' if rec.pendiente else 'Procesado'
            result.append((rec.id, f"{rec.descripcion or 'Moroso'} - {date} ({state})"))
        return result
