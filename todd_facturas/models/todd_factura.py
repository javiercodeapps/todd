import json
import logging
import os
from datetime import date, datetime

import requests

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

PROVINCIANET_URL = 'https://service-payment.provincianet.com.ar/api/v1/service/preorder'
SERVICIOS = {
    'E': 'Energía',
    'A': 'Agua',
    'T': 'Telefonía',
    'I': 'Internet',
    'S': 'Sepelio',
    'N': 'Nichos',
}

PROVINCIANET_VENCIDO_MSG = (
    'El código de pago de esta factura%s está vencido y Provincia NET no '
    'acepta facturas vencidas. Puede abonar con las otras opciones de pago '
    'de esta página (billeteras virtuales, Pagos Link, débito automático o '
    'en sucursal) o comunicarse con cobranzas.'
)


def decodificar_codigo_pago(barcode):
    """Extrae vencimientos e importes de un código de pago electrónico.

    Los primeros 12 dígitos identifican al servicio; el resto depende del
    formato (los importes están expresados en centavos):

    - 30 dígitos: ``DDMMYY`` + 10 dígitos de importe + 2 de verificación.
    - 40 dígitos: ``DDMMYY`` + 7 + ``DDMMYY`` + 7 + 2 (1er y 2do vencimiento).

    Devuelve una lista de ``(fecha_vencimiento, importe)`` ordenada por fecha,
    o ``[]`` si el código no es reconocible. No depende de Odoo para poder
    testearse de forma aislada.
    """
    if not barcode or not barcode.isdigit() or len(barcode) not in (30, 40):
        return []
    try:
        if len(barcode) == 30:
            periodos = [(barcode[12:18], barcode[18:28])]
        else:
            periodos = [
                (barcode[12:18], barcode[18:25]),
                (barcode[25:31], barcode[31:38]),
            ]
        return sorted(
            (datetime.strptime(fecha, '%d%m%y').date(), int(importe) / 100)
            for fecha, importe in periodos
        )
    except (ValueError, TypeError):
        return []


class ToddFactura(models.Model):
    _name = 'todd.factura'
    _description = 'Factura Todd'
    _order = 'fecha_emision desc, id desc'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, index=True)
    servicio_id = fields.Many2one('todd.servicio', string='Servicio', index=True, ondelete='set null')
    periodo = fields.Char(string='Periodo', size=6)
    punto_venta = fields.Integer(string='Punto de Venta')
    nro_factura = fields.Integer(string='Nro. Factura', index=True)
    numero_completo = fields.Char(string='Número', compute='_compute_numero', store=True, index=True)
    fecha_emision = fields.Date(string='Fecha Emisión', index=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento')
    importe = fields.Float(string='Importe', digits=(12, 2))
    archivo_pdf = fields.Char(string='Archivo PDF')
    cod_pago_electronico = fields.Char(string='Cód. Pago Electrónico')
    cod_pago_electronico_otros = fields.Char(string='Cód. Pago Electrónico Otros')
    estado_pago = fields.Selection([
        ('pagado', 'Pagado'), ('adeudado', 'Adeudado'),
    ], string='Estado', default='adeudado', index=True)
    domicilio = fields.Char(string='Domicilio')
    servicio = fields.Selection([
        ('E', 'Energía'), ('A', 'Agua'), ('T', 'Telefonía'),
        ('I', 'Internet'), ('S', 'Sepelio'), ('N', 'Nichos'),
    ], string='Tipo Servicio', index=True)
    importe_2do_vencimiento = fields.Float(string='Importe 2do Venc.', digits=(12, 2))
    codigo_estado = fields.Char(string='Código Estado')
    dni = fields.Char(string='DNI')
    archivo_pdf_ruta = fields.Char(string='Ruta PDF')
    pdf_disponible = fields.Boolean(string='PDF Disponible', compute='_compute_pdf_disponible')

    @api.depends('punto_venta', 'nro_factura')
    def _compute_numero(self):
        for r in self:
            r.numero_completo = f'{r.punto_venta:04d}-{r.nro_factura:08d}' if r.punto_venta and r.nro_factura else ''

    @api.depends('archivo_pdf_ruta')
    def _compute_pdf_disponible(self):
        for r in self:
            r.pdf_disponible = bool(r.archivo_pdf_ruta and os.path.exists(r.archivo_pdf_ruta))

    def action_registrar_pago(self):
        for r in self:
            r.estado_pago = 'pagado'
        return True

    def provincianet_vencimiento(self):
        """Fecha límite real del código de pago que se envía a Provincia NET.

        El vencimiento embebido en el código de barras manda: es lo que valida
        el proveedor (un código vencido responde 422 "El servicio se encuentra
        vencido"). `fecha_vencimiento` se usa sólo como respaldo cuando el
        código no se puede decodificar.
        """
        self.ensure_one()
        periodos = decodificar_codigo_pago(self.cod_pago_electronico_otros)
        if periodos:
            return periodos[-1][0]
        return self.fecha_vencimiento or None

    def provincianet_bloqueada(self):
        """True si el proveedor rechazará el preorder por código vencido."""
        self.ensure_one()
        vencimiento = self.provincianet_vencimiento()
        return bool(vencimiento and vencimiento < date.today())

    def provincianet_mensaje_vencido(self):
        """Explicación para el portal cuando este medio de pago no aplica."""
        self.ensure_one()
        vencimiento = self.provincianet_vencimiento()
        detalle = (
            f' (venció el {vencimiento.strftime("%d/%m/%Y")})'
            if vencimiento else ''
        )
        return PROVINCIANET_VENCIDO_MSG % detalle

    def generar_url_provincianet(self):
        self.ensure_one()
        # Provincia NET valida la fecha de vencimiento del código de barras:
        # si ya pasó, responde 422. Evitamos el POST (y los reintentos del
        # usuario) cuando sabemos de antemano que va a ser rechazado.
        if self.provincianet_bloqueada():
            _logger.warning(
                'Provincia NET preorder bloqueado factura=%s código vencido el %s',
                self.id, self.provincianet_vencimiento(),
            )
            return False, self.provincianet_mensaje_vencido()

        partner = self.partner_id
        partes = (partner.name or '').split()
        last_name = partes[0] if partes else ''
        first_name = ' '.join(partes[1:]) if len(partes) > 1 else last_name

        hoy = date.today()
        # El importe del payload debe coincidir con el codificado en el
        # barcode; si difiere, el proveedor lo rechaza por inconsistencia.
        periodos = decodificar_codigo_pago(self.cod_pago_electronico_otros)
        if periodos:
            vigentes = [(f, m) for f, m in periodos if f >= hoy]
            monto = vigentes[0][1] if vigentes else self.importe
        elif self.fecha_vencimiento and hoy > self.fecha_vencimiento:
            monto = self.importe_2do_vencimiento or self.importe
        else:
            monto = self.importe

        dni = partner.vat or self.dni or '0'
        try:
            document_number = '%08d' % int(dni)
        except (TypeError, ValueError):
            document_number = str(dni).zfill(8)

        servicio_nombre = SERVICIOS.get(self.servicio, self.servicio or '')
        periodo = self.periodo or ''
        periodo_fmt = f'{periodo[4:6]}/{periodo[0:4]}' if len(periodo) == 6 else periodo

        payload = {
            'payer': {
                'first_name': first_name,
                'last_name': last_name,
                'email': partner.email or 'mail@todd.com.ar',
                'document_type': '1',
                'document_number': document_number,
                'gender': '1',
                'locked_payer': False,
            },
            'payments': [{
                'barcode': self.cod_pago_electronico_otros or '',
                'amount': f'{monto:.2f}',
                'service': servicio_nombre,
                'detail': f'{periodo_fmt} {servicio_nombre} {self.domicilio or ""}'.strip(),
            }],
        }
        api_key = (self.env['ir.config_parameter'].sudo().get_param(
            'todd.provincianet_api_key',
            'u1kRIYc6d9NSSHDsdbczTMChD4qSaQUPbw3M5ijg52GnW2du2m',
        ) or '').strip()
        _logger.warning(
            'Provincia NET preorder factura=%s barcode=%s amount=%s vencimiento=%s payload=%s api_key_len=%s',
            self.id,
            payload['payments'][0]['barcode'],
            payload['payments'][0]['amount'],
            self.provincianet_vencimiento(),
            json.dumps(payload, ensure_ascii=False),
            len(api_key),
        )
        try:
            response = requests.post(
                PROVINCIANET_URL,
                headers={'x-api-key': api_key, 'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=30,
            )
            body = (response.text or '')[:2000]
            _logger.warning(
                'Provincia NET response factura=%s status=%s body=%s',
                self.id, response.status_code, body,
            )
            try:
                data = response.json()
            except ValueError:
                _logger.error('Provincia NET respuesta no JSON para factura %s', self.id)
                return False, 'No se pudo generar el link de pago de Provincia NET.'
            url, error_msg = self._provincianet_parse_response(data)
            if not url:
                _logger.error('Provincia NET sin url para factura %s data=%s', self.id, data)
                return False, error_msg
            return url, False
        except Exception:
            _logger.exception('Provincia NET preorder failed for factura %s', self.id)
            return False, 'No se pudo conectar con Provincia NET. Intente nuevamente.'

    def _provincianet_parse_response(self, data):
        inner = data.get('data') if isinstance(data, dict) else None
        if isinstance(inner, dict):
            url = (inner.get('url') or '').replace('\\', '')
            if url:
                return url, False
            if inner.get('error'):
                return False, inner['error']
        elif isinstance(inner, str) and inner:
            return False, inner
        message = data.get('message') if isinstance(data, dict) else None
        if message and message not in ('Unprocessable Entity', 'Unauthorized', 'Forbidden'):
            return False, message
        return False, 'No se pudo generar el link de pago de Provincia NET.'
