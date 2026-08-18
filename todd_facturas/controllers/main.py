import os
import mimetypes
from odoo import http
from odoo.http import request, content_disposition


class ToddPortal(http.Controller):

    @http.route('/my/facturas', type='http', auth='user', website=True)
    def facturas(self, **kw):
        partner = request.env.user.partner_id
        facturas = request.env['account.move'].sudo().search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('todd_archivo_pdf', '!=', False)
        ])
        return request.render('todd_facturas.portal_facturas', {'facturas': facturas})

    @http.route('/my/factura/<int:factura_id>/pdf', type='http', auth='user', website=True)
    def factura_pdf(self, factura_id, **kw):
        partner = request.env.user.partner_id
        factura = request.env['account.move'].sudo().search([
            ('id', '=', factura_id),
            ('partner_id', '=', partner.id)
        ], limit=1)

        if not factura or not factura.todd_pdf_disponible:
            return request.redirect('/my/facturas')

        try:
            with open(factura.todd_pdf_ruta, 'rb') as f:
                content = f.read()
            ct = mimetypes.guess_type(factura.todd_pdf_ruta)[0] or 'application/pdf'
            return request.make_response(content, [
                ('Content-Type', ct),
                ('Content-Disposition', content_disposition(factura.todd_archivo_pdf))
            ])
        except:
            return request.redirect('/my/facturas')