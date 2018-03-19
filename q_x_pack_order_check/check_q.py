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
    
    def dummy_action(self, cr, uid, ids, context=None):
        ''' Nothing
        '''
        return True
        
    def _check_pack_error_q_x_pack(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for sol in self.browse(cr, uid, ids, context=context):
            product = sol.product_id
            q_x_pack = product.q_x_pack
            res[sol.id] = {
                'error_pack': False,
                'product_q_x_pack': q_x_pack,
                }
            if not product:
                continue

            product_uom_qty = sol.product_uom_qty
            if round(product_uom_qty, 0) != product_uom_qty or not q_x_pack:
                continue
            
            if product_uom_qty % q_x_pack != 0:
                res[sol.id]['error_pack'] = True # no correct split 
        return res
        
    _columns = {
        'error_pack': fields.function(
            _check_pack_error_q_x_pack, method=True, 
            type='boolean', string='Error pack', 
            store=False, multi=True, readonly=True),
        'product_q_x_pack': fields.function(
            _check_pack_error_q_x_pack, method=True, 
            type='integer', string='Q. x imb.',
            help='Q x imb. per questo prodotto', 
            store=False, multi=True, readonly=True),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
