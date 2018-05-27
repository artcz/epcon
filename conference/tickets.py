# coding: utf-8

from assopy.models import Order, OrderItem
from conference.models import Ticket


def are_order_items_already_created(order):
    assert isinstance(order, Order)
    return order.orderitem_set.all().count() > 0


def create_ticket_from_order_item(order_item):
    assert isinstance(order_item, OrderItem)
    user = order_item.order.user.user
    ticket = Ticket.objects.create(
        user=user,
        fare=order_item.fare,
        fare_description=order_item.fare.description
    )
    return ticket


def create_tickets_for_order(order):
    assert isinstance(order, Order)
    assert are_order_items_already_created(order)
    assert order.is_already_paid
    tickets = []
    for order_item in order.orderitem_set.all():
        ticket = create_ticket_from_order_item(order_item)
        tickets.append(ticket)

    return tickets
