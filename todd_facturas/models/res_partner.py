import logging

import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

RADIUS_URL = 'https://radius-gestion.todd.com.ar/radius/numero_cliente/index'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    todd_nro_socio = fields.Char(string='Nro. Socio')
    todd_nro_usuario = fields.Char(string='Nro. Usuario')

    def _tiene_grupo_portal(self, user):
        """Verificar si un usuario tiene el grupo portal via SQL"""
        portal_group = self.env.ref('base.group_portal')
        self.env.cr.execute(
            "SELECT 1 FROM res_groups_users_rel WHERE gid = %s AND uid = %s",
            (portal_group.id, user.id)
        )
        return bool(self.env.cr.fetchone())

    def action_crear_usuario_portal(self):
        """Crear usuario de portal para este partner"""
        self.ensure_one()
        portal_group = self.env.ref('base.group_portal')

        users = self.env['res.users'].search([('partner_id', '=', self.id)])
        for user in users:
            if self._tiene_grupo_portal(user):
                return {'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {'title': 'Info', 'message': f'Ya tiene usuario portal: {user.login}', 'type': 'info'}}

        login = self.vat or self.todd_nro_socio
        if not login:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Error', 'message': 'No tiene DNI/Nro Socio definido', 'type': 'danger'}}

        if self.env['res.users'].search([('login', '=', login)], limit=1):
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': 'Error', 'message': f'Ya existe usuario con login: {login}', 'type': 'danger'}}

        password = self.vat or self.todd_nro_socio

        user = self.env['res.users'].create({
            'name': self.name,
            'login': login,
            'password': password,
            'partner_id': self.id,
            'share': True,
        })

        # Solo grupo portal, quitar otros
        self.env.cr.execute(
            "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid != %s",
            (user.id, portal_group.id)
        )
        self.env.cr.execute(
            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (portal_group.id, user.id)
        )
        # Asegurar share=True via SQL
        self.env.cr.execute(
            "UPDATE res_users SET share=true WHERE id=%s",
            (user.id,)
        )

        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Éxito', 'message': f'Usuario portal creado: {login}', 'type': 'success'}}

    def crear_usuario_portal_si_no_tiene(self):
        """Crea usuario portal si no tiene - login y password = DNI"""
        portal_group = self.env.ref('base.group_portal')
        for partner in self:
            users = self.env['res.users'].search([('partner_id', '=', partner.id)])
            tiene_portal = False
            for u in users:
                self.env.cr.execute(
                    "SELECT 1 FROM res_groups_users_rel WHERE gid = %s AND uid = %s",
                    (portal_group.id, u.id)
                )
                if self.env.cr.fetchone():
                    tiene_portal = True
                    break

            if not tiene_portal:
                login = partner.vat or partner.todd_nro_socio
                if not login:
                    continue
                if self.env['res.users'].search([('login', '=', login)], limit=1):
                    continue

                # Asegurar idioma del partner
                if not partner.lang:
                    partner.sudo().write({'lang': 'es_AR'})

                password = login
                user = self.env['res.users'].create({
                    'name': partner.name,
                    'login': login,
                    'password': password,
                    'partner_id': partner.id,
                    'share': True,
                })

                # Solo grupo portal, quitar otros
                self.env.cr.execute(
                    "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid != %s",
                    (user.id, portal_group.id)
                )
                self.env.cr.execute(
                    "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (portal_group.id, user.id)
                )
                # Asegurar share=True via SQL
                self.env.cr.execute(
                    "UPDATE res_users SET share=true WHERE id=%s",
                    (user.id,)
                )
        return True

    @api.model
    def _todd_variantes_numero(self, numero):
        n = (numero or '').strip()
        if not n:
            return []
        variantes = {n}
        sin_ceros = n.lstrip('0') or '0'
        variantes.add(sin_ceros)
        if n.isdigit():
            variantes.add(n.zfill(8))
            variantes.add(sin_ceros.zfill(8))
        return list(variantes)

    @api.model
    def todd_buscar_por_numero(self, numero):
        variantes = self._todd_variantes_numero(numero)
        if not variantes:
            return self.browse()
        partner = self.search([
            '|', '|',
            ('todd_nro_socio', 'in', variantes),
            ('todd_nro_usuario', 'in', variantes),
            ('vat', 'in', variantes),
        ], limit=1)
        if partner:
            return partner
        factura = self.env['todd.factura'].search([
            '|', '|',
            ('dni', 'in', variantes),
            ('nro_usuario', 'in', variantes),
            ('referencia', 'in', variantes),
        ], limit=1)
        return factura.partner_id

    @api.model
    def _todd_consultar_radius(self, numero_cliente):
        config = self.env['ir.config_parameter'].sudo()
        api_key = (config.get_param('todd.radius_api_key') or '').strip()
        base = (config.get_param('todd.radius_url', RADIUS_URL) or RADIUS_URL).strip().rstrip('/')
        if not api_key:
            return False, 'API key de Radius no configurada'
        if not numero_cliente:
            return False, 'Sin número de cliente para Radius'
        try:
            response = requests.get(
                f'{base}/{numero_cliente}',
                headers={'X-Api-Key': api_key, 'Accept': 'application/json'},
                params={'apikey': api_key},
                timeout=15,
            )
            try:
                data = response.json()
            except ValueError:
                _logger.warning(
                    'Radius respuesta no JSON status=%s body=%s',
                    response.status_code, (response.text or '')[:500],
                )
                return False, f'Radius status {response.status_code}'
            if response.status_code >= 400:
                error = data.get('error') or data.get('message') or f'Radius status {response.status_code}'
                return data, error
            return data, False
        except Exception:
            _logger.exception('Radius consulta falló para %s', numero_cliente)
            return False, 'No se pudo conectar con Radius'

    @api.model
    def todd_api_estado_cliente(self, numero, limit=20):
        try:
            limit = max(1, min(int(limit or 20), 50))
        except (TypeError, ValueError):
            limit = 20
        partner = self.todd_buscar_por_numero(numero)
        if not partner:
            return False
        facturas = self.env['todd.factura'].search(
            [('partner_id', '=', partner.id)],
            order='fecha_emision desc, id desc',
            limit=limit,
        )
        seleccion = dict(self.env['todd.factura']._fields['servicio'].selection)
        radius, radius_error = self._todd_consultar_radius(partner.todd_nro_socio or numero)
        return {
            'partner': {
                'id': partner.id,
                'name': partner.name,
                'vat': partner.vat or False,
                'nro_socio': partner.todd_nro_socio or False,
                'nro_usuario': partner.todd_nro_usuario or False,
            },
            'facturas': [{
                'id': f.id,
                'numero': f.numero_completo,
                'servicio': f.servicio,
                'servicio_nombre': seleccion.get(f.servicio, f.servicio),
                'periodo': f.periodo,
                'fecha_emision': f.fecha_emision.isoformat() if f.fecha_emision else False,
                'fecha_vencimiento': f.fecha_vencimiento.isoformat() if f.fecha_vencimiento else False,
                'importe': f.importe,
                'importe_2do_vencimiento': f.importe_2do_vencimiento,
                'estado_pago': f.estado_pago,
                'domicilio': f.domicilio,
                'nro_usuario': f.nro_usuario,
            } for f in facturas],
            'radius': radius,
            'radius_error': radius_error,
        }