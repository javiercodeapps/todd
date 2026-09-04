import hmac

from odoo import http
from odoo.http import request


class ToddApiCliente(http.Controller):

    def _provided_api_key(self):
        headers = request.httprequest.headers
        key = headers.get('X-Api-Key')
        if key:
            return key.strip()
        auth = headers.get('Authorization') or ''
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()
        return (request.params.get('apikey') or '').strip()

    def _check_api_key(self):
        configured = (request.env['ir.config_parameter'].sudo().get_param('todd.api_key') or '').strip()
        provided = self._provided_api_key()
        return bool(configured and provided and hmac.compare_digest(configured, provided))

    def _numero_from_request(self, numero=None, **kw):
        if numero:
            return numero
        if request.httprequest.method == 'POST' and request.httprequest.data:
            try:
                data = request.get_json_data() or {}
            except ValueError:
                data = {}
            for key in ('numero', 'documento', 'cliente', 'cuenta'):
                if data.get(key):
                    return str(data[key])
        for key in ('numero', 'documento', 'cliente', 'cuenta'):
            if kw.get(key):
                return kw[key]
        return False

    @http.route(
        ['/todd/api/cliente', '/todd/api/cliente/<string:numero>'],
        type='http', auth='public', methods=['GET', 'POST'], csrf=False, cors='*', save_session=False,
    )
    def cliente(self, numero=None, **kw):
        if not self._check_api_key():
            return request.make_json_response({'error': 'Unauthorized'}, status=401)
        numero = self._numero_from_request(numero, **kw)
        if not numero:
            return request.make_json_response(
                {'error': 'Falta número de documento, cliente o cuenta'},
                status=400,
            )
        data = request.env['res.partner'].sudo().todd_api_estado_cliente(numero, limit=kw.get('limit', 20))
        if not data:
            return request.make_json_response({'error': 'Cliente no encontrado'}, status=404)
        return request.make_json_response(data)
