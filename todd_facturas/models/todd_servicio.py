from odoo import models, fields, api


class ToddServicio(models.Model):
    _name = 'todd.servicio'
    _description = 'Servicio Todd'
    _order = 'tipo, nro_socio'

    unique_servicio = models.Constraint('''
        UNIQUE(partner_id, tipo, nro_usuario)
    ''', 'Ya existe un servicio de este tipo con ese número de usuario para este partner.')

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, index=True,
                                 ondelete='cascade')
    tipo = fields.Selection([
        ('E', 'Energía'), ('A', 'Agua'), ('T', 'Telefonía'),
        ('I', 'Internet'), ('S', 'Sepelio'), ('N', 'Nichos'),
    ], string='Tipo', required=True, index=True)
    nro_socio = fields.Char(string='Nro. Socio', required=True, index=True)
    nro_usuario = fields.Char(string='Nro. Usuario')
    nombre_usuario = fields.Char(string='Nombre Usuario')
    domicilio = fields.Char(string='Domicilio')
    facturas_count = fields.Integer(string='Facturas', compute='_compute_facturas_count')

    _rec_name = 'display_name'

    display_name = fields.Char(string='Nombre', compute='_compute_display_name', store=True)

    @api.depends('tipo', 'nro_socio', 'nro_usuario')
    def _compute_display_name(self):
        seleccion = dict(self._fields['tipo'].selection)
        for s in self:
            tipo_nombre = seleccion.get(s.tipo, s.tipo or '')
            parts = [tipo_nombre]
            if s.nro_socio:
                parts.append(f'Socio: {s.nro_socio}')
            if s.nro_usuario:
                parts.append(f'Usr: {s.nro_usuario}')
            s.display_name = ' - '.join(parts)

    def _compute_facturas_count(self):
        for svc in self:
            svc.facturas_count = self.env['todd.factura'].search_count([
                ('servicio_id', '=', svc.id)
            ])

    def action_ver_facturas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas - {self.display_name}',
            'res_model': 'todd.factura',
            'view_mode': 'list,form',
            'domain': [('servicio_id', '=', self.id)],
        }
