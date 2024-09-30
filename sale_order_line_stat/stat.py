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

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """

    _inherit = 'sale.order.line'

    def force_all_mrp_id(self, cr, uid, ids, context=None):
        """ Update
        """
        sol_ids = self.search(cr, uid, [
            ('family_id', '=', False)], context=context)
        for line in self.browse(cr, uid, sol_ids, context=context):
            self.write(cr, uid, line.id, {
                'is_manufactured': line.product_id.internal_manufacture,
                'family_id': line.product_id.family_id.id or False,
                }, context=context)
        return True

    # -------------------------------------------------------------------------
    # Store function:
    # -------------------------------------------------------------------------
    # sale.order:
    def _get_date_order_from_order(self, cr, uid, ids, context=None):
        """ When change sol line order
        """
        sale_pool = self.pool['sale.order']
        res = []
        for sale in sale_pool.browse(cr, uid, ids, context=context):
            for line in sale.order_line:
                res.append(line.id)
        return res

    def _get_date_order_from_sol(self, cr, uid, ids, context=None):
        """ When change sol line order
        """
        return ids

    # sale.order.line:
    def _get_default_code_from_sol(self, cr, uid, ids, context=None):
        """ When change sol line order
        """
        _logger.warning('Change product_id in sale.order.line')
        return ids

    def _get_default_code_from_product(self, cr, uid, ids, context=None):
        """ Change defauld code in product
        """
        _logger.warning('Change default_code in product.product')
        sol_pool = self.pool.get('sale.order.line')
        return sol_pool.search(cr, uid, [
            ('product_id', 'in', ids),
            ], context=context)

    _columns = {
        'force_sol':fields.boolean('Forza SOL'), # force default code calc.
        'default_code': fields.related(
            'product_id', 'default_code', type='char',
            store={
                'sale.order.line':
                    (_get_default_code_from_sol, [
                        'product_id', 'force_sol'], 10),
                'product.product':
                    (_get_default_code_from_product, ['default_code'], 10),
                }, string='Default code'),

        'destination_partner_id': fields.related(
            'order_id', 'destination_partner_id',
            type='many2one', string='Destination', relation='res.partner',
            store=False),

        'order_date': fields.related(
            'order_id', 'date_order', type='date',
            store={
                'sale.order.line': (
                    _get_date_order_from_sol, ['order_id'], 10),
                'sale.order': (
                    _get_date_order_from_order, ['date_order'], 10),
                }, string='Order date'),
        }
