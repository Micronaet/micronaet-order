# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """

    _inherit = 'sale.order'

    def extract_report_rpc_call(self, cr, uid, ids, context=None):
        """ Extract report with force parameters:
            context['force'] = {
                'partner_id': partner_id,  # Partner reference
                'fullname': fullname,   # File Excel output
                # Period checked:
                'from_date': from_date,
                'to_date': to_date,
                }
        """
        pdb.set_trace()
        if not context:
            context = {}

        order_pool = self.pool.get('sale.order')
        xls_pool = self.pool.get('excel.writer')

        params = context.get('force', {})

        # ---------------------------------------------------------------------
        # Collect data:
        # ---------------------------------------------------------------------
        partner_id = params.get('partner_id')
        from_date = params.get('from_date')
        to_date = params.get('to_date')
        fullname = params.get('fullname')

        order_ids = order_pool.search(cr, uid, [
            ('partner_id', '=', partner_id),

            ('date_order', '>=', '%s 00:00:00' % from_date),
            ('date_order', '<=', '%s 23:59:59' % to_date),

            ('state', 'not in', ('draft', 'sent', 'cancel')),
            ], context=context)

        data = {}
        for order in order_pool.browse(cr, uid, order_ids, context=context):
            forecast = order.previsional

            for line in order.order_line:
                product = line.product_id
                quantity = line.product_uom_qty

                if product not in data:
                    # Stock free:
                    data[product] = [
                        0.0,  # Forecast
                        0.0,  # OC
                        # Stock available:
                        product.mx_net_mrp_qty + product.mx_mrp_b_locked
                        ]

                if forecast:
                    data[product][0] += quantity
                else:
                    data[product][1] += quantity

        # ---------------------------------------------------------------------
        # Excel
        # ---------------------------------------------------------------------
        column_width = (
            15, 40,
            10, 10, 10,
            # 20,
        )
        ws_name = _('Ordini previsionali')
        xls_pool.create_worksheet(ws_name)
        xls_pool.column_width(ws_name, column_width)
        xls_pool.column_hidden(ws_name, [0])

        # Format
        number_format = '#,##0.#0'
        xls_pool.set_format(number_format=number_format)
        excel_format = {
            'title': xls_pool.get_format('title'),
            'header': xls_pool.get_format('header'),
            'total': xls_pool.get_format('number_total'),
            'center': xls_pool.get_format('text_center_all'),
            'right': xls_pool.get_format('text_right'),
            'white': {
                'text': xls_pool.get_format('bg_white'),
                'number': xls_pool.get_format('bg_white_number'),
            },
            'red': {
                'text': xls_pool.get_format('bg_red'),
                'number': xls_pool.get_format('bg_red_number'),
            },
            'green': {
                'text': xls_pool.get_format('bg_green'),
                'number': xls_pool.get_format('bg_green_number'),
            },
        }

        header = (
            'Codice', 'Prodotto',
            'Previs.', 'Ordinati', 'Disponibile',

        )
        row = 0
        xls_pool.write_xls_line(
            ws_name, row, header, default_format=excel_format['header'])
        # xls_pool.merge_cell(ws_name, [row, 1, row + 1, 1])

        # Data loop:
        for product in sorted(data, key=lambda p: (p.default_code or '')):
            row += 1
            forecast_qty, oc_qty, available_qty = data[product]
            if forecast_qty:
                color = excel_format['white']
            else:
                color = excel_format['red']

            xls_pool.write_xls_line(
                ws_name, row, [
                    product.default_code or '',
                    product.name,
                    (forecast_qty, color['number']),
                    (oc_qty, color['number']),
                    (available_qty, color['number']),
                ],
                default_format=color['text'])
        return xls_pool.save_file_as(fullname)


class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """
    _inherit = 'sale.order.line'

    _columns = {
        'previsional': fields.related(
            'order_id', 'previsional',
            type='boolean', string='Previsionale', store=False),
        }
