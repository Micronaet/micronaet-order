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
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
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

    # -------------------------------------------------------------------------
    # Scheduler:
    # -------------------------------------------------------------------------
    def scheduled_sale_order_shop_mail(
            self, cr, uid, partner_id, destination_id, context=None):
        """ Report for order to the shop
        """
        # ---------------------------------------------------------------------
        # Search data order line:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')
        line_pool = self.pool.get('sale.order.line')

        # Generate domain:
        domain = [
            ('order_id.partner_id', '=', partner_id),
            ('order_id.destination_partner_id', '=', destination_id),
            ('order_id.state', 'not in', ('draft', 'sent', 'cancel')),
            ('order_id.mx_closed', '=', False),
            ('mx_closed', '=', False),
            # ('order_id.pricelist_order', '=', False)
            # ('order_id.forecasted_production_id', '=', False)
            ]

        _logger.info('Domain: %s' % (domain, ))
        line_ids = line_pool.search(cr, uid, domain, context=None)

        # ---------------------------------------------------------------------
        #                              Excel:
        # ---------------------------------------------------------------------
        ws_name = 'Dettaglio ordini negozio'
        excel_pool.create_worksheet(ws_name)

        # Write header:
        header = [
            'Ordine', 'Data',
            # 'Partner', 'Destinazione',
            'Prodotto', 'Descrizione', 'Scadenza',
            'Produzione',
            'Ordinata', 'Assegnata', 'Prodotta', 'Consegnata', 'Residua',
             ]
        width = [
            18, 15,
            # 20, 20,
            15, 40, 10,
            15,
            10, 10, 10, 10, 10,
            ]
        excel_pool.column_width(ws_name, width)

        # Format:
        excel_pool.set_format()
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'black': {
                'text': excel_pool.get_format('text'),
                'number': excel_pool.get_format('number'),
            },
            'red': {
                'text': excel_pool.get_format('bg_red'),
                'number': excel_pool.get_format('bg_red_number'),
            },
            'yellow': {
                'text': excel_pool.get_format('bg_yellow'),
                'number': excel_pool.get_format('bg_yellow_number'),
            },
            'green': {
                'text': excel_pool.get_format('bg_green'),
                'number': excel_pool.get_format('bg_green_number'),
            },
        }

        row = 0
        excel_pool.write_xls_line(ws_name, row, [
            'Dettaglio ordini per negozio (attivi)',
            ], excel_format['title'])

        row += 1
        excel_pool.write_xls_line(ws_name, row, header, excel_format['header'])
        for line in line_pool.browse(
                cr, uid, line_ids, context=context):
            row += 1
            order = line.order_id
            product = line.product_id

            oc_qty = line.product_uom_qty
            stock_qty = line.mx_assigned_qty
            mrp_qty = line.product_uom_maked_sync_qty
            delivered_qty = line.delivered_qty
            remain_qty = oc_qty - stock_qty - mrp_qty

            if remain_qty <= 0:
                color_format = excel_format['green']
            else:
                color_format = excel_format['black']

            excel_pool.write_xls_line(ws_name, row, [

                order.name,
                order.date_order,
                # order.partner_id.name,

                product.default_code or '',
                line.name,
                line.date_deadline or '',

                line.mrp_id.name or '',

                oc_qty,
                stock_qty,
                mrp_qty,
                delivered_qty,
                remain_qty,
            ], color_format['text'])

        return excel_pool.send_mail_to_group(cr, uid,
            'sale_order_for_shop.group_sale_order_for_shop_mail',
            u'Mail automatica ODOO: Ordini per negozio',
            u'In allegato gli ordini aperti per il negozio.\n'
            u'Le righe verdi rappresentano la merce pronta.\n'
            u'Ci sono delle colonne di dettaglio che permettono di sapere:\n'
            u'- quale è la quantita ordinata,\n'
            u'- quella assegnata da magazzino,\n'
            u'- quella prodotta,\n'
            u'- quella consegnata e la residua.',
            u'ordini_negozio.xlsx',
            context=context)
