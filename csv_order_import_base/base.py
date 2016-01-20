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

class CsvImportOrderElement(orm.Model):
    """ Model name: CsvImportOrderTrace
        Object for save list of type of order that could be imported
        Virtual import procedure that will be overrided from all 
        extra modules
    """
    
    _name = 'csv.import.order.element'
    _description = 'CSV Order import'
    _rec_name = 'name'
    
    # Virtual procedure:
    def _csv_import_order(self, cr, uid, name, context=None):
        ''' Import procedure that will be called from modules (depend on this)
            name is the name of element to load (data.xml of every new mod.)
            Importatione will be as data in table
        '''
        return True
    
    _columns = {
        'code': fields.char('Code', size=20, required=True),
        'name': fields.char('Name', size=64, required=True),
        'filepath': fields.char('Path', size=180, required=True),
        'filename': fields.char('File name', size=80),        
        'filemask': fields.char('Mask', size=80), # Used?
        'partner_id': fields.many2one('res.partner', 'Customer'),
        'note': fields.text('Note') ,
        }

class CsvImportOrderElementMapping(orm.Model):
    """ Mapp partner code with ours
    """
    
    _name = 'csv.import.order.element.mapping'
    _description = 'CSV Order mapping import'
    _rec_name = 'name'
    
    _columns = {
        'name': fields.char('Customer code', size=20, required=True),
        'product_id': fields.many2one(
            'product.product', 'Product', required=True), 
        'item_id': fields.many2one(
            'csv.import.order.element', 'Import ref.'),
        }
    
class CsvImportOrderElement(orm.Model):
    """ Model name: CsvImportOrderTrace
        Object for save list of type of order that could be imported
        Virtual import procedure that will be overrided from all 
        extra modules
    """
    
    _inherit = 'csv.import.order.element'
    
    _columns = {
        'mapping_ids': fields.one2many(
            'csv.import.order.element.mapping', 'item_id', 
            'Code mapping'), 
        }
    
class SaleOrder(orm.Model):
    """ Link order to log
    """    
    _inherit = 'sale.order'
    
    def open_order_form_id(self, cr, uid, ids, context=None):
        '''        
        '''
        return {
            'type': 'ir.actions.act_window',
            'name': 'Imported order',
            'res_model': 'sale.order',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            }
 
        
    _columns = {
        'importation_id': fields.many2one('log.importation', 'Log link'), 
        }

class LogImportation(orm.Model):
    ''' Add *many relation field
    '''
    _inherit = 'log.importation'
    
    _columns = {
        #'order_ids': fields.one2many('sale.order', 'importation_id', 'Order'), 
        }

class ResPartner(orm.Model):
    """ Link order to log (for destination or partner)
    """    
    _inherit = 'res.partner'
    
    _columns = {
        'csv_import_code': fields.char('CSV Import code', size=10), 
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
