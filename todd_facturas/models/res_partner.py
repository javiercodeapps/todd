from odoo import models, fields, api


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