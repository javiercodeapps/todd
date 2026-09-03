import base64
from odoo import http
from odoo.http import request


class WebsiteVideoUploadController(http.Controller):

    @http.route('/website_video_upload/upload', type='http', auth='user',
                methods=['POST'], website=True, csrf=True)
    def upload_video(self, video_file, **kwargs):
        if not video_file:
            return request.make_json_response(
                {'error': 'No file provided'}, status=400,
            )
        data = base64.b64encode(video_file.read())
        attachment = request.env['ir.attachment'].create({
            'name': video_file.filename,
            'datas': data,
            'res_model': 'ir.ui.view',
            'res_id': 0,
            'type': 'binary',
            'public': True,
        })
        url = f'/web/content/{attachment.id}/{video_file.filename}'
        return request.make_json_response({
            'url': url,
            'id': attachment.id,
        })
