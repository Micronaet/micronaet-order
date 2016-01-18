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
import csv
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
    
    _inherit = 'csv.import.order.element'
    
    def _csv_format_date(self, value):
        ''' Return correct date from YYYMMDD
        '''
        try:
            return '%s-%s-%s' (
                 value[:4],
                 value[5:7],
                 value[8:10])
        except:
            return False         
                 
    
    # Virtual procedure:
    def _csv_import_order(self, cr, uid, code, context=None):
        ''' Import procedure that will be called from modules (depend on this)
            code is the code of element to load (data.xml of every new mod.)
            Importatione will be as data in table
        '''
        if code != 'company1':
            return super(CsvImportOrderElement, self)._csv_import_order(
                cr, uid, code, context=context)
        
        # ---------------------------------------------------------------------
        #                      Company 1 Import procedure:
        # ---------------------------------------------------------------------
        item_ids = self.search(cr, uid, [
            ('code', '=', 'company1')], context=context)
        if not item_ids:
            _logger.error(
                'Import code not found: company1 (record deleted?)')
            return False    

        # Pool used:
        log_pool = self.pool.get('log.importation')
        order_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')
        partner_pool = self.pool.get('res.partner')
        partic_pool = self.pool.get('res.partner.product.partic')
        product_pool = self.pool.get('product.product')
        
        # ---------------------
        # Read parametric data:
        # ---------------------
        item_proxy = self.browse(cr, uid, item_ids, context=context)[0]
        _logger.info('Start import %s order' % (item_proxy.name))

        filepath = os.path.expanduser(item_proxy.filepath)
        filemask = item_proxy.filemask
        partner_id = item_proxy.partner_id.id

        # ------------------
        # Start log message:
        # ------------------
        importation_id = log_pool.create(cr, uid, {
            'name': 'Import Company 1 order',
            'user_id': uid,
            #'mode_id': 'order', # TODO search order element!!
            'note': False,
            'error': False,
            }, context=context)

        # Loop on files in folder:
        import pdb; pdb.set_trace()
        order_list = []
        for f in os.listdir(filepath):
            if os.path.isfile(os.path.join(filepath, f)) and f.startswith(
                    filemask) and f.endswith('csv'):
                order_list.append(f)
        order_list.sort()
        
        # -----------------------------------------------------------------
        #                      Import order:
        # -----------------------------------------------------------------            
        # Init log elements:
        error = ''
        comment = ''
        for f in order_list:
            filename = os.path.join(filepath, f)
            _logger.info('Read file: %s' % filename)
            f_in = open(filename)            
            
            # reset header / footer element:
            note = ''
            order_id = False
            destination_partner_id = False
            for line in f_in:
                try:
                    # Read as CSV:
                    line = line.strip()
                    line = line.split(';')
                    
                    if line[0] == 't': 
                        # header data:                    
                        destination_code = line[1]
                        number = line[4]
                        insert_date = self._csv_format_date(line[6])
                        order_date = self._csv_format_date(line[7]) #  TODO format date
                        
                        # Create order:
                        if destination_code: 
                            destination_ids = partner_pool.search(cr, uid, [
                                ('parent_id', '=', partner_id),
                                ('csv_import_code', '=', destination_code),
                                ], context=context)
                            if destination_ids:
                                destination_partner_id = destination_ids[0]
                            else:    
                                error += 'File: %s destination code %sno found in ODOO\n' % (
                                    filename,
                                    destination_code,
                                    ) # XXX continue without destination
                        else:
                            error += 'File: %s destination code %s no found in file\n' % (
                                filename,
                                destination_code,
                                ) # XXX continue without destination
                        order_ids = order_pool.search(cr, uid, [
                            ('client_order_ref': number)
                            ('partner_id', '=', partner_id),
                            ], context=context)
                        if order_ids: # on same order:
                            order_id = order_ids[0]
                        else:   
                            order_id = order_pool.create(cr, uid, {
                                'importation_id': importation_id,
                                'partner_id': partner_id,
                                #'date_order': order_date,
                                'client_order_ref': number,
                                'destination_partner_id': destination_partner_id,
                                }, context=context)
                    
                    elif line[0] == 'r': 
                        if not order_id: 
                            error += 'File: %s order heder not created\n' % (
                                filename)
                            continue # next order
                            
                        # detail data:
                        sequence = line[8]
                        ean = line[9]
                        # destination EAN
                        product_code = line[10]
                        product_customer = line[11]
                        description = line[12]
                        product_uom_qty = float(line[13].replace(',', '.'))
                        price_unit = float(line[14].replace(',', '.'))
                                            
                        # Product:
                        product_ids = product_pool.search(cr, uid, [
                            ('default_code', '=', product_code)], context=context)
                        if not product_ids:
                            error += 'File: %s product not found: %s\n' % (
                                filename , product_code)
                            continue # jumnp all order # TODO delete order?    

                        product_id = product_ids[0]                        
                        # Partner - product partic:
                        partic_ids = partic_pool.search(cr, uid, [
                            ('partner_id', '=', partner_id),
                            ('product_id', '=', product_id),
                            ], context=context)
                        if partic_ids:
                            partic_pool.write(cr, uid, partic_ids[0], {
                                'partner_price': price_unit,
                                'partner_code': '%s - EAN %s' % (
                                    product_customer, ean)
                                }, context=context)
                        else: # create        
                            partic_pool.create(cr, uid, {
                                'partner_id': partner_id,
                                'product_id': product_id,
                                'partner_price': price_unit,
                                'partner_code': '%s - EAN %s' % (
                                    product_customer, ean)
                                }, context=context)
                                
                        # TODO onchange for extra data??
                        data = {
                            'order_id': order_id,
                            'sequence': sequence,
                            'product_id': product_id,
                            'product_uom_qty': product_uom_qty,
                            'price_unit': price_unit,
                            'name': description,
                            # TODO discount, scale vat ecc.
                            }
                        # Search sequence for update?    
                        line_ids = line_pool.search(cr, iud, [
                            ('order_id', '=', order_id),
                            ('sequence', '=', sequence),
                            ], context=context)
                        if line_ids:
                            line_pool.write(cr, uid, line_ids[0], data, context=context)    
                        else:    
                            line_pool.create(cr, uid, data, context=context)    
                    
                    elif line[0] == 'c': # comment:
                        note += line[9]
                    
                    else:
                        error += 'Type line not found: %s\n' % line[0]
                        continue                        
                except:
                    # Generic record error:
                    error += '%s\n' % (sys.exc_info(), )
                    
            # Update with coment once ad the end:
            order_pool.write(cr, uid, order_id, {
                'text_note_post': note,
                }, context=context)
        if error:
            log_pool.write(cr, uid, importation_id, {
                'error': error,
                }, context=context)        
        return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
