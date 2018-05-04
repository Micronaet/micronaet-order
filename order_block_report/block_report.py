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
    
    def _function_get_total_block(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for block in self.browse(cr, uid, ids, context=context):            
            res[block.id] = 0.0
            for sol in block.order_id.order_line:
                if sol.block_id.id == block.id:
                    res[block.id] += sol.price_subtotal
        return res
        
    _columns = {
        'code': fields.integer('Code', required=True),
        'name': fields.char('Name', size=64, required=True),
        
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
        'show_header': fields.boolean('Show header'),
        'show_detail': fields.boolean('Show details'),
        'show_price': fields.boolean(
            'Show price', 
            help='Show unit price and subtotal'),
        #'show_subtotal': fields.boolean('Show Subtotal'),
        'show_total': fields.boolean('Show total'),        
        }
    
    _defaults = {
       'show_header': lambda *a: True,
       'show_detail': lambda *a: True,
       'show_price': lambda *a: True,
       #'show_subtotal': lambda *a: True,
       'show_total': lambda *a: True,
        }

class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """    
    _inherit = 'sale.order'
    
    _columns = {
        'block_ids': fields.one2many(
            'sale.order.block.group', 'order_id', 'Block'),
        }

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrder
    """    
    _inherit = 'sale.order.line'
    _order = 'block_id,sequence'
    
    def onchange_categ_id(self, cr, uid, ids, categ_id, context=None):
        ''' Force domain of product   
        '''
        res = {
            'domain': {},
            'value': {},
            }
        if categ_id:
            res['domain']['product_id'] = [('categ_id', '=', categ_id)]
            res['value']['product_id'] = False
        else:    
            res['domain']['product_id'] = []        
        return res
        
    _columns = {
        'block_id': fields.many2one('sale.order.block.group', 'Block', 
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
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
