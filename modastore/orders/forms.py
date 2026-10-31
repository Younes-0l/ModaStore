from accounts.forms import AddressForm


class CheckoutAddressForm(AddressForm):
    """Same validation as AddressForm, with fewer and re-ordered fields."""

    class Meta(AddressForm.Meta):
        fields = (
            'receiver_name', 'receiver_phone', 'province', 'city',
            'postal_code', 'title', 'full_address',
        )