import os
import mimetypes
from datetime import date, timedelta
from odoo import http
from odoo.http import request, content_disposition

ITEMS_PER_PAGE = 10


class ToddPortal(http.Controller):

    @http.route('/my/facturas', type='http', auth='user', website=True)
    def facturas(self, page=1, **kw):
        partner = request.env.user.partner_id

        domain = [('partner_id', '=', partner.id)]

        total = request.env['todd.factura'].sudo().search_count(domain)
        facturas = request.env['todd.factura'].sudo().search(
            domain, order='fecha_emision desc',
            limit=ITEMS_PER_PAGE, offset=(int(page) - 1) * ITEMS_PER_PAGE
        )

        page = int(page)
        total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        values = {
            'facturas': facturas,
            'page': page,
            'total_pages': total_pages,
            'total': total,
            'page_start': (page - 1) * ITEMS_PER_PAGE + 1,
            'page_end': min(page * ITEMS_PER_PAGE, total),
        }
        return request.render('todd_facturas.portal_facturas', values)

    @http.route('/my/factura/<int:factura_id>/pago', type='http', auth='user', website=True)
    def factura_pago(self, factura_id, error=None, **kw):
        partner = request.env.user.partner_id
        factura = request.env['todd.factura'].sudo().search([
            ('id', '=', factura_id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if not factura:
            return request.redirect('/my/facturas')

        hoy = date.today()
        dias_deuda = (hoy - factura.fecha_emision).days if factura.fecha_emision else 0
        mas_90_dias = dias_deuda > 90

        values = {
            'factura': factura,
            'dias_deuda': dias_deuda,
            'mas_90_dias': mas_90_dias,
            'error_provincianet': error == 'provincianet',
        }
        return request.render('todd_facturas.portal_pago', values)

    @http.route('/my/factura/<int:factura_id>/provincianet', type='http', auth='user', website=True)
    def factura_provincianet(self, factura_id, **kw):
        partner = request.env.user.partner_id
        factura = request.env['todd.factura'].sudo().search([
            ('id', '=', factura_id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if not factura or factura.estado_pago == 'pagado':
            return request.redirect('/my/facturas')

        url = factura.generar_url_provincianet()
        if not url:
            return request.redirect(f'/my/factura/{factura.id}/pago?error=provincianet')
        return request.redirect(url, local=False)

    @http.route('/my/factura/<int:factura_id>/pdf', type='http', auth='user', website=True)
    def factura_pdf(self, factura_id, **kw):
        partner = request.env.user.partner_id
        factura = request.env['todd.factura'].sudo().search([
            ('id', '=', factura_id),
            ('partner_id', '=', partner.id)
        ], limit=1)

        if not factura or not factura.pdf_disponible:
            return request.redirect('/my/facturas')

        try:
            with open(factura.archivo_pdf_ruta, 'rb') as f:
                content = f.read()
            ct = mimetypes.guess_type(factura.archivo_pdf_ruta)[0] or 'application/pdf'
            return request.make_response(content, [
                ('Content-Type', ct),
                ('Content-Disposition', content_disposition(factura.archivo_pdf))
            ])
        except:
            return request.redirect('/my/facturas')
