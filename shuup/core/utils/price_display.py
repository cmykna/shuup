# This file is part of Shuup.
#
# Copyright (c) 2012-2016, Shoop Ltd. All rights reserved.
#
# This source code is licensed under the AGPLv3 license found in the
# LICENSE file in the root directory of this source tree.
"""
Utilities for displaying prices correctly.

Contents:

  * Class `PriceDisplayOptions` for storing the display options.

  * Helper function `render_price_property` for rendering prices
    correctly from Python code.

  * Various filter classes for implementing Jinja2 filters.
"""

import django_jinja.library
import jinja2

from shuup.core.pricing import PriceDisplayOptions, Priceful
from shuup.core.templatetags.shuup_common import money, percent

from .prices import convert_taxness


def render_price_property(request, item, priceful, property_name='price'):
    """
    Render price property of a Priceful object.

    :type request: django.http.HttpRequest
    :type item: shuup.core.taxing.TaxableItem
    :type priceful: shuup.core.pricing.Priceful
    :type propert_name: str
    :rtype: str
    """
    options = PriceDisplayOptions.from_context({'request': request})
    if options.hide_prices:
        return ""
    new_priceful = convert_taxness(
        request, item, priceful, options.include_taxes)
    price_value = getattr(new_priceful, property_name)
    return money(price_value)


class _ContextObject(object):
    def __init__(self, name, property_name=None):
        self.name = name
        self.property_name = (property_name or name)
        self._register()


class _ContextFilter(_ContextObject):
    def _register(self):
        django_jinja.library.filter(
            name=self.name,
            fn=jinja2.contextfilter(self))


class _ContextFunction(_ContextObject):
    def _register(self):
        django_jinja.library.global_function(
            name=self.name,
            fn=jinja2.contextfunction(self))


class PriceDisplayFilter(_ContextFilter):
    def __call__(self, context, item, quantity=1):
        options = PriceDisplayOptions.from_context(context)
        if options.hide_prices:
            return ""
        request = context.get('request')
        orig_priceful = _get_priceful(request, item, quantity)
        if not orig_priceful:
            return ""
        priceful = convert_taxness(
            request, item, orig_priceful, options.include_taxes)
        price_value = getattr(priceful, self.property_name)
        return money(price_value)


class PricePropertyFilter(_ContextFilter):
    def __call__(self, context, item, quantity=1):
        priceful = _get_priceful(context.get('request'), item, quantity)
        if not priceful:
            return ""
        return getattr(priceful, self.property_name)


class PricePercentPropertyFilter(_ContextFilter):
    def __call__(self, context, item, quantity=1):
        priceful = _get_priceful(context.get('request'), item, quantity)
        if not priceful:
            return ""
        return percent(getattr(priceful, self.property_name))


class TotalPriceDisplayFilter(_ContextFilter):
    def __call__(self, context, source):
        """
        :type source: shuup.core.order_creator.OrderSource|
                      shuup.core.models.Order
        """
        options = PriceDisplayOptions.from_context(context)
        if options.hide_prices:
            return ""
        try:
            if options.include_taxes is None:
                total = source.total_price
            elif options.include_taxes:
                total = source.taxful_total_price
            else:
                total = source.taxless_total_price
        except TypeError:
            total = source.total_price
        return money(total)


class PriceRangeDisplayFilter(_ContextFilter):
    def __call__(self, context, product, quantity=1):
        """
        :type product: shuup.core.models.Product
        """
        options = PriceDisplayOptions.from_context(context)
        if options.hide_prices:
            return ("", "")
        request = context.get('request')
        priced_children = product.get_priced_children(request, quantity)
        priced_products = priced_children if priced_children else [
            (product, _get_priceful(request, product, quantity))]

        def get_formatted_price(priced_product):
            (prod, price_info) = priced_product
            if not price_info:
                return ""
            pf = convert_taxness(
                request, prod, price_info, options.include_taxes)
            return money(pf.price)

        min_max = (priced_products[0], priced_products[-1])
        return tuple(get_formatted_price(x) for x in min_max)


def _get_priceful(request, item, quantity):
    """
    Get priceful from given item.

    If item has `get_price_info` method, it will be called with given
    `request` and `quantity` as arguments, otherwise the item itself
    should implement the `Priceful` interface.

    :type request: django.http.HttpRequest
    :type item: shuup.core.taxing.TaxableItem
    :type quantity: numbers.Number
    :rtype: shuup.core.pricing.Priceful|None
    """
    if hasattr(item, 'get_price_info'):
        if hasattr(item, 'is_variation_parent'):
            if item.is_variation_parent():
                return item.get_cheapest_child_price_info(request, quantity)
        return item.get_price_info(request, quantity=quantity)
    if hasattr(item, 'get_total_cost'):
        return item.get_total_cost(request.basket)
    assert isinstance(item, Priceful)
    return item
