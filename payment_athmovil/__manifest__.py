# -*- coding: utf-8 -*-
# Part of payment_athmovil. See LICENSE file for full copyright and licensing details.
#
# ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
# This module is an independent integration and is not affiliated with
# or endorsed by EVERTEC.

{
    "name": "ATH Móvil Payment Provider",
    "version": "17.0.1.0.0",
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

ATH Móvil is Puerto Rico's dominant mobile payment network, operated by EVERTEC Group, LLC.

**Features:**
- Accept ATH Móvil payments in eCommerce, Invoicing, Sales, and Customer Portal
- Webhook + polling fallback for payment confirmation
- Multi-company support (each company uses its own ATH Business credentials)
- Full and partial refund support (partial subject to ATH Móvil API capability)
- Automatic expiry of abandoned pending transactions (cron every 15 minutes)
- Sandbox mode using publicToken = "dummy"
- Bilingual interface (English and Spanish)

**Legal Notice:**
ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
This module is an independent integration and is not affiliated with
or endorsed by EVERTEC.

Each merchant must have their own active ATH Business account.
You must accept ATH Business Terms at https://ath.business/terminos
before using this provider.

ATH Business support: 787-773-5466
    """,
    "depends": [
        "payment",
        "website",
        # Note: 'sale' is NOT listed here intentionally — it is an optional
        # integration. _athmovil_build_items_list() uses getattr() to safely
        # access sale_order_ids only when the sale module is installed.
        # Adding 'sale' to depends would prevent installation on Odoo instances
        # that only have Accounting (no Sales app).
    ],
    "data": [
        # Load order matters: data first, then views
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_athmovil_templates.xml",
    ],
    "assets": {
        # The checkout JS uses _t() from @web/core/l10n/translation for
        # translatable strings. It must be registered in the frontend bundle
        # so Odoo's translation system can process it.
        # The QWeb template also loads it via <script type="module"> —
        # remove that tag from the template to avoid double loading.
        "web.assets_frontend": [
            "payment_athmovil/static/src/js/athmovil_checkout.js",
        ],
    },
    "images": [
        # icon.png: ATH Móvil logo is a trademark of EVERTEC Group, LLC.
        # A placeholder icon must be added manually before publishing to
        # Odoo Apps Store. The file must be 64x64 PNG at this path.
        # Do NOT bundle the ATH Móvil logo without written permission from EVERTEC.
        "static/description/icon.png",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
