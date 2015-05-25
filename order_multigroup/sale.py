# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
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

class SaleOrder(orm.Model):
    ''' Add extra field for manage master orders
    '''    
    _inherit = 'sale.order'
    
    _columns = {
        'master_order': fields.boolean('Master order'),
        }
    
class SaleOrderLineMaster(orm.Model):
    ''' Master element for create a grouped quotation
    '''    
    _name = 'sale.order.line.master'
    _description = 'Master order line'
    _order = 'order_id desc, sequence, id'
    
    # Button events:
    def write_subtotal(self, cr, uid, ids, context=None):
        ''' Calculate and write subtotal
        '''
        # TODO 
        return 0.0
        res = 0.0
        for item in self.browse(
                cr, uid, ids, context=context).master_child_ids:
            res += item.price_subtotal or 0.0            
        return self.write(cr, uid, ids, {
            'master_subtotal': res
            }, context=context)    
        
    _columns = {
        'sequence': fields.integer(
            'Sequence', 
            help="Gives the sequence order when displaying master fields."),
        'name': fields.text(
            'Description', required=True, readonly=True, 
            states={'draft': [('readonly', False)]}),
        'order_id': fields.many2one(
            'sale.order', 'Order Reference', required=True, 
            ondelete='cascade', select=True, 
            readonly=True, states={'draft':[('readonly',False)]}),
        'master_title': fields.text('Master title'),
        'master_note': fields.text('Master note'),
        'with_sub': fields.boolean('With subtotal'),
        'master_subtotal': fields.float(
            'Master subtotal', 
            digits=(16, 2)),
        #'state': fields.selection( # for problem in view (not used)
        #    [('draft', 'Draft')], 'State'),

        # Not used for now:
        'product_id': fields.many2one(
            'product.product', 'Product', domain=[('sale_ok', '=', True)], 
            change_default=True, readonly=True, 
            states={'draft': [('readonly', False)]}, 
            ondelete='restrict'),

        #'invoice_lines': fields.many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_id', 'Invoice Lines', readonly=True, copy=False),
        #'invoiced': fields.function(_fnct_line_invoiced, string='Invoiced', type='boolean',
        #    store={
        #        'account.invoice': (_order_lines_from_invoice, ['state'], 10),
        #        'sale.order.line': (lambda self,cr,uid,ids,ctx=None: ids, ['invoice_lines'], 10)
        #    }),
        'price_unit': fields.float(
            'Unit Price', required=True, 
            digits_compute= dp.get_precision('Product Price'), 
            readonly=True, states={'draft': [('readonly', False)]}),
        'price_subtotal': fields.float(
            'Subtota', required=True, 
            digits_compute=dp.get_precision('Product Price'), 
            readonly=True, states={'draft': [('readonly', False)]}),
        #'price_subtotal': fields.function(
        #    _amount_line, string='Subtotal', 
        #    digits_compute= dp.get_precision('Account')),
        #'price_reduce': fields.function(_get_price_reduce, type='float', 
        #    string='Price Reduce', 
        #    digits_compute=dp.get_precision('Product Price')),
        'tax_id': fields.many2many(
            'account.tax', 'sale_order_tax', 'order_line_id', 'tax_id', 
            'Taxes', readonly=True, states={'draft': [('readonly', False)]}),
        #'address_allotment_id': fields.many2one('res.partner', 
        #    'Allotment Partner',
        #    help="A partner to whom the particular product was allotment."),
        'product_uom_qty': fields.float(
            'Quantity', digits_compute= dp.get_precision('Product UoS'),
            required=True, readonly=True, 
            states={'draft': [('readonly', False)]}),
        'product_uom': fields.many2one(
            'product.uom', 'Unit of Measure ', required=True, readonly=True, 
            states={'draft': [('readonly', False)]}),
        'product_uos_qty': fields.float(
            'Quantity (UoS)', digits_compute= dp.get_precision('Product UoS'),
            readonly=True, states={'draft': [('readonly', False)]}),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'discount': fields.float(
            'Discount (%)', digits_compute= dp.get_precision('Discount'), 
            readonly=True, states={'draft': [('readonly', False)]}),
        #'th_weight': fields.float('Weight', readonly=True, 
        #    states={'draft': [('readonly', False)]}),
        #'state': fields.selection(
        #    [('cancel', 'Cancelled'),('draft', 'Draft'),
        #    ('confirmed', 'Confirmed'),('exception', 'Exception'),
        #    ('done', 'Done')],
        #    'Status', required=True, readonly=True, copy=False,),
        #'order_partner_id': fields.related(
        #    'order_id', 'partner_id', type='many2one', relation='res.partner',
        #    store=True, string='Customer'),
        #'salesman_id':fields.related('order_id', 'user_id', type='many2one', 
        #    relation='res.users', store=True, string='Salesperson'),
        #'company_id': fields.related('order_id', 'company_id', 
        #    type='many2one', relation='res.company', string='Company', 
        #    store=True, readonly=True),
        #'delay': fields.float('Delivery Lead Time', required=True, 
        #    readonly=True, states={'draft': [('readonly', False)]}),
        #'procurement_ids': fields.one2many(
        #    'procurement.order', 'sale_line_id', 'Procurements'),
    }
    
    _defaults = {
        'product_uom' : _get_uom_id,
        'discount': 0.0,
        'product_uom_qty': 1,
        'product_uos_qty': 1,
        'sequence': 10,
        #'state': 'draft',
        'price_unit': 0.0,
        #'delay': 0.0,
    }
        
        }
    _defaults = {
        #'state': lambda *x: 'draft',
        'with_sub': lambda *x: True,
        }    

class SaleOrderLine(orm.Model):
    ''' Master element for create a grouped quotation
    '''    
    _inherit = 'sale.order.line'
    
    _columns = {
        'master_order_id': fields.many2one('sale.order.line', 'Master parent'),
        }

class SaleOrderLineMaster(orm.Model):
    ''' For *many relations
    '''    
    _inherit = 'sale.order.line.master'
    
    _columns = {
        'master_child_ids': fields.one2many(
            'sale.order.line', 'master_order_id', 'Multi line'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
