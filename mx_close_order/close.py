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

class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """
    _inherit = 'sale.order'

    #def get_write_close_line(self, line):
    #    ''' Internal procedure for close (overrided for mrp line)
    #    '''
    def unlock_closed_order(self, cr, uid, ids, context=None):
        ''' Unlock order 
        '''
        assert len(ids) == 1, 'Works only with one order!'
        
        self.write(cr, uid, ids, {
            'mx_closed': False,
            }, context=context)
            
        return True
    
    # Scheduled events:
    def scheduled_check_close_order(self, cr, uid, context=None):
        ''' Check closed order (completely delivered)
        '''
        # ------------------------------
        # Close all pricelist confirmed:
        # ------------------------------
        sol_pool = self.pool.get('sale.order.line')
        _logger.info('Start setup order as closed')
        # Pricelist order are set to closed:        
        order_ids = self.search(cr, uid, [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', False),
            ('pricelist_order', '=', True),
            ], context=context)
        if order_ids:    
            self.write(cr, uid, order_ids, {
                'mx_closed': True,
                #'all_produced': True,
                }, context=context) 
        _logger.info('Update order not closed but pricelist (# %s)' % len(
            order_ids))

        # -----------------------------------------------
        # Force produced line and closed in closed order: 
        # -----------------------------------------------
        #TODO temp?!?
        order_ids = self.search(cr, uid, [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', True),
            ], context=context)            
        _logger.info('Order closed: %s' % len(
            order_ids))
        line_ids = sol_pool.search(cr, uid, [
            ('order_id', 'in', order_ids),
            ], context=context)
        if line_ids:
            sol_pool.write(cr, uid, line_ids, {
                'mx_closed': True,
                #'all_produced': True,
                }, context=context) 
        _logger.info('Close lines: %s' % len(
            line_ids))

        # --------------------------
        # TODO check Forecast order:
        # --------------------------
        
        # -------------------------
        # Check line in order open:        
        # -------------------------
        order_ids = self.search(cr, uid, [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', False),
            #('pricelist_order', '=', False), # not necessary
            ], context=context)            
        _logger.info('Check open order: %s' % len(
            order_ids))
           
        close_ids = []    
        for order in self.browse(cr, uid, order_ids, context=context):
            to_close = True
            for line in order.order_line:
                if line.product_uom_qty - line.delivered_qty > 0.0:
                    to_close = False
                    break
            if to_close:
               close_ids.append(order.id)
        if close_ids:
            self.write(cr, uid, close_ids, {
                'mx_closed': True
                }, context=context)
            _logger.info('Closed now: %s' % len(
                close_ids))
        return True        
    
    _columns = {
        'mx_closed': fields.boolean('MX closed'),
        }

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """    
    _inherit = 'sale.order.line'
    
    _columns = {
        'mx_closed': fields.boolean('Line closed'),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
