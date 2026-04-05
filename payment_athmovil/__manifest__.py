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
    ],
    "data": [
        # Load order matters: data first, then views
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_athmovil_templates.xml",
    ],
    "assets": {
        # The checkout JS is loaded directly by the QWeb template via
        # <script type="module"> — do NOT also register it in assets bundles
        # as that would cause it to load twice on the payment page.
        # This assets block is intentionally empty but kept for future use.
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
