==================
Todd Helpdesk Sync
==================

Extensión de ``helpdesk_mgmt`` (OCA) para **Odoo 19**. Cuando se crea un ticket
nuevo (backend, alias de correo o formulario web de ``website_helpdesk_mgmt``),
encola un job de ``queue_job`` que copia los datos básicos del ticket a **otra
instancia de Odoo vía XML-RPC**.

Qué hace
========

* Hook en ``helpdesk.ticket.create()`` (``@api.model_create_multi``): marca el
  ticket como *pendiente* y encola un job por ticket. La llamada de red **no**
  bloquea la creación del ticket.
* El job construye un payload con los campos básicos y crea un
  ``helpdesk.ticket`` en el servidor remoto con ``execute_kw``.
* Guarda en el ticket local el estado, el id remoto, la fecha, el número de
  intentos y el último error. Hay un botón **"Reenviar al servidor"** y una
  pestaña *"Réplica a servidor"* en el formulario.
* Evita duplicados con tres capas: estado ``done`` en el ticket, búsqueda por
  ``number`` en el remoto antes de crear, e ``identity_key`` de queue_job por
  ticket.
* Reintentos: hasta 5 intentos con backoff de 60/120/180/240 s. Los reintentos
  se encadenan con ``eta`` (en lugar de ``RetryableJobError``) porque queue_job
  hace *rollback* de todo lo escrito dentro de ``perform()`` cuando reintenta;
  así el estado y el error del ticket siempre quedan persistidos.
* Anti-bucle: el ``create`` remoto se llama con el contexto
  ``todd_helpdesk_sync_skip``. Si el otro servidor también tiene este módulo,
  no devolverá el ticket.

Configuración
=============

Ajustes → Helpdesk → bloque **"Réplica a otro servidor Odoo (XML-RPC)"**:

.. list-table::
   :header-rows: 1

   * - Parámetro (``ir.config_parameter``)
     - Uso
   * - ``todd_helpdesk_sync.enabled``
     - Interruptor general. Sin esto no se encola nada.
   * - ``todd_helpdesk_sync.remote_url``
     - ``https://odoo.empresa.com`` (sin barra final).
   * - ``todd_helpdesk_sync.remote_db``
     - Nombre de la base remota.
   * - ``todd_helpdesk_sync.remote_user``
     - Login del usuario remoto.
   * - ``todd_helpdesk_sync.remote_key``
     - API key (o contraseña) de ese usuario.
   * - ``todd_helpdesk_sync.timeout``
     - Timeout de socket en segundos (default 15).

El botón **"Probar conexión"** valida las credenciales contra
``/xmlrpc/2/common`` sin crear ningún ticket.

Seguridad
---------

El usuario remoto debe pertenecer al grupo **Helpdesk Manager** (o tener
reglas equivalentes): la búsqueda por ``number`` que evita duplicados debe ver
* todos * los tickets, no solo los propios. Usá una **API key con permisos
acotados** para ese usuario (lectura de ``helpdesk.ticket``,
``helpdesk.ticket.team/category/channel`` y ``res.company``; creación de
``helpdesk.ticket``). No uses ``admin_passwd`` ni
la contraseña de un administrador. El campo de la key está enmascarado en la
vista y restringido al grupo ``group_helpdesk_manager``, pero como todo
``ir.config_parameter`` sigue siendo legible por ORM para usuarios internos:
no lo trates como un secreto criptográfico.

Datos que se copian
===================

``number``, ``name``, ``description``, ``partner_name``, ``partner_email``,
``priority``, ``last_stage_update`` y ``assigned_date`` se envían tal cual.
Los campos relacionales se resuelven **por nombre** en el remoto (los ids
locales no sirven allí): ``team_id``, ``category_id``, ``channel_id`` y
``company_id``. Si no hay coincidencia se omite y aplica el default del remoto.
``stage_id`` lo calcula el remoto a partir del equipo.

No se copian adjuntos, chatter, seguidores, tags ni ``properties``. Si en el
futuro se necesitan, el punto de extensión es
``helpdesk.ticket._todd_sync_payload()`` / ``_todd_sync_send()``.

El payload completo (incluyendo ``origin_url``, ``origin_id`` y nombres de
equipo/categoría/canal/etapa/compañía) está disponible en
``_todd_sync_payload()`` para cambiar el transporte a REST sin tocar el modelo.

Supuestos
=========

* El remoto tiene instalado ``helpdesk_mgmt`` (mismo modelo ``helpdesk.ticket``).
* El ``number`` del ticket se preserva en el remoto para mantener trazabilidad
  y servir de clave de idempotencia. Si ambos servidores crean tickets con la
  misma secuencia, configurá prefijos distintos en el remoto.
* ``queue_job`` debe estar instalado (ya es dependencia de ``todd_facturas``).

Instalación / actualización
===========================

En el entorno de ``todd`` (DB ``todd``, según ``deploy.sh``)::

    /opt/odoo19/venv/bin/python /opt/odoo19/odoo/odoo-bin \
        -d todd -i todd_helpdesk_sync --stop-after-init

Para actualizar después de un cambio::

    /opt/odoo19/venv/bin/python /opt/odoo19/odoo/odoo-bin \
        -d todd -u todd_helpdesk_sync --stop-after-init

Tests::

    /opt/odoo19/venv/bin/python /opt/odoo19/odoo/odoo-bin \
        -d todd_test -i todd_helpdesk_sync --test-enable --stop-after-init

Estructura
==========

::

    todd_helpdesk_sync/
    ├── models/
    │   ├── todd_helpdesk_sync_client.py   # XML-RPC + timeout + excepciones
    │   ├── res_config_settings.py         # parámetros + "Probar conexión"
    │   └── helpdesk_ticket.py             # campos, create(), job, payload
    ├── views/                             # herencias de vistas OCA
    ├── tests/                             # trap_jobs + RemoteOdoo mockeado
    └── README.rst
