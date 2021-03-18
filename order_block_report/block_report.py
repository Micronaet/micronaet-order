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


class SaleOrderBlockGroup(orm.Model):
    """ Model name: SaleOrderBlockGroup
    """

    _name = 'sale.order.block.group'
    _description = 'Sale order block'
    _rec_name = 'code'
    _order = 'code'

    def print_only_this(self, cr, uid, ids, context=None):
        """ Print sale order only with this block
        """
        if context is None:
            context = {}

        sale_pool = self.pool.get('sale.order')

        current_proxy = self.browse(cr, uid, ids, context=context)
        context['only_this_block'] = ids[0]

        return sale_pool.print_quotation(
            cr, uid, [current_proxy.order_id.id], context=context)

    def _function_get_total_block(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for block in self.browse(cr, uid, ids, context=context):
            res[block.id] = 0.0
            for sol in block.order_id.order_line:
                if sol.block_id.id == block.id:
                    res[block.id] += sol.price_subtotal
            if block.block_margin:
                res[block.id] = res[block.id] * (
                    100.0 + block.block_margin) / 100.0
        return res

    _columns = {
        'code': fields.integer('Code', required=True),
        'name': fields.char('Name', size=64, required=True),
        'block_margin': fields.float('Extra recharge %', digits=(16, 3),
            help='Add extra recharge to calculate real total'),

        'pre_text': fields.text('Pre text'),
        'post_text': fields.text('Post text'),

        'total': fields.float(
            'Block total', digits=(16, 2),
            help='Total written in offer block'),
        'real_total': fields.function(
            _function_get_total_block, method=True,
            type='float', string='Real total', store=False,
            help='Total sum of sale line in this block'),
        'order_id': fields.many2one('sale.order', 'Order', ondelete='cascade'),

        # Parameter for line:
        'hide_block': fields.boolean(
            'Hide block', help='Hide in report for simulation'),
        'not_confirmed': fields.boolean(
            'Not confirmed', help='Removed from order'),

        'show_header': fields.boolean('Show header'),
        'show_detail': fields.boolean('Show details'),
        'show_code': fields.boolean(
            'Show code',
            help='Show code in line details'),
        'show_price': fields.boolean(
            'Show price',
            help='Show unit price and subtotal'),
        # 'show_subtotal': fields.boolean('Show Subtotal'),
        'show_total': fields.boolean('Show total'),
        }

    _defaults = {
       'show_header': lambda *a: True,
       'show_detail': lambda *a: True,
       'show_code': lambda *a: True,
       'show_price': lambda *a: True,
       # 'show_subtotal': lambda *a: True,
       'show_total': lambda *a: True,
        }


class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """
    _inherit = 'sale.order'

    def dummy_action(self, cr, uid, ids, context=None):
        """ Dummy button to refresh data
        """
        return True

    # -------------------------------------------------------------------------
    # Override function:
    # -------------------------------------------------------------------------
    def copy(self, cr, uid, old_id, default=None, context=None):
        """ Create a new record in ClassName model from existing one
            @param cr: cursor to database
            @param uid: id of current user
            @param id: list of record ids on which copy method executes
            @param default: dict type contains the values to override in copy oper.
            @param context: context arguments

            @return: returns a id of newly created record
        """
        new_id = super(SaleOrder, self).copy(
            cr, uid, old_id, default=default, context=context)

        block_pool = self.pool.get('sale.order.block.group')
        block_ids = block_pool.search(cr, uid, [
            ('order_id', '=', old_id),
            ], context=context)
        convert_db = []

        # XXX When adding new parameter put here!
        # ---------------------------------------------------------------------
        # Duplicate block list:
        # ---------------------------------------------------------------------
        _logger.warning('Duplicate extra block in sale: %s' % len(block_ids))
        for block in block_pool.browse(cr, uid, block_ids, context=context):
            data = {
                'code': block.code,
                'name': block.name,

                'pre_text': block.pre_text,
                'post_text': block.post_text,

                'total': block.total,
                # 'real_total':
                'order_id': new_id,

                # Parameter for line:
                'show_header': block.show_header,
                'show_detail': block.show_detail,
                'show_code': block.show_code,
                'show_price': block.show_detail,
                # 'show_subtotal': fields.boolean('Show Subtotal'),
                'show_total': block.show_total,
                }
            convert_db.append((
                block.id, block_pool.create(cr, uid, data, context=context)))

        # ---------------------------------------------------------------------
        # Change reference for block in detail list:
        # ---------------------------------------------------------------------
        sol_pool = self.pool.get('sale.order.line')
        _logger.warning('Update reference in details: %s' % len(convert_db))
        for old, new in convert_db:
            sol_ids = sol_pool.search(cr, uid, [
                ('order_id', '=', new_id),
                ('block_id', '=', old),
                ], context=context)
            if not sol_ids:
                continue
            sol_pool.write(cr, uid, sol_ids, {
                'block_id': new,
                }, context=context)
        return new_id

    def print_quotation(self, cr, uid, ids, context=None):
        """ This function prints the sales order and mark it as sent
            so that we can see more easily the next step of the workflow
        """
        if context is None:
            context = {}

        assert len(ids) == 1, \
            'This option should only be used for a single id at a time'

        # Mark as sent: TODO use workflow?
        # wf_service = netsvc.LocalService("workflow")
        # wf_service.trg_validate(
        #    uid, 'sale.order', ids[0], 'quotation_sent', cr)

        datas = {
            'model': 'sale.order',
            'ids': ids,
            'form': self.read(cr, uid, ids[0], context=context),
            }
        only_this_block = context.get('only_this_block')
        if only_this_block:
            datas['only_this_block'] = only_this_block

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'custom_block_sale_order_report',
            'datas': datas,
            'nodestroy': True,
            }

    # -------------------------------------------------------------------------
    # Fields function:
    # -------------------------------------------------------------------------
    def _function_get_total_block(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = 0.0
            for block in order.block_ids:
                res[order.id] += block.total or block.real_total
        return res

    _columns = {
        'show_master_total': fields.boolean('Show master total'),
        'block_ids': fields.one2many(
            'sale.order.block.group', 'order_id', 'Block'),

        'real_total': fields.function(
            _function_get_total_block, method=True,
            type='float', string='Real total', store=False,
            help='Total sum of sale line in this block'),
        }

    _defaults = {
        'show_master_total': lambda *x: True,
        }


class SaleOrderLine(orm.Model):
    """ Model name: SaleOrder
    """
    _inherit = 'sale.order.line'
    _order = 'block_id,sequence'

    def onchange_categ_id(
            self, cr, uid, ids, categ_id, pre_filter, context=None):
        """ Force domain of product
        """
        res = {
            'domain': {
                'product_id': []},
            'value': {},
            }
        if categ_id:
            res['domain']['product_id'].append(
                ('categ_id', '=', categ_id))
            res['value']['product_id'] = False

        if pre_filter:
            # res['domain']['product_id'].extend(
            #    self.pool.get('product.product').clean_domain_filter_from_text(
            #    cr, uid, pre_filter, context=context))
            res['domain']['product_id'].append(
                ('default_code', 'ilike', pre_filter))
            # print res
            res['value']['pre_filter'] = False # XXX reset filter
        return res

    _columns = {
        'pre_filter': fields.char('Pre filter', size=50),
        'block_id': fields.many2one(
            'sale.order.block.group', 'Block',
            ondelete='set null'),
        'categ_id': fields.many2one('product.category', 'Category'),
        }


class SaleOrderBlockGroup(orm.Model):
    """ Model name: SaleOrderBlockGroup
    """

    _inherit = 'sale.order.block.group'


    _columns = {

        'line_ids': fields.one2many(
            'sale.order.line', 'block_id', 'Sale order line'),
        }
