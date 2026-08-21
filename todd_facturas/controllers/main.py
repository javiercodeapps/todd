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

        domain = [
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('todd_archivo_pdf', '!=', False)
        ]

        total = request.env['account.move'].sudo().search_count(domain)
        facturas = request.env['account.move'].sudo().search(
            domain, order='invoice_date desc',
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
    def factura_pago(self, factura_id, **kw):
        partner = request.env.user.partner_id
        factura = request.env['account.move'].sudo().search([
            ('id', '=', factura_id),
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
        ], limit=1)

        if not factura:
            return request.redirect('/my/facturas')

        # Calcular días de deuda
        hoy = date.today()
        dias_deuda = (hoy - factura.invoice_date).days if factura.invoice_date else 0
        mas_90_dias = dias_deuda > 90

        values = {
            'factura': factura,
            'dias_deuda': dias_deuda,
            'mas_90_dias': mas_90_dias,
        }
        return request.render('todd_facturas.portal_pago', values)

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

    @http.route('/my/invoices', type='http', auth='user', website=True)
    def portal_my_invoices(self, **kw):
        partner = request.env.user.partner_id
        invoices = request.env['account.move'].sudo().search([
            ('partner_id', '=', partner.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ])
        return request.render('account.portal_my_invoices', {'invoices': invoices, 'page_name': 'invoices'})