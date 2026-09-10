import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PASSWORD_ATTRS = (
    'Cleartext-Password',
    'NT-Password',
    'MD5-Password',
    'Crypt-Password',
    'SHA2-Password',
)
USERINFO_EXCLUDE = ('portalloginpassword', 'tvpass')


def _api_key_ok():
    configured = (request.env['ir.config_parameter'].sudo().get_param('todd.radius.api_key') or '').strip()
    provided = (
        (request.httprequest.headers.get('X-Api-Key') or '')
        or (request.httprequest.args.get('apikey') or '')
    ).strip()
    return bool(configured and provided and hmac.compare_digest(configured, provided))


def _json_response(data, status=200):
    return request.make_response(
        json.dumps(data, default=str, ensure_ascii=False),
        headers=[
            ('Content-Type', 'application/json'),
        ],
    )


class ToddRadiusController(http.Controller):

    @http.route('/radius/user_info/data/<int:user_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def user_info_data(self, user_id, **kw):
        if not _api_key_ok():
            return _json_response({'error': 'Unauthorized'}, 401)

        Db = request.env['todd.radius.db'].sudo()

        rows = Db._execute(
            "SELECT * FROM userinfo WHERE id = %s", (user_id,)
        )
        if not rows:
            return _json_response({'error': 'Cliente no encontrado'}, 404)

        usuario = rows[0]
        username = usuario.get('username', '')

        sesiones = Db._execute(
            "SELECT * FROM radacct WHERE username = %s AND acctstoptime IS NULL",
            (username,),
        )

        checks = Db._execute(
            "SELECT * FROM radcheck WHERE username = %s", (username,)
        )

        radchecks_filtrados = [
            {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in c.items() if k not in ('id',) and c.get('attribute') not in PASSWORD_ATTRS}
            for c in checks
        ]

        raduserinfo = {
            k: (v.isoformat() if hasattr(v, 'isoformat') else v)
            for k, v in usuario.items()
            if k not in USERINFO_EXCLUDE
        }

        return _json_response({
            'user_id': usuario.get('id'),
            'raduserinfo': raduserinfo,
            'raduseracct': [
                {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in s.items()}
                for s in sesiones
            ],
            'radcheck': radchecks_filtrados,
        })

    @http.route('/radius/user_info/data', type='http', auth='none', methods=['GET'], csrf=False)
    def user_info_data_list(self, **kw):
        if not _api_key_ok():
            return _json_response({'error': 'Unauthorized'}, 401)

        Db = request.env['todd.radius.db'].sudo()
        username = kw.get('username') or kw.get('user_id')

        if not username:
            return _json_response({'error': 'Falta username'}, 400)

        rows = Db._execute(
            "SELECT * FROM userinfo WHERE username = %s", (username,)
        )
        if not rows:
            return _json_response({'error': 'Cliente no encontrado'}, 404)

        usuario = rows[0]

        sesiones = Db._execute(
            "SELECT * FROM radacct WHERE username = %s AND acctstoptime IS NULL",
            (username,),
        )

        checks = Db._execute(
            "SELECT * FROM radcheck WHERE username = %s", (username,)
        )

        radchecks_filtrados = [
            {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in c.items() if c.get('attribute') not in PASSWORD_ATTRS}
            for c in checks
        ]

        return _json_response({
            'user_id': usuario.get('id'),
            'raduserinfo': {
                k: (v.isoformat() if hasattr(v, 'isoformat') else v)
                for k, v in usuario.items()
                if k not in USERINFO_EXCLUDE
            },
            'raduseracct': [
                {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in s.items()}
                for s in sesiones
            ],
            'radcheck': radchecks_filtrados,
        })
