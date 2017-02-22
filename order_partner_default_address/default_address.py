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

class ResPartner(orm.Model):
    """ Model name: ResPartner
    """
    
    _inherit = 'res.partner'

    def no_auto_address_field(self, cr, uid, ids, context=None):
        ''' Remove default for this partner
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        address_ids = self.search(cr, uid, [
            ('parent_id', '=', ids[0]),
            ('is_address', '=', True),
            ('auto_address', '=', True),
            ], context=context)
        
        # Remove previous check:    
        if address_ids:
            self.write(cr, uid, address_ids, {
                'auto_address': False,
                }, context=context)    
        return True        
        
    def set_auto_address_field(self, cr, uid, ids, context=None):
        ''' Set as default address for this partner
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        parent_id = current_proxy.parent_id.id
        address_ids = self.search(cr, uid, [
            ('parent_id', '=', parent_id),
            ('is_address', '=', True),
            ('auto_address', '=', True),
            ], context=context)
        
        # Remove previous check:    
        if address_ids:
            self.write(cr, uid, address_ids, {
                'auto_address': False,
                }, context=context)    
        
        # Write check on this:
        return self.write(cr, uid, ids, {
            'auto_address': True,
            }, context=context)    
        
    _columns = {
        'auto_address': fields.boolean('Auto address', 
            help='Set up as default oder address when choose this partner'),
    }
    
class SaleOrder(orm.Model):
    ''' Manage delivery in header
    '''
    _inherit = 'sale.order'
    
    # Override onchange for reset address name
    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        res = super(SaleOrder, self).onchange_partner_id(
            cr, uid, ids, part, context=context)

        partner_pool = self.pool.get('res.partner')
        address_id = False
        if part:
            address_ids = partner_pool.search(cr, uid, [
                ('parent_id', '=', part),
                ('is_address', '=', True),
                ('auto_address', '=', True),
                ], context=context)
            if address_ids:
                address_id = address_ids[0]    
        
        # Reset value if not present    
        res['value']['destination_partner_id'] = address_id
        res['value']['invoice_partner_id'] = False
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
