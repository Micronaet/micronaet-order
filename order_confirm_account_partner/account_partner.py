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
    
    # -------------------------------------------------------------------------
    #                 Override confirm workflow action:
    # -------------------------------------------------------------------------
    def action_button_confirm(self, cr, uid, ids, context=None):
        ''' Override button for check partner accounting status
        '''        
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        if order_proxy.partner_id.sql_customer_code:
            return super(SaleOrder, self).action_button_confirm(
                cr, uid, ids, context=context)        
        
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(cr, uid, 
            'xmlrpc_operation_partner', 
            'view_insert_res_partner_form')[1]
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer mandatory'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': order_proxy.partner_id.id,
            'res_model': 'res.partner',
            'view_id': view_id, 
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }        
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
