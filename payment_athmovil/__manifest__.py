# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

{
    "name": "ATH Móvil Payment Provider",
    "version": "17.0.3.0.0",
    "category": "Accounting/Payment Providers",
    "summary": "Accept ATH Móvil payments in Odoo — Puerto Rico's #1 mobile payment",
    "author": "Spark Workforce LLC",
    "website": "https://www.sparkworkforcellc.com",
    "support": "jvelez@sparkworkforcellc.com",
    "license": "LGPL-3",
    "price": 0,
    "currency": "USD",
    "description": """
ATH Móvil Payment Provider for Odoo
=====================================

Integrate ATH Móvil Business as a native payment method in Odoo 17, 18, and 19.

**Features:**
- Seamless checkout with ATH Móvil payment modal
- Webhook + polling fallback for payment confirmation
- Server-side payment verification (anti-fraud)
- ATH-branded success/failure/expired status pages
- QR code payments for invoices and in-person scenarios
- Full and partial refund support with status tracking
- Payment analytics dashboard (pivot, graph, list views)
- Smart button on invoices linking to ATH Móvil transactions
- Daily auto-reconciliation with ATH Business reports
- Merchant onboarding guide with Test Connection button
- Multi-company support, bilingual (English/Spanish)
- CSP headers, CSRF protection, session binding
    """,
    "depends": [
        "payment",
        "website",
        "account",
        "mail",
        "point_of_sale",
    ],
    "data": [
        "data/payment_provider_data.xml",
        "data/mail_template_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_athmovil_templates.xml",
        "views/payment_status_templates.xml",
        "views/payment_transaction_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "payment_athmovil/static/src/js/athmovil_checkout.js",
        ],
        "point_of_sale._assets_pos": [
            "payment_athmovil/static/src/js/pos_payment_athmovil.js",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
