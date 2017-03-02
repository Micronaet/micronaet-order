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

    _logfile = '/home/administrator/photo/log/order/close.log'
    
    #def get_write_close_line(self, line):
    #    ''' Internal procedure for close (overrided for mrp line)
    #    '''
    def unlock_closed_order(self, cr, uid, ids, context=None):
        ''' Unlock order 
        '''
        # TODO:
        assert len(ids) == 1, 'Works only with one order!'
        
        self.write(cr, uid, ids, {
            'mx_closed': False,
            }, context=context)
            
        return True
    
    # Scheduled events:
    def scheduled_check_close_order(self, cr, uid, context=None):
        ''' Check closed order (completely delivered)
        '''
        logfile = self._logfile
        sol_pool = self.pool.get('sale.order.line')
        
        log = []

        # ---------------------------------------------------------------------
        # Close all pricelist confirmed:
        # ---------------------------------------------------------------------
        log.append('Start setup order as closed')
        _logger.info(log[-1])
        
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
        log.append('Update order not closed but pricelist (# %s)' % len(
            order_ids))
        _logger.info(log[-1])

        # ---------------------------------------------------------------------
        # Close order line of order closed:
        # ---------------------------------------------------------------------
        #TODO temp?!?
        line_ids = sol_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('cancel', 'sent', 'draft')),
            ('order_id.mx_closed', '=', True),        
            ('mx_closed', '=', False),        
            ], context=context)
        if line_ids:
            sol_pool.write(cr, uid, line_ids, {
                'mx_closed': True,
                #'all_produced': True,
                }, context=context) 
        log.append('Close lines of closed order: %s' % len(line_ids))
        _logger.info(log[-1])

        # --------------------------
        # TODO check Forecast order:
        # --------------------------
        
        # ---------------------------------------------------------------------
        # Check line in order open (qty VS delivered):
        # ---------------------------------------------------------------------
        order_ids = self.search(cr, uid, [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', False),
            ], context=context)            
        log.append('Check open order: %s' % len(order_ids))
        _logger.info(log[-1])
                   
        close_ids = [] 
        for order in self.browse(cr, uid, order_ids, context=context):
            to_close = True
            for line in order.order_line:
                if line.product_uom_qty - line.delivered_qty > 0.0:
                    to_close = False
                    break
                # TODO order line remain not closed?
            if to_close:
               close_ids.append(order.id)

        if close_ids:
            # Close order header:
            self.write(cr, uid, close_ids, {
                'mx_closed': True,
                }, context=context)
            log.append('Closed all delivered order: %s' % len(close_ids))
            _logger.info(log[-1])
            
            # Close order line:
            line_ids = sol_pool.search(cr, uid, [
                ('order_id', 'in', close_ids),
                ('mx_closed', '=', False),
                ], context=context)
            if line_ids:
                sol_pool.write(cr, uid, line_ids, {
                    'mx_closed': True,
                    }, context=context) 
                log.append(
                    'Closed all order line delivered: %s' % len(line_ids))
                _logger.info(log[-1])
        
        # Log event:  
        log_f = open(logfile, 'a')
        log_f.write('\n'.join(log))
        log_f.close()
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
