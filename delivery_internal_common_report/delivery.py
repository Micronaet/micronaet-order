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
from openerp import SUPERUSER_ID #, api
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

    def open_detailed_order(self, cr, uid, ids, context=None):
        ''' Open detailed order popup
        '''
        context = context or {}
        # Choose form:
        try:        
            model_pool = self.pool.get('ir.model.data')
            form_view = model_pool.get_object_reference(
                cr, uid, 'delivery_todo_report', 
                'view_sale_order_delivery_form')[1]
        except:
            tree_view = False        

        return {
            'type': 'ir.actions.act_window',
            'name': 'Order',
            'res_model': 'sale.order',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'views': [
                (form_view or False, 'form'), 
                ],
            #'domain': [('id', 'in', item_ids)],
            'target': 'new',
            'context': {'minimal_view': True},
            }
            
    def open_original(self, cr, uid, ids, context=None):
        ''' Open original order
        '''
        return {
            'type': 'ir.actions.act_window',
            'name': 'Order',
            'res_model': 'sale.order',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            #'domain': [('product_id', 'in', ids)],
            }
        
    def reset_print(self, cr, uid, ids, context=None):
        ''' Called at the end of report to reset print check
        '''
        sale_ids = self.search(
            cr, uid, [('print', '=', True)], context=context)
        self.write(
            cr, uid, sale_ids, {'print': False})     
        return True
        
    # Procedure to update
    def force_parameter_for_delivery(self, cr, uid, ids, context=None):
        ''' Compute all not closed order for delivery
        '''        
        return self.scheduled_check_close_order(cr, uid, context=context)

    def force_parameter_for_delivery_one(self, cr, uid, ids, context=None):
        ''' Compute all not closed order for delivery
        '''        
        context = context or {}
        context['force_one'] = ids[0]
        return self.scheduled_check_close_order(cr, uid, context=context)

    # -----------------
    # Scheduled events:
    # -----------------
    def scheduled_check_close_order(self, cr, uid, context=None):
        ''' Override original procedure for write all producted
        '''
        # Function that will be overrided!!!
        return
    
    # Button event:
    def to_print(self, cr, uid, ids, context=None):
        header_mod = self.write(cr, uid, ids, {
            'print': True}, context=context)
        return True

    def no_print(self, cr, uid, ids, context = None):
        header_mod = self.write(cr, uid, ids, {
            'print': False}, context=context)
        return True

    def _function_get_remain_order(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = [
                line.id for line in order.order_line if line.delivery_oc > 0]
                #if line.product_uom_qty > line.delivered_qty
        return res

    _columns = {
        'all_produced': fields.boolean('All produced'),
        'print': fields.boolean('To Print'),

        # Total:
        'delivery_amount_b': fields.float('Amount B', digits=(16, 2)),             
        'delivery_amount_s': fields.float('Amount S', digits=(16, 2)),

        'delivery_ml_total': fields.float('m/l tot', digits=(16, 2)),             
        'delivery_ml_partial': fields.float('m/l part', digits=(16, 2)),
        'delivery_vol_total': fields.float('vol. tot', digits=(16, 2)),
        'delivery_vol_partial': fields.float('vol. part', digits=(16, 2)),             

        'remain_order_line': fields.function(_function_get_remain_order, 
            method=True, type='one2many', string='Residual order line', 
            relation='sale.order.line', store=False), 
        }

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """
    _inherit = 'sale.order.line'
    
    def nothing(self, cr, uid, ids, context=None):
        '''  do nothing
        '''
        return True

    _columns = {
        'mrp_production_state': fields.selection([
            ('delivered', 'Delivered'),
            ('produced', 'All produced'),
            ('partial', 'Partial deliver'),
            ('no', 'Nothing to deliver'),
            ], 'Production state', readonly=False),
        
        'delivery_oc': fields.float('OC remain', digits=(16, 2)),     
        'delivery_b': fields.float('B(lock)', digits=(16, 2)),     
        'delivery_s': fields.float('S(uspend)', digits=(16, 2)),             
        
        'delivery_ml_total': fields.float('m/l tot', digits=(16, 2)),             
        'delivery_ml_partial': fields.float('m/l part', digits=(16, 2)),
        'delivery_vol_total': fields.float('vol. tot', digits=(16, 2)),             
        'delivery_vol_partial': fields.float('vol. part', digits=(16, 2)),
        }

    _defaults = {
        'mrp_production_state': lambda *x: 'no',            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
