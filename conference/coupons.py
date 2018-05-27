# coding: utf-8

from assopy.models import Coupon, Order


def create_coupon(fares, start_validity, end_validity):
    pass


def apply_coupon_to_order(coupon, order):
    assert isinstance(coupon, Coupon)
    assert isinstance(order, Order)

    pass
