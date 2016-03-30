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

    # Button force close:
    def force_close_residual_order(self, cr, uid, ids, context=None):
        ''' Force order and line closed:
        '''
        assert len(ids) == 1, 'Force only one order a time'        
        order_proxy = self.browse(cr, uid, ids, context=context):

        # --------------------------------------
        # Read data for log and get information:
        # --------------------------------------
        import pdb; pdb.set_trace()
        html_log = ''
        line_ids = []
        for line in order_proxy.order_line:
            if not line.mx_close:
                line_ids.append(line.id)
                html_log += '''
                    <tr><td>%s</td><td>%s</td></tr>\n''' % (
                        line.product_id.default_code,
                        line.product_uom_qty - line.product_uom_delivered_qty,
                        )
        
        # -----------
        # Force line:
        # -----------
        sol_pool.write(cr, uid, line_ids, {
            'mx_close': True,
            'forced_close': True,            
            }, context=context)
        
        # -------------
        # Force header:
        # -------------
        self.write(cr, uid, ids, {
            'mx_close': True,
            'forced_close': True,            
            }, context=context)
        
        # --------------------------
        # Log message for operation:
        # --------------------------
        if html_log:
            message = _('''
                <table>
                    <tr><td>Prod.</td><td>Q.</td></tr>
                    %s
                </table>
                ''') % html_log
                
            # Send message
            # TODO
        return True
        
    _columns = {
        'forced_close': fields.boolean('Forced close', 
            help='Order force closed'),
    }

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """    
    _inherit = 'sale.order.line'

    _columns = {
        'forced_close': fields.boolean('Forced close', 
            help='Order force closed'),
    }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
