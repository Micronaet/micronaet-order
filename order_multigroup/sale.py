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
    
    _defaults = {
        'master_order': lambda *x: False,
        }

class SaleOrderLine(orm.Model):
    ''' Add extra field for manage master line
    '''    
    _inherit = 'sale.order.line'
    
    # Button events:
    def write_subtotal(self, cr, uid, ids, context=None):
        ''' Calculate and write subtotal
        '''
        res = 0.0
        for item in self.browse(
                cr, uid, ids, context=context).master_child_ids:
            res += item.price_subtotal or 0.0            
        return self.write(cr, uid, ids, {
            'master_subtotal': res
            }, context=context)    
        
    _columns = {
        'master': fields.boolean('Master'),
        'master_order_id': fields.many2one('sale.order.line', 'Master parent'),
        'master_title': fields.text('Master title'),
        'master_note': fields.text('Master note'),
        'with_sub': fields.boolean('With subtotal'),
        'master_subtotal': fields.float(
            'Master subtotal', 
            digits=(16, 2)),
        'state': fields.selection( # for problem in view (not used)
            [('draft', 'Draft')], 'State'),
        }
    _defaults = {
        'state': lambda *x: 'draft',
        'with_sub': lambda *x: True,
        }    

class SaleOrderLine(orm.Model):
    ''' For *many relations
    '''    
    _inherit = 'sale.order.line'
    
    _columns = {
        'master_child_ids': fields.one2many(
            'sale.order.line', 'master_order_id', 'Multi line'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
