# -*- coding: utf-8 -*-

from odoo import fields, models


class Users(models.Model):
    _inherit = "res.users"

    enable_idle = fields.Boolean(string="Enable Idle Time",default=True,
                                 help="Enable Idle Timer")
    idle_time = fields.Integer(string="Idle Time (In minutes)", default=5,
                               help="Set Idle Time For This User")

    # Since 19.0 SQL constraints are declared with models.Constraint;
    # _sql_constraints is ignored by the ORM. The attribute name is kept
    # identical so an upgrade from 18.0 reuses the existing DB constraint.
    _positive_idle_time = models.Constraint(
        'CHECK(idle_time >= 1)',
        'Idle Time should be a positive number.',
    )
