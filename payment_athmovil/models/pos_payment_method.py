# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    athmovil_provider_id = fields.Many2one(
        "payment.provider",
        string="ATH Móvil Provider",
        domain="[('code', '=', 'athmovil'), ('state', 'in', ('enabled', 'test'))]",
        help="Link this POS payment method to an ATH Móvil provider for QR payments.",
    )

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [
            ("athmovil", "ATH Móvil"),
        ]

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ["athmovil_provider_id"]
        return fields
