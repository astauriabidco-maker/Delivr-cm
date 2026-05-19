<?php
/**
 * Plugin Name: RELAY237 Shipping
 * Plugin URI: https://relay237.com
 * Description: Intégration de livraison express géolocalisée par moto pour WooCommerce. Connecte votre boutique à l'API RELAY237.
 * Version: 1.0.0
 * Author: RELAY237
 * Author URI: https://relay237.com
 * Text Domain: relay237-shipping
 * Domain Path: /languages
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * WC requires at least: 5.0
 * WC tested up to: 8.0
 *
 * @package DELIVR_CM_Shipping
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Define plugin constants
define('DELIVR_CM_VERSION', '1.0.1');
define('DELIVR_CM_PLUGIN_FILE', __FILE__);
define('DELIVR_CM_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('DELIVR_CM_PLUGIN_URL', plugin_dir_url(__FILE__));

/**
 * Check if WooCommerce is active
 */
function delivr_cm_check_woocommerce()
{
    if (!class_exists('WooCommerce')) {
        add_action('admin_notices', 'delivr_cm_woocommerce_missing_notice');
        return false;
    }
    return true;
}

/**
 * Admin notice for missing WooCommerce
 */
function delivr_cm_woocommerce_missing_notice()
{
    ?>
    <div class="notice notice-error">
        <p>
            <strong>RELAY237 Shipping</strong> nécessite WooCommerce pour fonctionner.
            Veuillez <a
                href="<?php echo esc_url(admin_url('plugin-install.php?s=woocommerce&tab=search&type=term')); ?>">installer
                WooCommerce</a>.
        </p>
    </div>
    <?php
}

/**
 * Initialize the shipping method
 */
function delivr_cm_shipping_init()
{
    if (!delivr_cm_check_woocommerce()) {
        return;
    }

    // Include shipping method class
    require_once DELIVR_CM_PLUGIN_DIR . 'includes/class-wc-shipping-delivr.php';

    // Include incoming webhook receiver
    require_once DELIVR_CM_PLUGIN_DIR . 'includes/class-wc-webhook-receiver.php';
}
add_action('woocommerce_shipping_init', 'delivr_cm_shipping_init');

/**
 * Initialize checkout customizations early enough for admin-ajax.php handlers.
 */
function delivr_cm_checkout_fields_init()
{
    if (!delivr_cm_check_woocommerce()) {
        return;
    }

    require_once DELIVR_CM_PLUGIN_DIR . 'includes/class-wc-checkout-fields.php';
}
add_action('plugins_loaded', 'delivr_cm_checkout_fields_init', 20);

/**
 * Register incoming REST webhook endpoint.
 */
function delivr_cm_register_webhook_routes()
{
    if (!delivr_cm_check_woocommerce()) {
        return;
    }

    if (!class_exists('WC_Delivr_Webhook_Receiver')) {
        require_once DELIVR_CM_PLUGIN_DIR . 'includes/class-wc-webhook-receiver.php';
    }

    WC_Delivr_Webhook_Receiver::register_routes();
}
add_action('rest_api_init', 'delivr_cm_register_webhook_routes');

/**
 * Register the shipping method
 */
function delivr_cm_add_shipping_method($methods)
{
    $methods['delivr_cm'] = 'WC_Delivr_Shipping_Method';
    return $methods;
}
add_action('woocommerce_shipping_methods', 'delivr_cm_add_shipping_method');

/**
 * Add settings link on plugins page
 */
function delivr_cm_plugin_action_links($links)
{
    $settings_link = '<a href="' . admin_url('admin.php?page=wc-settings&tab=shipping&section=delivr_cm') . '">' . __('Paramètres', 'relay237-shipping') . '</a>';
    array_unshift($links, $settings_link);
    return $links;
}
add_filter('plugin_action_links_' . plugin_basename(__FILE__), 'delivr_cm_plugin_action_links');

/**
 * Declare HPOS compatibility
 */
add_action('before_woocommerce_init', function () {
    if (class_exists(\Automattic\WooCommerce\Utilities\FeaturesUtil::class)) {
        \Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility('custom_order_tables', __FILE__, true);
    }
});

/**
 * Check whether a WooCommerce order uses the RELAY237 shipping method.
 *
 * @param WC_Order|false $order WooCommerce order.
 * @return bool
 */
function delivr_cm_order_uses_shipping($order)
{
    if (!$order) {
        return false;
    }

    foreach ($order->get_shipping_methods() as $method) {
        if ($method->get_method_id() === 'delivr_cm') {
            return true;
        }
    }

    return false;
}

/**
 * Trigger delivery order on payment complete
 */
function delivr_cm_on_payment_complete($order_id)
{
    $order = wc_get_order($order_id);

    if (!delivr_cm_order_uses_shipping($order)) {
        return;
    }

    if (!class_exists('WC_Delivr_Shipping_Method')) {
        require_once DELIVR_CM_PLUGIN_DIR . 'includes/class-wc-shipping-delivr.php';
    }

    $shipping_method = new WC_Delivr_Shipping_Method();
    $shipping_method->trigger_delivery_order($order_id);
}
add_action('woocommerce_payment_complete', 'delivr_cm_on_payment_complete', 10, 1);

/**
 * Also trigger on order status change to processing (for COD, BACS, etc.)
 */
function delivr_cm_on_order_processing($order_id)
{
    $order = wc_get_order($order_id);

    if (!$order) {
        return;
    }

    // Check if we already processed this order
    if ($order->get_meta('_delivr_cm_order_sent') === 'yes') {
        return;
    }

    if (!delivr_cm_order_uses_shipping($order)) {
        return;
    }

    delivr_cm_on_payment_complete($order_id);
}
add_action('woocommerce_order_status_processing', 'delivr_cm_on_order_processing', 10, 1);
