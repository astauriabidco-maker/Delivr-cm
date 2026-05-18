from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "delivr-cm-shipping"


def read_plugin_file(relative_path):
    return (PLUGIN_DIR / relative_path).read_text(encoding="utf-8")


def test_payment_complete_only_creates_delivery_for_relay237_shipping():
    plugin = read_plugin_file("delivr-cm-shipping.php")

    assert "function delivr_cm_order_uses_shipping" in plugin
    assert "get_method_id() === 'delivr_cm'" in plugin
    assert "if (!delivr_cm_order_uses_shipping($order))" in plugin
    assert plugin.index("if (!delivr_cm_order_uses_shipping($order))") < plugin.index(
        "$shipping_method->trigger_delivery_order($order_id);"
    )


def test_delivery_creation_never_marks_sent_without_delivery_id():
    shipping = read_plugin_file("includes/class-wc-shipping-delivr.php")

    assert "private function order_uses_method($order)" in shipping
    assert "if (!$this->order_uses_method($order))" in shipping
    assert "sanitize_text_field($data['delivery_id'])" in shipping
    assert "if (empty($delivery_id))" in shipping
    assert shipping.index("if (empty($delivery_id))") < shipping.index(
        "$order->update_meta_data('_delivr_cm_order_sent', 'yes');"
    )


def test_checkout_phone_normalization_accepts_local_cameroon_numbers():
    shipping = read_plugin_file("includes/class-wc-shipping-delivr.php")

    assert "preg_match('/^0[0-9]{8,9}$/', $phone)" in shipping
    assert "substr($phone, 1)" in shipping
    assert "preg_replace('/^\\+2370/', '+237', $phone)" in shipping


def test_webhook_receiver_is_signed_idempotent_and_heals_delivery_id():
    receiver = read_plugin_file("includes/class-wc-webhook-receiver.php")

    assert "$request->get_header('x-webhook-signature')" in receiver
    assert "hash_hmac('sha256', $body, $secret)" in receiver
    assert "$previous_status = $order->get_meta('_delivr_cm_delivery_status')" in receiver
    assert "$is_duplicate = $previous_status === $status && $previous_event === $event" in receiver
    assert "$order->update_meta_data('_delivr_cm_delivery_id', $delivery_id)" in receiver
    assert "if (!$is_duplicate)" in receiver
