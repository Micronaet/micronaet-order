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
import shutil
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
            return '%s-%s-%s' % (
                 value[:4],
                 value[4:6],
                 value[6:8])
        except:
            return False         

    def _csv_float(self, value):
        ''' Return remove . and / 10.000
        '''
        try:
            return float(value.replace('.', '')) / 10000
        except:
            return 0.0
                 
    
    # Virtual procedure:
    def _csv_import_order(self, cr, uid, code, context=None):
        ''' Import procedure that will be called from modules (depend on this)
            code is the code of element to load (data.xml of every new mod.)
            Importatione will be as data in table
        '''
        if code != 'company2':
            return super(CsvImportOrderElement, self)._csv_import_order(
                cr, uid, code, context=context)
        
        # ---------------------------------------------------------------------
        #                      Company 1 Import procedure:
        # ---------------------------------------------------------------------
        item_ids = self.search(cr, uid, [
            ('code', '=', 'company2')], context=context)
        if not item_ids:
            _logger.error(
                'Import code not found: company2 (record deleted?)')
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
        historypath = os.path.join(filepath, 'history') # TODO param
        filemask = item_proxy.filemask
        partner_id = item_proxy.partner_id.id
        code_mapping = {}
        for mapping in item_proxy.mapping_ids:
            code_mapping[mapping.name] = mapping.product_id.id

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
        order_list = []
        for f in os.listdir(filepath):
            if os.path.isfile(os.path.join(filepath, f)) and f.startswith(
                    filemask) and f.endswith('zip'):
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
            historyname = os.path.join(historypath, f)
            _logger.info('Read file: %s' % filename)
            
            # TODO: 
            f1 = 'orte_fia.csv' 
            f2 = 'orri_fia.csv' 
            f3 = 'orag_fia.csv' # not used
            fn1 = os.path.join(filepath, f1)
            fn2 = os.path.join(filepath, f2)
            fn3 = os.path.join(filepath, f3)
            # Delete if present:
            try: 
                os.remove(fn1)
            except:
                pass
            try: 
                os.remove(fn2)
            except:
                pass
            try: 
                os.remove(fn3)
            except:
                pass                
            # Unzip in 3 files:
            os.shell('unzip %s -d %s' (
                filename, filepath))
                
            move_history = True
            
            # -----------------------------------------------------------------
            # Header file:
            # -----------------------------------------------------------------
            f1_in = open(fn1, 'r')
            i = 0
            order_id = False
            for line in f1_in:
                i += 1
                if i != 2:
                    continue
                    
                # Read header from file:
                line = line.strip()
                line = line.split(';')
                
                partner_code = line[4]
                date_order = self._csv_format_date(line[6])
                #11 vendita
                agent_code = line[13]
                client_order_ref = line[15] # note
                # max 16
                dest_description = line[18]
                dest_address = line[19]
                dest_cap = line[20]
                dest_city = line[21]
                dest_province = line[22]
                pay_code = line[27]

                # -------------------------------------------------------------
                # Create header:
                # -------------------------------------------------------------
                # Partner:
                if not partner_code: 
                    move_history = False
                    error += '''
                        File: %s no partner code %s<br/>\n''' % (
                            filename, partner_code)
                    break
            
                partner_ids = partner_pool.search(cr, uid, [
                    ('is_company', '=', True),
                    ('sql_customer_code', '=', partner_code),
                    ], context=context)
                if not partner_ids:
                    move_history = False
                    error += '''
                        File: %s partner ID from code %s 
                        not found in ODOO<br/>\n''' % (
                            filename, partner_code)
                    break                                    
                partner_id = partner_ids[0]

                # Agent:
                if not agent_code: 
                    error += '''
                        File: %s agent not present, code %s<br/>\n''' % (
                            filename, agent_code)
                    break
            
                agent_ids = partner_pool.search(cr, uid, [
                    ('sql_supplier_code', '=', agent_code),
                    ], context=context)
                if agent_ids:
                    agent_id = agent_ids[0]
                
                    error += '''
                        File: %s agent ID from code %s 
                        not found in ODOO<br/>\n''' % (
                            filename, agent_code)
                else:
                    agent_id = False
                
                # Order
                order_ids = order_pool.search(cr, uid, [
                    ('client_order_ref', '=', client_order_ref),
                    ], context=context)

                if order_ids and len(order_ids) == 1:
                    order_id = order_ids[0]
                else:
                    data = partner_pool.onchange_partner_id(
                        cr, uid, False, partner_id, context=context).get(
                            'value', {})
                    
                    data.update({
                        'partner_id': partner_id,
                        'client_order_ref': client_order_ref,
                        'mx_agent_id': agent_id,
                        'date_order': date_order,
                        })
                    order_id = order_pool.create(cr, uid, data, context=context)
                    
                break
                
            f1_in.close()
            if not order_id:
                continue # next file
            

            # -----------------------------------------------------------------
            # Line file:
            # -----------------------------------------------------------------
            f2_in = open(fn2, 'r')

            i = 0
            for line in f1_in:
                i += 1
                if i < 2: # jump header
                    continue
                line = line.strip()
                line = line.split(';')
                
                row_type = line[6] # R (data)
                if row_type != 'R':
                    # There's other row (description)
                    pass
                    
                product_code = line[8]
                product_uom = line[10]
                product_uom_qty = line[11]
                price = line[12]
                vat = line[13]
                discount_scale = line[15]
                deadline = self._csv_format_date(line[18])
                # parcel 22
                # parcel q 23
            
            f2_in.close()    

            # -----------------------------------------------------------------
            # Agent file:
            # -----------------------------------------------------------------
            #f3_in = open(fn3, 'r')
            #f3_in.close()
            # XXX not used
                
                        # Create order:
                        if destination_code: 
                            destination_ids = partner_pool.search(cr, uid, [
                                ('parent_id', '=', partner_id),
                                ('csv_import_code', '=', destination_code),
                                ], context=context)
                            if destination_ids:
                                destination_partner_id = destination_ids[0]
                            else:
                                move_history = False
                                error += '''
                                    File: %s destination code %s 
                                    not found in ODOO<br/>\n''' % (
                                        filename,
                                        destination_code,
                                        ) # XXX continue without destination
                        else:
                            move_history = False
                            error += '''
                                File: %s destination code %s 
                                not found in file<br/>\n''' % (
                                    f,
                                    destination_code,
                                    ) # XXX continue without destination
                        order_ids = order_pool.search(cr, uid, [
                            ('client_order_ref', '=', number),
                            ('partner_id', '=', partner_id),
                            ], context=context)
                        
                        if order_ids: # on same order:
                            order_id = order_ids[0]
                            
                            # delete all previous line:
                            line_unlink_ids = line_pool.search(cr, uid, [
                                ('order_id', '=', order_id)], context=context)
                            if line_unlink_ids:    
                                line_pool.unlink(cr, uid, line_unlink_ids, 
                                    context=context)
                                _logger.warning(
                                    'Delete all previous line: %s' % (
                                        len(line_unlink_ids), ))

                            # move parent log:
                            order_pool.write(cr, uid, order_id, {
                                'importation_id': importation_id,
                                }, context=context)                            
                        else:
                            try:
                                onchange_data = order_pool.onchange_partner_id(
                                    cr, uid, [], partner_id, context=context)[
                                        'value']
                            except:
                                error += '''
                                    Onchange partner data not 
                                    'present in order %s!''' % number
                                onchange_data = {} # error
                                            
                            onchange_data.update({
                                'importation_id': importation_id,
                                'partner_id': partner_id,
                                #'date_order': order_date,
                                'date_deadline': date_deadline,
                                'client_order_ref': number,
                                'destination_partner_id':  
                                    destination_partner_id,                                
                                })
                            order_id = order_pool.create(
                                cr, uid, onchange_data, context=context)
                    
                    elif line[0] == 'r': 
                        # -----------------------------------------------------
                        #                 Details:
                        # -----------------------------------------------------
                        if not order_id: 
                            move_history = False
                            error += 'File: %s header not created<br/>\n' % (
                                f)
                            continue # next order
                            
                        # detail data:
                        sequence = line[8]
                        ean = line[9]
                        # destination EAN
                        product_code = line[10]
                        product_customer = line[11]
                        description = line[12]
                        product_uom_qty = self._csv_float(line[13])
                        price_unit = self._csv_float(line[14])
                 
                        # Product:
                        # XXX Problem with spaces (1 not 3)
                        product_ids = product_pool.search(cr, uid, ['|', '|',
                            ('default_code', '=', product_code),
                            # TODO remove:
                            ('default_code', '=', product_code.replace(
                                ' ', '  ')),
                            ('default_code', '=', product_code.replace(
                                ' ', '   ')),
                            ], context=context)
                            
                        if product_ids:
                            product_id = product_ids[0]                        
                        else:
                            # Try search in mapping code:
                            product_id = code_mapping.get(
                                product_customer, False)
                            if not product_id:    
                                move_history = False
                                error += \
                                    '%s. File: %s no product: %s>%s<br/>\n' % (
                                        counter,
                                        f, 
                                        product_customer, 
                                        product_code,
                                        )
                                continue # jumnp all order # TODO delete order?    

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
                            'date_deadline': date_deadline,
                            # TODO discount, scale vat ecc.
                            }
                        # Search sequence for update?    
                        #line_ids = line_pool.search(cr, uid, [
                        #    ('order_id', '=', order_id),
                        #    ('sequence', '=', sequence),
                        #    ], context=context)
                        #if line_ids:
                        #    line_pool.write(cr, uid, line_ids[0], data, 
                        #        context=context)    
                        #else:    
                        line_pool.create(cr, uid, data, context=context)    
                        _logger.info('Create line: %s' % data)
                    
                    elif line[0] == 'c': # comment:
                        # -----------------------------------------------------
                        #                 Footer:
                        # -----------------------------------------------------
                        note += line[9]
                    
                    else:
                        move_history = False
                        error += 'Type line not found: %s\n' % line[0]
                        continue
                    
                except:
                    # Generic record error:
                    error += '%s. %s<br/>\n' % (counter, sys.exc_info(), )
                    
            # Update with coment once ad the end:
            # XXX Note not used!
            #order_pool.write(cr, uid, order_id, {
            #    'text_note_post': note,
            #    }, context=context)
                
            # History file if not error:
            if move_history:
                _logger.info('History file: %s > %s' % (
                    filename, historyname))
                shutil.move(filename, historyname)

        if error:
            log_pool.write(cr, uid, importation_id, {
                'error': error,
                }, context=context)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Log importation',
            'res_model': 'log.importation',
            'res_id': importation_id,
            'view_type': 'form',
            'view_mode': 'form',
            #'view_id': view_id,
            #'target': 'new',
            #'nodestroy': True,
            }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
