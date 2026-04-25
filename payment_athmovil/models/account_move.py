# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    athmovil_tx_count = fields.Integer(
        string="ATH Móvil Transactions",
        compute="_compute_athmovil_tx_count",
    )
    athmovil_payment_link = fields.Char(
        string="ATH Móvil Payment Link",
        copy=False,
        readonly=True,
    )

    def _compute_athmovil_tx_count(self):
        for move in self:
            move.athmovil_tx_count = self.env["payment.transaction"].search_count(
                [
                    ("invoice_ids", "in", move.ids),
                    ("provider_code", "=", "athmovil"),
                ]
            )

    def action_view_athmovil_transactions(self):
        self.ensure_one()
        txs = self.env["payment.transaction"].search(
            [("invoice_ids", "in", self.ids), ("provider_code", "=", "athmovil")]
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "payment_athmovil.action_athmovil_payment_analytics"
        )
        if len(txs) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = txs.id
        else:
            action["domain"] = [("id", "in", txs.ids)]
        return action

    def action_athmovil_create_payment_link(self):
        """Create an ATH Móvil payment link for this invoice.

        Creates a payment.transaction, generates the ticket via ATH API,
        and stores the shareable payment link + QR URL on the invoice.
        """
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self.state != "posted":
            raise UserError(_("Invoice must be posted to create a payment link."))
        if self.payment_state == "paid":
            raise UserError(_("Invoice is already paid."))

        provider = self.env["payment.provider"].search(
            [("code", "=", "athmovil"), ("state", "in", ("enabled", "test"))],
            limit=1,
        )
        if not provider:
            raise UserError(
                _("No active ATH Móvil payment provider found. "
                  "Enable it in Settings → Payment Providers.")
            )

        usd = self.env.ref("base.USD")
        tx = self.env["payment.transaction"].create({
            "provider_id": provider.id,
            "amount": self.amount_residual,
            "currency_id": usd.id,
            "reference": self.env["payment.transaction"]._compute_reference(
                provider_code="athmovil",
            ),
            "partner_id": self.partner_id.id,
            "invoice_ids": [(4, self.id)],
        })

        # Create the ATH Móvil ticket
        tx._athmovil_create_payment_ticket()

        base_url = provider.get_base_url()
        self.athmovil_payment_link = (
            "%s/payment/athmovil/status?ecommerce_id=%s"
            % (base_url, tx.athmovil_ecommerce_id)
        )

        qr_url = "%s/payment/athmovil/qr/%s" % (
            base_url, tx.athmovil_ecommerce_id
        )

        self.message_post(
            body=_(
                "🔗 ATH Móvil payment link created:<br/>"
                "<a href='%(link)s'>%(link)s</a><br/>"
                "<img src='%(qr)s' width='200' alt='QR Code'/><br/>"
                "Amount: $%(amount).2f · Expires in 10 minutes."
            ) % {
                "link": self.athmovil_payment_link,
                "qr": qr_url,
                "amount": self.amount_residual,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Payment Link Created"),
                "message": _(
                    "Link copied to the chatter. Share it via WhatsApp, "
                    "email, or SMS. The QR code is also available."
                ),
                "type": "success",
                "sticky": False,
            },
        }
