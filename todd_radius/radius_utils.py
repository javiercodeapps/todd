import datetime
import decimal

# Atributos de radcheck que nunca deben exponerse fuera del módulo.
PASSWORD_ATTRS = (
    'Cleartext-Password',
    'NT-Password',
    'MD5-Password',
    'Crypt-Password',
    'SHA2-Password',
)

# Columnas de userinfo que nunca deben exponerse fuera del módulo.
USERINFO_EXCLUDE = ('portalloginpassword', 'tvpass')


def json_safe_row(row, exclude=()):
    """Copia serializable a JSON de una fila devuelta por MySQL."""
    data = {}
    for clave, valor in row.items():
        if clave in exclude:
            continue
        if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
            valor = valor.isoformat()
        elif isinstance(valor, decimal.Decimal):
            valor = float(valor)
        elif isinstance(valor, (bytes, bytearray)):
            valor = valor.decode('utf-8', 'replace')
        data[clave] = valor
    return data
