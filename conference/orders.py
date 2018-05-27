# coding: utf-8

from __future__ import unicode_literals, absolute_import

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Max
from django.utils import timezone

from assopy.models import Order, OrderItem

from .models import Fare
from .invoicing import create_invoices_for_order
from .tickets import create_tickets_for_order
from .coupons import apply_coupon_to_order


ORDER_CODE_PREFIX = "O/"
ORDER_CODE_TEMPLATE = "O/%(year_two_digits)s.%(sequential_id)s"

# ORDER_CODE_TEMPLATE = "O/{year_two_digits:02d}.{sequential_id:04d}"


def increment_order_code(code):
    NUMBER_OF_DIGITS_WITH_PADDING = 4

    prefix_with_year, number = code.split('.')
    number = str(int(number) + 1).zfill(NUMBER_OF_DIGITS_WITH_PADDING)
    return "{}.{}".format(prefix_with_year, number)


def latest_order_code_for_year(prefix, year):
    """
    returns latest used order.code in a given year.
    rtype – string or None
    """
    assert 2016 <= year <= 2020, year
    assert prefix == ORDER_CODE_PREFIX

    orders = Order.objects.filter(
        code__startswith=prefix,
        date__year=year,
    )

    return orders.aggregate(max=Max('code'))['max']


def next_order_code_for_year(prefix, year):
    assert 2016 <= year <= 2020, year
    assert prefix == ORDER_CODE_PREFIX

    current_code = latest_order_code_for_year(prefix, year)
    if current_code:
        next_code = increment_order_code(current_code)
        return next_code

    # if there are no current codes, return the first one
    return ORDER_CODE_TEMPLATE % {'year_two_digits': year % 1000,
                                  'sequential_id': '0001'}


def are_items_valid(items):
    """
    :items: dictionary {fare_code: quantity, fare_code2: quantity2}
            like {'TRSP': 2, 'VOUPE03': 1}
    """
    available_fares = Fare.objects.available().values_list('code', flat=True)

    for key, value in items.items():
        assert key in available_fares, key
        assert value < settings.MAX_TICKETS_PER_ORDER

    return True


def create_order_items(order, items):
    """
    :items: dictionary {fare_code: quantity, fare_code2: quantity2}
            like {'TRSP': 2, 'VOUPE03': 1}

    """
    assert isinstance(order, Order)
    assert are_items_valid(items)

    def calculate_price(fare, quantity):
        # TODO any VAT calculations here(?)
        return fare.price * quantity

    for fare_code, quantity in items.items():
        fare = Fare.objects.get(fare_code=fare_code)
        OrderItem.objects.create(
            order=order,
            ticket=None,  # to be filled in later
            code=fare_code,
            price=calculate_price(fare.price, quantity),
            description=fare.description,
            vat=fare.vat,  # FIXME that's wrong
        )


def create_order(user, payment_method, items,
                 billing_notes=None,
                 country=None,
                 address=None,
                 coupons=None):
    """
    :items: dictionary {fare_code: quantity, fare_code2: quantity2}
            like {'TRSP': 2, 'VOUPE03': 1}

    """

    assert isinstance(user, User)  # AssopyUser or User(?)
    assert payment_method in Order.PAYMENT_METHODS
    assert are_items_valid(items)
    coupons = [] if coupons is None else coupons

    order = Order(
        code=next_order_code_for_year(timezone.now().year),
        method=payment_method,
        user=user,
        billing_notes=billing_notes,
        country=country,
        address=address,
    )
    for coupon in coupons:
        order = apply_coupon_to_order(coupon, order)

    order.save()

    create_order_items(order, items)
    return order


def confirm_order(order):
    """
    NOTE(artcz)(2018-05-27)
    This should probably not be called when we go for deferred invoices,
    because it issues tickets and invoices at the same time.
    """
    assert isinstance(order, Order)

    create_invoices_for_order(order)
    create_tickets_for_order(order)
