from odoo import api, fields, models

from .todd_factura import ESTADOS_PAGO, ORIGENES_CAMBIO, SENTIDOS_CAMBIO


class ToddFacturaEstadoHistorial(models.Model):
    """Un registro por cada cambio real de ``todd.factura.estado_pago``.

    El chatter es cómodo para leer una factura, pero no se puede filtrar ni
    agrupar: por eso cada cambio además deja una fila consultable con el TXT,
    la línea, el valor crudo, el sentido del cambio y el usuario. Así se puede
    responder "¿quién pasó esta factura a Adeudado y desde qué archivo?" sin
    leer el chatter factura por factura.
    """

    _name = 'todd.factura.estado.historial'
    _description = 'Historial de cambios de estado de pago'
    _order = 'fecha desc, id desc'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    factura_id = fields.Many2one(
        'todd.factura', string='Factura', required=True,
        ondelete='cascade', index=True, readonly=True,
    )
    fecha = fields.Datetime(
        string='Fecha', required=True, readonly=True, index=True,
        default=lambda self: fields.Datetime.now(),
    )
    estado_anterior = fields.Selection(
        ESTADOS_PAGO, string='Estado anterior', readonly=True,
    )
    estado_nuevo = fields.Selection(
        ESTADOS_PAGO, string='Estado nuevo', required=True, readonly=True,
    )
    sentido = fields.Selection(
        SENTIDOS_CAMBIO, string='Sentido', required=True, readonly=True, index=True,
    )
    origen = fields.Selection(
        ORIGENES_CAMBIO, string='Origen', required=True, readonly=True, index=True,
    )
    txt_nombre = fields.Char(string='Archivo TXT', readonly=True, index=True)
    txt_import_id = fields.Many2one(
        'todd.txt.import', string='Importación', readonly=True,
    )
    linea_txt = fields.Integer(string='Línea del TXT', readonly=True)
    estado_comp = fields.Char(
        string='Valor crudo del TXT', readonly=True,
        help="Contenido literal de la columna 'estado_comp' que originó el cambio.",
    )
    user_id = fields.Many2one(
        'res.users', string='Usuario', readonly=True,
        default=lambda self: self.env.user,
    )
    nota = fields.Text(string='Nota', readonly=True)

    @api.depends(
        'factura_id.numero_completo', 'estado_anterior', 'estado_nuevo',
        'txt_nombre', 'origen',
    )
    def _compute_name(self):
        etiquetas = dict(ESTADOS_PAGO)
        origenes = dict(ORIGENES_CAMBIO)
        for rec in self:
            rec.name = '%s: %s → %s (%s)' % (
                rec.factura_id.numero_completo or rec.factura_id.id,
                etiquetas.get(rec.estado_anterior, '—'),
                etiquetas.get(rec.estado_nuevo, '—'),
                rec.txt_nombre or origenes.get(rec.origen, rec.origen),
            )
