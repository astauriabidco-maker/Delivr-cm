<?php
/**
 * DELIVR-CM Checkout Fields Customization
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
                'label' => __('Quartier', 'delivr-cm-shipping'),
                'placeholder' => __('Sélectionnez votre quartier', 'delivr-cm-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-neighborhood-select'),
                'options' => $neighborhoods,
                'priority' => 60,
            );
        }

        // Transform shipping_address_2 into neighborhood select
        if (isset($fields['shipping']['shipping_address_2'])) {
            $fields['shipping']['shipping_address_2'] = array(
                'type' => 'select',
                'label' => __('Quartier', 'delivr-cm-shipping'),
                'placeholder' => __('Sélectionnez votre quartier', 'delivr-cm-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-neighborhood-select'),
                'options' => $neighborhoods,
                'priority' => 60,
            );
        }

        // Modify city field to trigger neighborhood refresh
        if (isset($fields['billing']['billing_city'])) {
            $fields['billing']['billing_city'] = array(
                'type' => 'select',
                'label' => __('Ville', 'delivr-cm-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-city-select'),
                'options' => array(
                    '' => __('Sélectionnez une ville', 'delivr-cm-shipping'),
                    'Douala' => 'Douala',
                    'Yaounde' => 'Yaoundé',
                ),
                'priority' => 50,
            );
        }

        if (isset($fields['shipping']['shipping_city'])) {
            $fields['shipping']['shipping_city'] = array(
                'type' => 'select',
                'label' => __('Ville', 'delivr-cm-shipping'),
                'required' => true,
                'class' => array('form-row-wide', 'delivr-city-select'),
                'options' => array(
                    '' => __('Sélectionnez une ville', 'delivr-cm-shipping'),
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
        $cache_key = self::CACHE_KEY . '_' . sanitize_key($city);

        // Try cache first
        $cached = get_transient($cache_key);
        if (false !== $cached) {
            return $cached;
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
        $url = add_query_arg('city', urlencode($city), $url);

        $response = wp_remote_get($url, $args);

        if (is_wp_error($response)) {
            // Return fallback neighborhoods
            return $this->get_fallback_neighborhoods($city);
        }

        $status_code = wp_remote_retrieve_response_code($response);

        if ($status_code !== 200) {
            return $this->get_fallback_neighborhoods($city);
        }

        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        // Build options array
        $options = array(
            '' => __('Sélectionnez votre quartier', 'delivr-cm-shipping'),
        );

        if (isset($data['results']) && is_array($data['results'])) {
            foreach ($data['results'] as $neighborhood) {
                $name = $neighborhood['name'];
                $options[$name] = $name;
            }
        } elseif (is_array($data)) {
            foreach ($data as $neighborhood) {
                if (isset($neighborhood['name'])) {
                    $name = $neighborhood['name'];
                    $options[$name] = $name;
                }
            }
        }

        // Cache the result
        set_transient($cache_key, $options, self::CACHE_EXPIRATION);

        return $options;
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
            '' => __('Sélectionnez votre quartier', 'delivr-cm-shipping'),
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
        $shipping_methods = WC()->shipping()->get_shipping_methods();

        if (isset($shipping_methods['delivr_cm'])) {
            return $shipping_methods['delivr_cm']->settings;
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

        $neighborhoods = $this->get_neighborhoods($city);

        wp_send_json_success($neighborhoods);
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
            'delivr-cm-checkout',
            DELIVR_CM_PLUGIN_URL . 'assets/js/checkout.js',
            array('jquery', 'wc-checkout'),
            DELIVR_CM_VERSION,
            true
        );

        wp_localize_script(
            'delivr-cm-checkout',
            'delivr_cm_params',
            array(
                'ajax_url' => admin_url('admin-ajax.php'),
                'nonce' => wp_create_nonce('delivr_cm_nonce'),
            )
        );

        wp_enqueue_style(
            'delivr-cm-checkout',
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
}

// Initialize
new WC_Delivr_Checkout_Fields();
