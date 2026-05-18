<?php
/**
 * RELAY237 incoming webhook receiver for WooCommerce.
 *
 * @package DELIVR_CM_Shipping
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Receives signed delivery status webhooks from RELAY237.
 */
class WC_Delivr_Webhook_Receiver
{
    /**
     * Register REST routes.
     */
    public static function register_routes()
    {
        register_rest_route(
            'relay237/v1',
            '/webhook',
            array(
                'methods' => 'POST',
                'callback' => array(__CLASS__, 'handle_webhook'),
                'permission_callback' => '__return_true',
            )
        );
    }

    /**
     * Handle a RELAY237 webhook request.
     *
     * @param WP_REST_Request $request Incoming request.
     * @return WP_REST_Response
     */
    public static function handle_webhook($request)
    {
        $body = $request->get_body();
        $payload = json_decode($body, true);

        if (!is_array($payload)) {
            return new WP_REST_Response(array('error' => 'invalid_json'), 400);
        }

        $secrets = self::get_webhook_secrets();
        if (empty($secrets)) {
            self::log('Secret webhook non configuré.', 'error');
            return new WP_REST_Response(array('error' => 'webhook_secret_missing'), 500);
        }

        if (!self::is_valid_signature($body, $request->get_header('x-webhook-signature'), $secrets)) {
            self::log('Signature webhook invalide.', 'warning');
            return new WP_REST_Response(array('error' => 'invalid_signature'), 401);
        }

        $order_data = isset($payload['data']['order']) && is_array($payload['data']['order']) ? $payload['data']['order'] : array();
        $order = self::find_order($order_data);

        if (!$order) {
            self::log('Commande WooCommerce introuvable pour webhook RELAY237.', 'warning');
            return new WP_REST_Response(array('error' => 'order_not_found'), 404);
        }

        $status = isset($order_data['status']) ? sanitize_text_field($order_data['status']) : '';
        $event = isset($payload['event']) ? sanitize_text_field($payload['event']) : 'delivery.updated';
        $delivery_id = isset($order_data['id']) ? sanitize_text_field($order_data['id']) : '';

        $order->update_meta_data('_delivr_cm_delivery_status', $status);
        $order->update_meta_data('_delivr_cm_last_webhook_event', $event);
        $order->update_meta_data('_delivr_cm_last_webhook_at', current_time('mysql', true));

        self::sync_order_status($order, $status);
        self::add_status_note($order, $status, $delivery_id);
        $order->save();

        return new WP_REST_Response(
            array(
                'success' => true,
                'order_id' => $order->get_id(),
            ),
            200
        );
    }

    /**
     * Verify webhook HMAC signature.
     *
     * @param string $body      Raw request body.
     * @param string $signature Signature header.
     * @param array  $secrets   Shared webhook secrets.
     * @return bool
     */
    private static function is_valid_signature($body, $signature, $secrets)
    {
        if (empty($signature)) {
            return false;
        }

        foreach ($secrets as $secret) {
            $expected = 'sha256=' . hash_hmac('sha256', $body, $secret);
            if (hash_equals($expected, trim($signature))) {
                return true;
            }
        }

        return false;
    }

    /**
     * Find the WooCommerce order referenced by the RELAY237 payload.
     *
     * @param array $order_data Delivery payload order data.
     * @return WC_Order|null
     */
    private static function find_order($order_data)
    {
        $external_order_id = isset($order_data['external_order_id']) ? absint($order_data['external_order_id']) : 0;
        if ($external_order_id) {
            $order = wc_get_order($external_order_id);
            if ($order) {
                return $order;
            }
        }

        $delivery_id = isset($order_data['id']) ? sanitize_text_field($order_data['id']) : '';
        if (empty($delivery_id)) {
            return null;
        }

        $orders = wc_get_orders(
            array(
                'limit' => 1,
                'meta_key' => '_delivr_cm_delivery_id',
                'meta_value' => $delivery_id,
                'return' => 'objects',
            )
        );

        return !empty($orders) ? $orders[0] : null;
    }

    /**
     * Sync WooCommerce order status from RELAY237 status.
     *
     * @param WC_Order $order  WooCommerce order.
     * @param string   $status RELAY237 delivery status.
     */
    private static function sync_order_status($order, $status)
    {
        if ($status === 'COMPLETED' && !$order->has_status('completed')) {
            $order->update_status('completed', __('RELAY237: livraison complétée.', 'relay237-shipping'), false);
            return;
        }

        if ($status === 'CANCELLED' && !$order->has_status('cancelled')) {
            $order->update_status('cancelled', __('RELAY237: livraison annulée.', 'relay237-shipping'), false);
            return;
        }

        if ($status === 'FAILED' && !$order->has_status('failed')) {
            $order->update_status('failed', __('RELAY237: livraison échouée.', 'relay237-shipping'), false);
        }
    }

    /**
     * Add an order note for the delivery status update.
     *
     * @param WC_Order $order       WooCommerce order.
     * @param string   $status      RELAY237 delivery status.
     * @param string   $delivery_id RELAY237 delivery ID.
     */
    private static function add_status_note($order, $status, $delivery_id)
    {
        $label = self::status_label($status);
        $suffix = $delivery_id ? ' #' . substr($delivery_id, 0, 8) : '';

        $order->add_order_note(
            sprintf(
                /* translators: 1: delivery status label, 2: short delivery id */
                __('RELAY237: statut livraison %1$s%2$s.', 'relay237-shipping'),
                $label,
                $suffix
            )
        );
    }

    /**
     * Human label for delivery status.
     *
     * @param string $status Delivery status.
     * @return string
     */
    private static function status_label($status)
    {
        $labels = array(
            'PENDING' => 'en attente',
            'ASSIGNED' => 'assignée',
            'PICKED_UP' => 'récupérée',
            'IN_TRANSIT' => 'en transit',
            'COMPLETED' => 'complétée',
            'CANCELLED' => 'annulée',
            'FAILED' => 'échouée',
        );

        return isset($labels[$status]) ? $labels[$status] : $status;
    }

    /**
     * Get webhook secrets from RELAY237 shipping method settings.
     *
     * @return array
     */
    private static function get_webhook_secrets()
    {
        $secrets = array();
        $legacy_settings = get_option('woocommerce_delivr_cm_settings', array());
        if (is_array($legacy_settings) && !empty($legacy_settings['webhook_secret'])) {
            $secrets[] = $legacy_settings['webhook_secret'];
        }

        if (class_exists('WC_Shipping_Zones')) {
            $zones = WC_Shipping_Zones::get_zones();
            foreach ($zones as $zone_data) {
                $zone = WC_Shipping_Zones::get_zone(absint($zone_data['zone_id']));
                if (!$zone) {
                    continue;
                }

                foreach ($zone->get_shipping_methods() as $method) {
                    if ($method->id === 'delivr_cm') {
                        $secret = $method->get_option('webhook_secret', '');
                        if (!empty($secret)) {
                            $secrets[] = $secret;
                        }
                    }
                }
            }

            $default_zone = new WC_Shipping_Zone(0);
            foreach ($default_zone->get_shipping_methods() as $method) {
                if ($method->id === 'delivr_cm') {
                    $secret = $method->get_option('webhook_secret', '');
                    if (!empty($secret)) {
                        $secrets[] = $secret;
                    }
                }
            }
        }

        return array_unique(array_map('strval', $secrets));
    }

    /**
     * Log receiver messages.
     *
     * @param string $message Log message.
     * @param string $level   Log level.
     */
    private static function log($message, $level = 'info')
    {
        if (function_exists('wc_get_logger')) {
            wc_get_logger()->log($level, '[RELAY237 Webhook] ' . $message, array('source' => 'relay237-shipping'));
        }
    }
}
