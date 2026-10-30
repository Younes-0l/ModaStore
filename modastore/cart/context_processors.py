from . import services


def cart_count(request):
    return {'cart_count': services.cart_count(request)}