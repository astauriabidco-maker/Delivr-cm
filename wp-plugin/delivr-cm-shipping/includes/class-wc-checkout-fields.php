<?php
/**
 * RELAY237 Checkout Fields Customization
 *
 * Transforms address fields into neighborhood selectors
 * with cached API data for performance.
 *
 * @package DELIVR_CM_Shipping
 */

if (!defined('ABSPATH')) {
    exit;
}

/**
 * Class WC_Delivr_Checkout_Fields
 *
 * Handles checkout field modifications for neighborhood selection
 */
class WC_Delivr_Checkout_Fields
{

    /**
     * Cache key for neighborhoods
     */
    const CACHE_KEY = 'delivr_cm_neighborhoods';

    /**
     * Cache expiration (12 hours)
     */
    const CACHE_EXPIRATION = 43200;

    /**
     * Constructor
     */
    public function __construct()
    {
        add_filter('woocommerce_checkout_fields', array($this, 'customize_checkout_fields'));
        add_filter('woocommerce_billing_fields', array($this, 'customize_billing_fields'), 20);
        add_filter('woocommerce_shipping_fields', array($this, 'customize_shipping_fields'), 20);

        // AJAX handler for city change
        add_action('wp_ajax_delivr_get_neighborhoods', array($this, 'ajax_get_neighborhoods'));
        add_action('wp_ajax_nopriv_delivr_get_neighborhoods', array($this, 'ajax_get_neighborhoods'));

        // Enqueue scripts
        add_action('wp_enqueue_scripts', array($this, 'enqueue_scripts'));

        // Persist RELAY237 neighborhood UUIDs beside WooCommerce address data.
        add_action('woocommerce_checkout_create_order', array($this, 'save_order_neighborhood_ids'), 10, 2);

        // Clear cache on admin action
        add_action('wp_ajax_delivr_clear_neighborhoods_cache', array($this, 'clear_cache'));
    }

    /**
     * Customize checkout fields
     *
     * @param array $fields Checkout fields.
     * @return array Modified fields.
     */
    public function customize_checkout_fields($fields)
    {
        // Get city from session or default
        $current_city = WC()->session ? WC()->session->get('delivr_selected_city', 'Douala') : 'Douala';

        // Get neighborhoods for current city
        $neighborhoods = $this->get_neighborhoods($current_city);

        // Transform billing_address_2 into neighborhood select
        if (isset($fields['billing']['billing_address_2'])) {
            $fields['billing']['billing_address_2'] = array(
                'type' => 'select',
                'label' => __('Quartier', 'relay237-shipping'),
                'placeholder' => __('Sélectionnez votre quartier', 'relay237-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-neighborhood-select'),
                'options' => $neighborhoods,
                'priority' => 60,
            );
        }

        $fields['billing']['billing_delivr_cm_neighborhood_id'] = array(
            'type' => 'hidden',
            'required' => false,
            'class' => array('delivr-neighborhood-id-field'),
            'priority' => 61,
        );

        // Transform shipping_address_2 into neighborhood select
        if (isset($fields['shipping']['shipping_address_2'])) {
            $fields['shipping']['shipping_address_2'] = array(
                'type' => 'select',
                'label' => __('Quartier', 'relay237-shipping'),
                'placeholder' => __('Sélectionnez votre quartier', 'relay237-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-neighborhood-select'),
                'options' => $neighborhoods,
                'priority' => 60,
            );
        }

        $fields['shipping']['shipping_delivr_cm_neighborhood_id'] = array(
            'type' => 'hidden',
            'required' => false,
            'class' => array('delivr-neighborhood-id-field'),
            'priority' => 61,
        );

        // Modify city field to trigger neighborhood refresh
        if (isset($fields['billing']['billing_city'])) {
            $fields['billing']['billing_city'] = array(
                'type' => 'select',
                'label' => __('Ville', 'relay237-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-city-select'),
                'options' => array(
                    '' => __('Sélectionnez une ville', 'relay237-shipping'),
                    'Douala' => 'Douala',
                    'Yaounde' => 'Yaoundé',
                ),
                'priority' => 50,
            );
        }

        if (isset($fields['shipping']['shipping_city'])) {
            $fields['shipping']['shipping_city'] = array(
                'type' => 'select',
                'label' => __('Ville', 'relay237-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-city-select'),
                'options' => array(
                    '' => __('Sélectionnez une ville', 'relay237-shipping'),
                    'Douala' => 'Douala',
                    'Yaounde' => 'Yaoundé',
                ),
                'priority' => 50,
            );
        }

        return $fields;
    }

    /**
     * Customize billing fields (for My Account)
     *
     * @param array $fields Billing fields.
     * @return array Modified fields.
     */
    public function customize_billing_fields($fields)
    {
        return $fields;
    }

    /**
     * Customize shipping fields (for My Account)
     *
     * @param array $fields Shipping fields.
     * @return array Modified fields.
     */
    public function customize_shipping_fields($fields)
    {
        return $fields;
    }

    /**
     * Get neighborhoods from API with caching
     *
     * @param string $city City name.
     * @return array Neighborhoods as options array.
     */
    public function get_neighborhoods($city = 'Douala')
    {
        $data = $this->get_neighborhood_data($city);
        return $data['options'];
    }

    /**
     * Get neighborhood option labels and RELAY237 UUIDs from API with caching.
     *
     * @param string $city City name.
     * @return array Options and UUID lookup map.
     */
    public function get_neighborhood_data($city = 'Douala')
    {
        $cache_key = self::CACHE_KEY . '_' . sanitize_key($city);

        // Try cache first
        $cached = get_transient($cache_key);
        if (false !== $cached) {
            if (isset($cached['options'], $cached['ids'])) {
                return $cached;
            }

            return array(
                'options' => $cached,
                'ids' => array(),
            );
        }

        // Get API settings
        $shipping_method = $this->get_shipping_method_settings();
        $api_url = isset($shipping_method['api_url']) ? $shipping_method['api_url'] : 'http://localhost:8000';

        // Fetch from API
        $url = trailingslashit($api_url) . 'api/neighborhoods/';

        $args = array(
            'method' => 'GET',
            'timeout' => 10,
            'headers' => array(
                'Content-Type' => 'application/json',
            ),
        );

        // Add city filter
        $url = add_query_arg('city', $city, $url);

        $response = wp_remote_get($url, $args);

        if (is_wp_error($response)) {
            // Return fallback neighborhoods
            return array(
                'options' => $this->get_fallback_neighborhoods($city),
                'ids' => array(),
            );
        }

        $status_code = wp_remote_retrieve_response_code($response);

        if ($status_code !== 200) {
            return array(
                'options' => $this->get_fallback_neighborhoods($city),
                'ids' => array(),
            );
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        // Build options array
        $options = array(
            '' => __('Sélectionnez votre quartier', 'relay237-shipping'),
        );
        $ids = array();

        if (isset($data['results']) && is_array($data['results'])) {
            foreach ($data['results'] as $neighborhood) {
                $name = $neighborhood['name'];
                $options[$name] = $name;
                if (isset($neighborhood['id'])) {
                    $ids[$name] = $neighborhood['id'];
                }
            }
        } elseif (is_array($data)) {
            foreach ($data as $neighborhood) {
                if (isset($neighborhood['name'])) {
                    $name = $neighborhood['name'];
                    $options[$name] = $name;
                    if (isset($neighborhood['id'])) {
                        $ids[$name] = $neighborhood['id'];
                    }
                }
            }
        }

        $result = array(
            'options' => $options,
            'ids' => $ids,
        );

        // Cache the result
        set_transient($cache_key, $result, self::CACHE_EXPIRATION);

        return $result;
    }

    /**
     * Get fallback neighborhoods when API is unavailable
     *
     * @param string $city City name.
     * @return array Fallback neighborhoods.
     */
    private function get_fallback_neighborhoods($city)
    {
        $neighborhoods = array(
            '' => __('Sélectionnez votre quartier', 'relay237-shipping'),
        );

        if (strtolower($city) === 'douala') {
            $quartiers = array(
                'Akwa',
                'Bonanjo',
                'Bonapriso',
                'Deido',
                'Bali',
                'New Bell',
                'Bessengue',
                'Ndokoti',
                'Makepe',
                'Kotto',
                'Bonamoussadi',
                'Logpom',
                'Logbessou',
                'Yassa',
                'PK8',
                'PK10',
                'PK12',
                'PK14',
                'Nyalla',
                'Bepanda',
            );
        } elseif (strtolower($city) === 'yaounde' || strtolower($city) === 'yaoundé') {
            $quartiers = array(
                'Bastos',
                'Nlongkak',
                'Mvan',
                'Essos',
                'Mimboman',
                'Mvog-Mbi',
                'Briqueterie',
                'Mokolo',
                'Nkoldongo',
                'Emana',
                'Simbock',
                'Biyem-Assi',
                'Mendong',
                'Messa',
                'Nsam',
                'Ekounou',
                'Nkolbisson',
                'Olembe',
                'Ahala',
                'Nkomo',
            );
        } else {
            $quartiers = array('Centre-ville', 'Autre');
        }

        foreach ($quartiers as $q) {
            $neighborhoods[$q] = $q;
        }

        return $neighborhoods;
    }

    /**
     * Get shipping method settings
     *
     * @return array Settings.
     */
    private function get_shipping_method_settings()
    {
        if (WC()->session) {
            $chosen_methods = WC()->session->get('chosen_shipping_methods', array());

            foreach ($chosen_methods as $chosen_method) {
                if (strpos($chosen_method, 'delivr_cm:') !== 0) {
                    continue;
                }

                $instance_id = absint(substr($chosen_method, strlen('delivr_cm:')));
                $settings = get_option('woocommerce_delivr_cm_' . $instance_id . '_settings', array());

                if (is_array($settings) && !empty($settings)) {
                    return $settings;
                }
            }
        }

        $shipping_methods = WC()->shipping()->get_shipping_methods();

        if (isset($shipping_methods['delivr_cm'])) {
            return $shipping_methods['delivr_cm']->settings;
        }

        if (class_exists('WC_Shipping_Zones')) {
            $zones = WC_Shipping_Zones::get_zones();
            $zones[] = array('zone_id' => 0);

            foreach ($zones as $zone_data) {
                $zone = WC_Shipping_Zones::get_zone($zone_data['zone_id']);

                foreach ($zone->get_shipping_methods(true) as $method) {
                    if ($method->id === 'delivr_cm' && is_array($method->instance_settings)) {
                        return $method->instance_settings;
                    }
                }
            }
        }

        return array();
    }

    /**
     * AJAX handler for getting neighborhoods by city
     */
    public function ajax_get_neighborhoods()
    {
        check_ajax_referer('delivr_cm_nonce', 'nonce');

        $city = isset($_POST['city']) ? sanitize_text_field(wp_unslash($_POST['city'])) : 'Douala';

        // Save to session
        if (WC()->session) {
            WC()->session->set('delivr_selected_city', $city);
        }

        $data = $this->get_neighborhood_data($city);

        wp_send_json_success($data);
    }

    /**
     * Enqueue frontend scripts
     */
    public function enqueue_scripts()
    {
        if (!is_checkout()) {
            return;
        }

        wp_enqueue_script(
            'relay237-checkout',
            DELIVR_CM_PLUGIN_URL . 'assets/js/checkout.js',
            array('jquery', 'wc-checkout'),
            DELIVR_CM_VERSION,
            true
        );

        $neighborhood_data = $this->get_neighborhood_data(WC()->session ? WC()->session->get('delivr_selected_city', 'Douala') : 'Douala');

        wp_localize_script(
            'relay237-checkout',
            'delivr_cm_params',
            array(
                'ajax_url' => admin_url('admin-ajax.php'),
                'nonce' => wp_create_nonce('delivr_cm_nonce'),
                'neighborhood_ids' => $neighborhood_data['ids'],
            )
        );

        wp_enqueue_style(
            'relay237-checkout',
            DELIVR_CM_PLUGIN_URL . 'assets/css/checkout.css',
            array(),
            DELIVR_CM_VERSION
        );
    }

    /**
     * Clear neighborhoods cache
     */
    public function clear_cache()
    {
        check_ajax_referer('delivr_cm_nonce', 'nonce');

        if (!current_user_can('manage_options')) {
            wp_send_json_error('Unauthorized');
        }

        delete_transient(self::CACHE_KEY . '_douala');
        delete_transient(self::CACHE_KEY . '_yaounde');

        wp_send_json_success('Cache cleared');
    }

    /**
     * Save RELAY237 neighborhood UUIDs on the order.
     *
     * @param WC_Order $order Posted order.
     * @param array    $data  Checkout data.
     */
    public function save_order_neighborhood_ids($order, $data)
    {
        $billing_id = isset($_POST['billing_delivr_cm_neighborhood_id']) ? sanitize_text_field(wp_unslash($_POST['billing_delivr_cm_neighborhood_id'])) : '';
        $shipping_id = isset($_POST['shipping_delivr_cm_neighborhood_id']) ? sanitize_text_field(wp_unslash($_POST['shipping_delivr_cm_neighborhood_id'])) : '';

        if (!empty($billing_id)) {
            $order->update_meta_data('_billing_delivr_cm_neighborhood_id', $billing_id);
        }

        if (!empty($shipping_id)) {
            $order->update_meta_data('_shipping_delivr_cm_neighborhood_id', $shipping_id);
        }
    }
}

// Initialize
new WC_Delivr_Checkout_Fields();
