<?php
/**
 * DELIVR-CM Shipping Method for WooCommerce
 *
 * @package DELIVR_CM_Shipping
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * WC_Delivr_Shipping_Method class
 *
 * Handles shipping rate calculation and order dispatch to DELIVR-CM API
 */
class WC_Delivr_Shipping_Method extends WC_Shipping_Method
{

    /**
     * API URL
     *
     * @var string
     */
    private $api_url;

    /**
     * API Key
     *
     * @var string
     */
    private $api_key;

    /**
     * Fallback price when API fails
     *
     * @var float
     */
    private $fallback_price;

    /**
     * Logger instance
     *
     * @var WC_Logger
     */
    private $logger;

    /**
     * Constructor
     *
     * @param int $instance_id Instance ID.
     */
    public function __construct($instance_id = 0)
    {
        $this->id = 'delivr_cm';
        $this->instance_id = absint($instance_id);
        $this->method_title = __('DELIVR-CM Express', 'delivr-cm-shipping');
        $this->method_description = __('Livraison express géolocalisée par moto. Tarifs calculés en temps réel selon le quartier du client.', 'delivr-cm-shipping');
        $this->supports = array(
            'shipping-zones',
            'instance-settings',
            'instance-settings-modal',
        );

        $this->init();

        // Load settings
        $this->api_url = $this->get_option('api_url', 'http://localhost:8000');
        $this->api_key = $this->get_option('api_key', '');
        $this->fallback_price = floatval($this->get_option('fallback_price', 1500));
        $this->title = $this->get_option('title', __('Livraison Express (DELIVR-CM)', 'delivr-cm-shipping'));

        // Initialize logger
        $this->logger = wc_get_logger();
    }

    /**
     * Initialize form fields and settings
     */
    private function init()
    {
        $this->init_form_fields();
        $this->init_settings();

        // Save settings hook
        add_action('woocommerce_update_options_shipping_' . $this->id, array($this, 'process_admin_options'));
    }

    /**
     * Define settings fields
     */
    public function init_form_fields()
    {
        $this->instance_form_fields = array(
            'title' => array(
                'title' => __('Titre', 'delivr-cm-shipping'),
                'type' => 'text',
                'description' => __('Titre affiché au client lors du checkout.', 'delivr-cm-shipping'),
                'default' => __('Livraison Express (DELIVR-CM)', 'delivr-cm-shipping'),
                'desc_tip' => true,
            ),
            'api_url' => array(
                'title' => __('URL de l\'API', 'delivr-cm-shipping'),
                'type' => 'url',
                'description' => __('URL de base de l\'API DELIVR-CM (ex: https://api.delivr.cm)', 'delivr-cm-shipping'),
                'default' => 'http://localhost:8000',
                'desc_tip' => true,
            ),
            'api_key' => array(
                'title' => __('Clé API', 'delivr-cm-shipping'),
                'type' => 'password',
                'description' => __('Token JWT pour authentification API. Obtenez-le depuis votre dashboard DELIVR-CM.', 'delivr-cm-shipping'),
                'default' => '',
                'desc_tip' => true,
            ),
            'fallback_price' => array(
                'title' => __('Prix de secours (XAF)', 'delivr-cm-shipping'),
                'type' => 'number',
                'description' => __('Prix utilisé si l\'API est indisponible.', 'delivr-cm-shipping'),
                'default' => 1500,
                'desc_tip' => true,
                'custom_attributes' => array(
                    'min' => 0,
                    'step' => 100,
                ),
            ),
            'shop_latitude' => array(
                'title' => __('Latitude de la boutique', 'delivr-cm-shipping'),
                'type' => 'text',
                'description' => __('Coordonnée GPS latitude de votre boutique (ex: 4.0511)', 'delivr-cm-shipping'),
                'default' => '4.0511',
                'desc_tip' => true,
            ),
            'shop_longitude' => array(
                'title' => __('Longitude de la boutique', 'delivr-cm-shipping'),
                'type' => 'text',
                'description' => __('Coordonnée GPS longitude de votre boutique (ex: 9.7679)', 'delivr-cm-shipping'),
                'default' => '9.7679',
                'desc_tip' => true,
            ),
        );
    }

    /**
     * Calculate shipping cost
     *
     * @param array $package Package data.
     */
    public function calculate_shipping($package = array())
    {
        // Get destination info
        $city = isset($package['destination']['city']) ? sanitize_text_field($package['destination']['city']) : '';
        $neighborhood = isset($package['destination']['address']) ? sanitize_text_field($package['destination']['address']) : '';
        $address_2 = isset($package['destination']['address_2']) ? sanitize_text_field($package['destination']['address_2']) : '';

        // Use address_2 as neighborhood if provided (common pattern)
        if (!empty($address_2)) {
            $neighborhood = $address_2;
        }

        // Try to get price from API
        $price = $this->get_quote_from_api($city, $neighborhood);

        // Add shipping rate
        $this->add_rate(
            array(
                'id' => $this->get_rate_id(),
                'label' => $this->title,
                'cost' => $price,
                'calc_tax' => 'per_order',
                'meta_data' => array(
                    'city' => $city,
                    'neighborhood' => $neighborhood,
                ),
            )
        );
    }

    /**
     * Get quote from DELIVR-CM API
     *
     * @param string $city City name.
     * @param string $neighborhood Neighborhood name.
     * @return float Shipping price.
     */
    private function get_quote_from_api($city, $neighborhood)
    {
        // Prepare request - use public endpoint (no auth required)
        $url = trailingslashit($this->api_url) . 'api/public/quote/';

        // Get shop coordinates from settings
        $shop_lat = floatval($this->get_option('shop_latitude', '4.0511'));
        $shop_lng = floatval($this->get_option('shop_longitude', '9.7679'));

        $body = array(
            'city' => $city,
            'neighborhood' => $neighborhood,
            'shop_lat' => $shop_lat,
            'shop_lng' => $shop_lng,
        );

        $args = array(
            'method' => 'POST',
            'timeout' => 10,
            'headers' => array(
                'Content-Type' => 'application/json',
            ),
            'body' => wp_json_encode($body),
        );

        // Make API request
        $response = wp_remote_post($url, $args);

        // Check for errors
        if (is_wp_error($response)) {
            $this->log('Erreur API Quote: ' . $response->get_error_message(), 'error');
            return $this->fallback_price;
        }

        $status_code = wp_remote_retrieve_response_code($response);
        $body = wp_remote_retrieve_body($response);

        if ($status_code !== 200) {
            $this->log("API Quote retourne {$status_code}: {$body}", 'error');
            return $this->fallback_price;
        }

        // Parse response
        $data = json_decode($body, true);

        if (isset($data['estimated_price'])) {
            $price = floatval($data['estimated_price']);
            $this->log("Prix obtenu: {$price} XAF pour {$neighborhood}, {$city}", 'info');
            return $price;
        }

        // Fallback if response format unexpected
        $this->log('Format de réponse API inattendu: ' . $body, 'warning');
        return $this->fallback_price;
    }

    /**
     * Trigger delivery order creation on payment complete
     *
     * @param int $order_id WooCommerce order ID.
     */
    public function trigger_delivery_order($order_id)
    {
        $order = wc_get_order($order_id);

        if (!$order) {
            $this->log("Commande {$order_id} introuvable.", 'error');
            return;
        }

        // Check if already sent
        if ($order->get_meta('_delivr_cm_order_sent') === 'yes') {
            $this->log("Commande {$order_id} déjà envoyée à DELIVR-CM.", 'info');
            return;
        }

        // Skip if no API key
        if (empty($this->api_key)) {
            $this->log('API Key non configurée, commande non envoyée.', 'warning');
            return;
        }

        // Prepare order data
        $billing_phone = $order->get_billing_phone();
        $shipping = $order->get_address('shipping');

        // Build items description
        $items = array();
        foreach ($order->get_items() as $item) {
            $items[] = $item->get_quantity() . 'x ' . $item->get_name();
        }
        $items_description = implode(', ', $items);

        // Get neighborhood from shipping address
        $neighborhood = !empty($shipping['address_2']) ? $shipping['address_2'] : $shipping['address_1'];
        $city = $shipping['city'];

        // Prepare API payload
        $payload = array(
            'external_order_id' => (string) $order_id,
            'customer_phone' => $this->normalize_phone($billing_phone),
            'customer_name' => $order->get_formatted_billing_full_name(),
            'neighborhood' => $neighborhood,
            'city' => $city,
            'items_description' => $items_description,
            'order_total' => $order->get_total(),
            'shipping_total' => $order->get_shipping_total(),
        );

        // Make API request
        $url = trailingslashit($this->api_url) . 'api/orders/';

        $args = array(
            'method' => 'POST',
            'timeout' => 15,
            'headers' => array(
                'Content-Type' => 'application/json',
                'Authorization' => 'Bearer ' . $this->api_key,
            ),
            'body' => wp_json_encode($payload),
        );

        $response = wp_remote_post($url, $args);

        if (is_wp_error($response)) {
            $this->log("Erreur envoi commande {$order_id}: " . $response->get_error_message(), 'error');
            $order->add_order_note('❌ DELIVR-CM: Erreur - ' . $response->get_error_message());
            return;
        }

        $status_code = wp_remote_retrieve_response_code($response);
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        if ($status_code === 201 || $status_code === 200) {
            // Success
            $delivery_id = isset($data['delivery_id']) ? $data['delivery_id'] : 'N/A';

            $order->update_meta_data('_delivr_cm_order_sent', 'yes');
            $order->update_meta_data('_delivr_cm_delivery_id', $delivery_id);
            $order->save();

            $order->add_order_note(
                sprintf(
                    '✅ DELIVR-CM: Livraison créée #%s. Le client sera contacté sur WhatsApp.',
                    substr($delivery_id, 0, 8)
                )
            );

            $this->log("Commande {$order_id} envoyée avec succès. Delivery ID: {$delivery_id}", 'info');
        } elseif ($status_code === 402) {
            // Insufficient funds
            $error_msg = isset($data['message']) ? $data['message'] : 'Solde insuffisant';
            $order->add_order_note('⚠️ DELIVR-CM: ' . $error_msg);
            $this->log("Commande {$order_id}: Solde insuffisant - {$error_msg}", 'error');
        } else {
            // Other error
            $error_msg = isset($data['error']) ? $data['error'] : $body;
            $order->add_order_note('❌ DELIVR-CM: Erreur ' . $status_code . ' - ' . $error_msg);
            $this->log("Commande {$order_id}: Erreur {$status_code} - {$error_msg}", 'error');
        }
    }

    /**
     * Normalize phone number to Cameroon format
     *
     * @param string $phone Phone number.
     * @return string Normalized phone number.
     */
    private function normalize_phone($phone)
    {
        // Remove spaces, dashes, etc.
        $phone = preg_replace('/[^0-9+]/', '', $phone);

        // Add country code if missing
        if (!preg_match('/^\+/', $phone)) {
            if (preg_match('/^237/', $phone)) {
                $phone = '+' . $phone;
            } else {
                $phone = '+237' . $phone;
            }
        }

        return $phone;
    }

    /**
     * Log message
     *
     * @param string $message Log message.
     * @param string $level   Log level (info, warning, error).
     */
    private function log($message, $level = 'info')
    {
        if ($this->logger) {
            $this->logger->log($level, '[DELIVR-CM] ' . $message, array('source' => 'delivr-cm-shipping'));
        }
    }
}
