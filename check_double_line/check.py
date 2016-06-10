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
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
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
    
    def dummy(self, cr, uid, ids, context=None):
        ''' Dummy button event
        '''
        return True

    # ----------------
    # Function fields:
    # ----------------
    def _search_double_line(self, cr, uid, obj, name, args, context=None):
        ''' Search double
        '''
        # TODO filter only open
        ids = self.search(cr, uid, [
            ('state', 'not in', ('cancel', 'draft', 'sent')),
            ('mx_closed', '=', False),
            # TODO forecast?
            ], context=context)
        res = []
        for order in self.browse(cr, uid, ids, context=context): 
            lines = {}
            for line in order.order_line:
                key = (line.product_id, line.date_deadline)
                if key in lines:
                    lines[key] = True # other time
                else:
                    lines[key] = False # first time
                if lines[key]: # >2 time check
                    res.append(order.id)
                    break
        return [('id', 'in', res)]

    def _check_double_line(self, cr, uid, ids, fields, args, context=None):
        ''' Check if order has double lines
        '''
        res = {}
        for order in self.browse(cr, uid, ids, context=context): 
            lines = {}
            res[order.id] = {}
            esit = ''
            for line in order.order_line:
                key = (line.product_id, line.date_deadline)
                if key in lines:
                    lines[key] = True # other time
                else:
                    lines[key] = False # first time
                if lines[key]: # >2 time check
                    esit += '[%s] ' % line.product_id.default_code
            if esit:
                res[order.id]['double_line'] = True        
                res[order.id]['double_line_note'] = esit
            else:    
                res[order.id]['double_line'] = False
                res[order.id]['double_line_note'] = False                
        return res

    _columns = {
        'double_line': fields.function(
            _check_double_line, 
            fnct_search=_search_double_line,
            method=True, 
            type='boolean', string='Double line', 
            store=False, multi=True),
        'double_line_note': fields.function(
            _check_double_line, method=True, 
            type='text', string='Double line note', 
            store=False, multi=True),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
