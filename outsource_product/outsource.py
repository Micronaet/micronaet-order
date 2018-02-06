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
import xmlrpclib
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

class ProductProductOutsource(orm.Model):
    """ Model name: Out source Product
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'outsource': fields.boolean('Outsource', 
            help='Product made or buyed from other company'),
        'default_code_linked': fields.char('Code linked', size=64),
        
        # TODO New management not yet implemented:
        'marketed': fields.boolean('Marketed', 
            help='Product marketed from another company database'),
        # TODO company DB?
        }

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """    
    _inherit = 'res.company'
    
    def get_outsource_parameters(self, cr, uid, context=None):
        ''' Read company parameters
        '''
        company_ids = self.search(cr, uid, [], context=context)
        return self.browse(cr, uid, company_ids, context=context)[0]

    def get_outsource_xmlrpc_socket(self, cr, uid, context=None):
        ''' Return socket for XMLRPC call
        '''
        param = self.get_outsource_parameters(cr, uid, context=context)
        db = param.outsource_db  
        username = param.outsource_username
        password = param.outsource_password
        
        sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/common' % (
            param.outsource_hostname, param.outsource_port))
        
        user_id = sock.login(db, username, password)

        sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object' % (
            param.outsource_hostname, param.outsource_port))

        return (db, user_id, password, sock)
    
    _columns = {
        'outsource_management': fields.boolean('XMLRPC Outsource management', 
            help='If is remote company no XMLRPC connection'),

        'outsource_db': fields.char('XMLRPC DB name', size=80),
        'outsource_hostname': fields.char('XMLRPC Hostname', size=80),
        'outsource_port': fields.integer('XMLRPC Port'),
        'outsource_username': fields.char('XMLRPC Username', size=80),
        'outsource_password': fields.char('XMLRPC Password', size=80),
        'outsource_product_mask': fields.char(
            'Mask', size=10, help='Mask for product in other DB'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
