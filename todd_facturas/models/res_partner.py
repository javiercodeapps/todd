from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    todd_nro_socio = fields.Char(string='Nro. Socio')
    todd_nro_usuario = fields.Char(string='Nro. Usuario')

    def action_crear_usuario_portal(self):
        """Crear usuario de portal para este partner"""
        self.ensure_one()
        portal_group = self.env.ref('base.group_portal')

        # Verificar si ya tiene usuario portal
        users = self.env['res.users'].search([('partner_id', '=', self.id)])
        for user in users:
            if portal_group.id in user.groups_id.ids:
                return {'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {'title': 'Info', 'message': f'Ya tiene usuario portal: {user.login}', 'type': 'info'}}

        # Determinar login y contraseña
        login = self.todd_nro_usuario or f'todd_{self.todd_nro_socio}'
        if self.env['res.users'].search([('login', '=', login)], limit=1):
            login = f'todd_{self.todd_nro_socio}'

        password = self.vat or self.todd_nro_usuario or self.todd_nro_socio

        user = self.env['res.users'].create({
            'name': self.name,
            'login': login,
            'password': password,
            'partner_id': self.id,
            'share': True,
        })

        # Asignar grupo portal via SQL
        self.env.cr.execute(
            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (portal_group.id, user.id)
        )

        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Éxito', 'message': f'Usuario creado: {login}', 'type': 'success'}}

    def crear_usuario_portal_si_no_tiene(self):
        """Método para llamar desde otros módulos - crea usuario portal si no tiene"""
        portal_group = self.env.ref('base.group_portal')
        for partner in self:
            users = self.env['res.users'].search([('partner_id', '=', partner.id)])
            tiene_portal = False
            for user in users:
                if portal_group.id in user.groups_id.ids:
                    tiene_portal = True
                    break

            if not tiene_portal:
                login = partner.todd_nro_usuario or f'todd_{partner.todd_nro_socio}'
                if self.env['res.users'].search([('login', '=', login)], limit=1):
                    login = f'todd_{partner.todd_nro_socio}'
                password = partner.vat or partner.todd_nro_usuario or partner.todd_nro_socio
                user = self.env['res.users'].create({
                    'name': partner.name,
                    'login': login,
                    'password': password,
                    'partner_id': partner.id,
                    'share': True,
                })
                self.env.cr.execute(
                    "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (portal_group.id, user.id)
                )
        return True