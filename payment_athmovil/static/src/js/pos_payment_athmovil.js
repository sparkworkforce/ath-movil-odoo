/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { jsonrpc } from "@web/core/network/rpc";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";

const POLL_INTERVAL = 3000;
const POLL_TIMEOUT = 600000;

export class PaymentAthmovil extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this._pollTimer = null;
    }

    async send_payment_request(cid) {
        await super.send_payment_request(...arguments);
        const line = this.pos.get_order().selected_paymentline;
        const provider_id = line.payment_method.athmovil_provider_id?.[0];

        if (!provider_id) {
            line.set_payment_status("retry");
            return false;
        }

        try {
            const result = await jsonrpc("/pos/athmovil/create_ticket", {
                provider_id: provider_id,
                amount: line.amount,
                order_reference: this.pos.get_order().name,
            });

            if (result.error) {
                line.set_payment_status("retry");
                return false;
            }

            line.athmovil_ecommerce_id = result.ecommerce_id;
            line.athmovil_qr_url = result.qr_url;

            // Show QR on customer display if available
            if (this.pos.config.iface_customer_facing_display_via_proxy) {
                this.pos.send_current_order_to_customer_facing_display();
            }

            // Start polling for payment completion
            return await this._pollForPayment(line, provider_id);
        } catch (err) {
            line.set_payment_status("retry");
            return false;
        }
    }

    async _pollForPayment(line, provider_id) {
        const startTime = Date.now();

        return new Promise((resolve) => {
            const poll = async () => {
                if (Date.now() - startTime > POLL_TIMEOUT) {
                    line.set_payment_status("retry");
                    resolve(false);
                    return;
                }

                try {
                    const result = await jsonrpc("/pos/athmovil/check_payment", {
                        provider_id: provider_id,
                        ecommerce_id: line.athmovil_ecommerce_id,
                    });

                    if (result.status === "COMPLETED") {
                        line.set_payment_status("done");
                        line.transaction_id = line.athmovil_ecommerce_id;
                        resolve(true);
                        return;
                    }
                    if (result.status === "CANCEL") {
                        line.set_payment_status("retry");
                        resolve(false);
                        return;
                    }
                } catch (_) {
                    // Continue polling on network errors
                }

                this._pollTimer = setTimeout(poll, POLL_INTERVAL);
            };

            this._pollTimer = setTimeout(poll, POLL_INTERVAL);
        });
    }

    send_payment_cancel(order, cid) {
        super.send_payment_cancel(...arguments);
        if (this._pollTimer) {
            clearTimeout(this._pollTimer);
            this._pollTimer = null;
        }
        return true;
    }
}

register_payment_method("athmovil", PaymentAthmovil);
