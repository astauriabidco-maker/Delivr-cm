/**
 * DELIVR-CM Checkout JavaScript
 *
 * Handles dynamic neighborhood loading based on city selection
 */

(function ($) {
    'use strict';

    var DelivrCheckout = {
        /**
         * Initialize
         */
        init: function () {
            this.bindEvents();
        },

        /**
         * Bind event handlers
         */
        bindEvents: function () {
            // City change handlers
            $(document.body).on('change', '#billing_city', this.onCityChange);
            $(document.body).on('change', '#shipping_city', this.onCityChange);

            // Sync billing to shipping
            $(document.body).on('change', '#billing_address_2', this.syncNeighborhood);

            // Update shipping on neighborhood change
            $(document.body).on('change', '.delivr-neighborhood-select select', this.triggerShippingUpdate);
        },

        /**
         * Handle city change
         */
        onCityChange: function () {
            var $this = $(this);
            var city = $this.val();
            var type = $this.attr('id').indexOf('billing') !== -1 ? 'billing' : 'shipping';
            var $neighborhoodField = $('#' + type + '_address_2');

            if (!city) {
                return;
            }

            // Show loading state
            $neighborhoodField.prop('disabled', true);

            // Fetch neighborhoods via AJAX
            $.ajax({
                url: delivr_cm_params.ajax_url,
                type: 'POST',
                data: {
                    action: 'delivr_get_neighborhoods',
                    nonce: delivr_cm_params.nonce,
                    city: city
                },
                success: function (response) {
                    if (response.success) {
                        DelivrCheckout.updateNeighborhoodOptions($neighborhoodField, response.data);
                    }
                },
                error: function () {
                    console.error('DELIVR-CM: Failed to load neighborhoods');
                },
                complete: function () {
                    $neighborhoodField.prop('disabled', false);
                }
            });
        },

        /**
         * Update neighborhood select options
         */
        updateNeighborhoodOptions: function ($field, options) {
            var currentVal = $field.val();

            $field.empty();

            $.each(options, function (value, label) {
                $field.append($('<option></option>').attr('value', value).text(label));
            });

            // Restore previous value if exists
            if (currentVal && options[currentVal]) {
                $field.val(currentVal);
            }

            // Trigger change to update shipping
            $field.trigger('change');
        },

        /**
         * Sync billing neighborhood to shipping
         */
        syncNeighborhood: function () {
            var $shippingDifferent = $('#ship-to-different-address-checkbox');

            if (!$shippingDifferent.is(':checked')) {
                $('#shipping_address_2').val($(this).val());
            }
        },

        /**
         * Trigger shipping methods update
         */
        triggerShippingUpdate: function () {
            // Trigger WooCommerce shipping update
            $(document.body).trigger('update_checkout');
        }
    };

    // Initialize on document ready
    $(document).ready(function () {
        DelivrCheckout.init();
    });

})(jQuery);
