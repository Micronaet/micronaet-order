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
    """ Model name: Sale order line
    """    
    _inherit = 'sale.order.line'
    
    def _update_pack_from_product(self, cr, uid, ids, context=None):
        ''' Change q_x_pack in product
        '''
        line_pool = self.pool.get('sale.order.line')
        line_ids = line_pool.search(cr, uid, [
            ('product_id', 'in', ids),
            ], context=context)
        _logger.warning('Change q_x_pack in sale order line')
        return line_ids

    # -------------------------------------------------------------------------    
    # Field function:    
    # -------------------------------------------------------------------------    
    def _get_pack_from_product(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.product_id.q_x_pack or 0
        return res

    _columns = {
        'q_x_pack': fields.function(
            _get_pack_from_product, method=True, 
            type='integer', string='Q x pack', 
            store={
                'product.product':
                    (_update_pack_from_product, ['q_x_pack'], 10),
                }
            )     
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
