#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    counters = {}
    last_record = 0

    def __init__(self, cr, uid, name, context):

        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object_line': self.get_object_line,
            'get_object_order_line': self.get_object_order_line,

            'get_datetime': self.get_datetime,
            'get_date': self.get_date,

            'get_filter_description': self.get_filter_description,

            'extract_order_line': self.extract_order_line,
            'get_extract_database': self.get_extract_database,
        })

    def get_filter_description(self, ):
        return self.filter_description

    def get_datetime(self):
        """ Return datetime obj
        """
        return datetime

    def get_date(self):
        """ Return datetime obj
        """
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    # Utility for 2 report:
    def get_object_line(self, data):
        """ Order line delivered
        """
        _logger.info('Start report data: %s' % data)

        # Parameters for report management:
        sale_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')

        fiscal_position = data.get('fiscal_position', 'all')
        partner_id = data.get('partner_id', False)
        statistic_category_id = data.get('statistic_category_id', False)
        statistic_category_name = data.get('statistic_category_name', False)
        from_date = data.get('from_date', False)
        to_date = data.get('to_date', False)
        from_deadline = data.get('from_deadline', False)
        to_deadline = data.get('to_deadline', False)
        report_type = data.get('report_type', False)
        data_type = data.get('data_type', '')
        order_status = data.get('order_status', '')
        discount_limit = data.get('discount_limit', '')

        # ---------------------------------------------------------------------
        #                      Sale order filter
        # ---------------------------------------------------------------------
        # Default:
        domain = [
            ('state', 'not in', ('cancel', 'draft', 'sent')),  # 'done'
            ('pricelist_order', '=', False),
            ]

        self.filter_description = _(
            'Ora: %s, escluso ordini listino') % datetime.now()

        # Discount description:
        if discount_limit:
            self.filter_description += _(', Sconto >= %s' % discount_limit)

        # Add status test
        if order_status == 'open':
            domain.append(('mx_closed', '=', False))
            self.filter_description += _(', ordini aperti')
        elif order_status == 'close':
            domain.append(('mx_closed', '=', True))
            self.filter_description += _(', ordini chiusi')
        else: # all
            self.filter_description += _(', tutti gli ordini')

        if statistic_category_id:
            domain.append(
                ('partner_id.statistic_category_id', '=',
                 statistic_category_id))
            self.filter_description += ', %s' % statistic_category_name

        if fiscal_position == 'italy':
            # TODO not all!!!!!
            domain.append(('partner_id.property_account_position', '=', 1))
            self.filter_description += _(', Italia')
        elif fiscal_position == 'extra':
            domain.append(('partner_id.property_account_position', '!=', 1))
            self.filter_description += _(', non Italia')
        else:
            self.filter_description += _(', Tutte le nazioni')

        if partner_id:
            domain.append(('partner_id', '=', partner_id))
            self.filter_description += _(', Partner filter')

        if report_type == 'extract':
            self.filter_description += _(
                ', Dato visualizzato: %s') % data_type.upper()

        # -------------------------
        # Start filter description:
        # -------------------------
        if from_date:
            domain.append(('date_order', '>=', from_date))
            self.filter_description += _(', date >= %s') % from_date
        if to_date:
            domain.append(('date_order', '<=', to_date))
            self.filter_description += _(', date <= %s') % to_date

        order_ids = sale_pool.search(self.cr, self.uid, domain) # TODO order ?!
        _logger.info('Found %s orders' % len(order_ids))

        # ---------------------------------------------------------------------
        #                      Sale order line filter
        # ---------------------------------------------------------------------
        domain = [('order_id', 'in', order_ids)]

        if from_deadline:
            domain.append(('date_deadline', '>=', from_deadline))
            self.filter_description += _(', deadline >= %s') % from_deadline
        if to_deadline:
            domain.append(('date_deadline', '<=', to_deadline))
            self.filter_description += _(', deadline <= %s') % to_deadline

        line_ids = line_pool.search(
            self.cr, self.uid, domain,
            order='date_deadline, order_id, id')
        # res = []
        # _logger.info('Found %s order line' % len(line_ids))
        # for line in line_pool.browse(self.cr, self.uid, line_ids):
        #    if line.product_uom_qty - line.delivered_qty > 0.0:
        #        res.append(line.id)
        return line_pool.browse(self.cr, self.uid, line_ids)#res)

    def get_object_order_line(self, data):
        """ Order line delivered
        """
        order_list = []
        for line in self.get_object_line(data):
            if line.order_id not in order_list:
                # line.open_amount_total > 0 and
                order_list.append(line.order_id)
        return order_list

    def extract_order_line(self, data):
        """ Generate elements extract order report:
        """
        data = data or {}
        data_type = data.get('data_type', 'oc')
        data_sort = data.get('data_sort', 'number')  # or deadline

        self.extract_cells_ma = {}
        self.extract_cells_oc = {}
        self.extract_cells_b = {}
        self.extract_cells_s = {}

        self.extract_total = {}

        self.extract_product = []  # row
        self.extract_order = []  # col

        extract_product = {}
        extract_order = {}

        for line in self.get_object_line(data):
            product = line.product_id
            product_code = product.default_code or (
                _('NOT FOUND #: %s') % product.id)  # sort field

            order = line.order_id
            order_name = order.name  # sort field

            key = (product.id, order.id)

            if product.id not in self.extract_total:
                self.extract_total[product.id] = 0.0

            # -----------------------------------------------------------------
            # Quantity block:
            value_ma = line.product_uom_qty
            value_oc = value_ma - line.delivered_qty
            if value_oc == 0.0:
                continue  # line delivered jumped

            try: # for no production company:
                if line.product_uom_maked_sync_qty > line.delivered_qty:
                    # B = Produced + assigned:
                    value_b = line.mx_assigned_qty + \
                        line.product_uom_maked_sync_qty - line.delivered_qty
                else:
                    value_b = 0
            except:
                value_b = 0
            value_s = value_oc - value_b

            if key not in self.extract_cells_ma:
                self.extract_cells_ma[key] = value_ma
                self.extract_cells_oc[key] = value_oc
                self.extract_cells_b[key] = value_b
                self.extract_cells_s[key] = value_s
            else:
                self.extract_cells_ma[key] += value_ma
                self.extract_cells_oc[key] += value_oc
                self.extract_cells_b[key] += value_b
                self.extract_cells_s[key] += value_s

            if data_type == 'oc':
                self.extract_total[product.id] += value_oc
            elif data_type == 'ma':
                self.extract_total[product.id] += value_ma
            elif data_type == 'b':
                self.extract_total[product.id] += value_b
            elif data_type == 's':
                self.extract_total[product.id] += value_s
            # -----------------------------------------------------------------

            if product_code not in extract_product:
                extract_product[product_code] = product

            if order_name not in extract_order:
                extract_order[order_name] = order

        # Sort operation:
        for key, value in extract_product.iteritems():
            self.extract_product.append((key, value))
        self.extract_product.sort()

        for key, value in extract_order.iteritems():
            self.extract_order.append((key, value))

        if data_sort == 'deadline':
            self.extract_order.sort(key=lambda x: x[1].date_deadline)
        else: # 'number' default
            self.extract_order.sort()  # as is
        return ''

    def get_extract_database(self, name, key=False, data=False):
        """ return 3 elements: product, order, cell DB
            for cell DB return value passed with key (product, order)
        """
        data = data or {}
        data_type = data.get('data_type', 'oc')
        if name not in ('order', 'product', 'total'):
            name = 'key_%s' % data_type  # ma, oc, s, b

        if name == 'product':
            return self.extract_product
        elif name == 'order':
            return self.extract_order
        elif name == 'total':
            return self.extract_total.get(key, 0)

        elif name == 'key_ma':
            return self.extract_cells_ma.get(key, '')
        elif name == 'key_oc':
            return self.extract_cells_oc.get(key, '')
        elif name == 'key_s':
            return self.extract_cells_s.get(key, '')
        elif name == 'key_b':
            return self.extract_cells_b.get(key, '')

        elif name == 'key_sb': # not used for now
            s = self.extract_cells_s.get(key, '')
            b = self.extract_cells_b.get(key, '')
            if s or b:
                return 'S: %10s  B: %10s' % (
                    self.extract_cells_s.get(key),
                    self.extract_cells_b.get(key),
                    )
            return ''
        return '?'
