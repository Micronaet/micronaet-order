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
    
    def _csv_format_c2_code(self, value):
        ''' 000600001 > 06.00001
        '''
        try:
            return '%s.%s' % (
                 value[2:4],
                 value[4:],
                 )
        except:
            return False    
                 
    def _csv_format_c2_date(self, value, separator=False):
        ''' Return correct date from YYYMMDD
        '''
        try:
            return '%s-%s-%s' % (
                 value[4:8],
                 value[2:4],
                 value[:2])
        except:
            return False         

    def _csv_c2_float(self, value):
        ''' Return remove . and / 10.000
        '''
        try:
            return float(value.replace(',', '.'))
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
        pay_pool = self.pool.get('account.payment.term')
        
        # ---------------------
        # Read parametric data:
        # ---------------------
        item_proxy = self.browse(cr, uid, item_ids, context=context)[0]
        _logger.info('Start import %s order' % (item_proxy.name))

        filepath = os.path.expanduser(item_proxy.filepath)
        historypath = os.path.join(filepath, 'history') # TODO param
        filemask = item_proxy.filemask
        company_tag = item_proxy.company_tag

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
            f1 = 'orte_%s.csv' % company_tag
            f2 = 'orri_%s.csv' % company_tag
            f3 = 'orag_%s.csv' % company_tag
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
            os.system('unzip \'%s\' -d %s' % (
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
                
                partner_code = self._csv_format_c2_code(line[4])
                date_order = self._csv_format_c2_date(line[6])
                #11 vendita
                agent_code = line[14]
                client_order_ref = line[16] # note
                # max 16
                dest_description = line[19] or ''
                dest_address = line[20] or ''
                dest_cap = line[21] or ''
                dest_city = line[22] or ''
                dest_province = line[23] or ''       
                pay_code = line[28] or ''

                text_note_post = '%s\n%s\n%s %s (%s)' % (
                    dest_description,
                    dest_address,
                    dest_cap,
                    dest_city,
                    dest_province,
                    )                    

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
                agent_id = False
                if not agent_code:                 
                    error += '''
                        File: %s agent not present, code %s<br/>\n''' % (
                            filename, agent_code)
                else:                
                    agent_ids = partner_pool.search(cr, uid, [
                        ('sql_supplier_code', '=', agent_code),
                        ], context=context)
                    if agent_ids:
                        agent_id = agent_ids[0]
                    else:
                        error += '''
                            File: %s agent ID from code %s 
                            not found in ODOO<br/>\n''' % (
                                filename, agent_code)

                # Payment term:
                payment_term_id = False                    
                if pay_code:
                    pay_ids = pay_pool.search(cr, uid, [
                        ('import_id', '=', pay_code)], context=context)
                    if pay_ids:
                        payment_term_id = pay_ids[0]
                    else:                         
                        error += '''
                            File: %s pay code %s 
                            not found in ODOO<br/>\n''' % (
                                filename, pay_code)
                    
                # Order
                order_ids = order_pool.search(cr, uid, [
                    ('client_order_ref', '=', client_order_ref),
                    ('partner_id', '=', partner_id),
                    # TODO payment
                    ], context=context)

                if order_ids and len(order_ids) == 1:
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

                else:
                    data = order_pool.onchange_partner_id(
                        cr, uid, False, partner_id, context=context).get(
                            'value', {})
                            
                    if payment_term_id:
                        # TODO log difference!!!!!!!
                        data['payment_term_id'] = payment_term_id
                        data['payment_term'] = payment_term_id # double!!

                    data.update({
                        'partner_id': partner_id,
                        'client_order_ref': client_order_ref,
                        'mx_agent_id': agent_id,
                        'date_order': date_order,
                        'text_note_post': text_note_post,                        
                        })
                    order_id = order_pool.create(
                        cr, uid, data, context=context)                    
                break
                
            f1_in.close()
            if not order_id:
                continue # next file

            # move parent log:
            order_pool.write(cr, uid, order_id, {
                'importation_id': importation_id,
                }, context=context)                            
            
            # -----------------------------------------------------------------
            # Line file:
            # -----------------------------------------------------------------
            f2_in = open(fn2, 'r')

            i = 0
            for line in f2_in:
                i += 1
                if i < 2: # jump header
                    continue
                line = line.strip()
                line = line.split(';')
                
                row_type = line[6] # R (data)
                if row_type != 'R':
                    # There's other row (description)
                    pass
                    
                default_code = line[8]
                #product_uom = line[10] # TODO use product one's
                product_uom_qty = self._csv_c2_float(line[11])
                price_unit = self._csv_c2_float(line[12])
                vat = line[13] # >>> taxes_ids!!!
                discount_scale = line[15]
                date_deadline = self._csv_format_c2_date(line[18])
                sequence = line[89]
                # TODO doesn't work:
                if i == 2: # update date dedaline in header
                    order_pool.write(cr, uid, order_id, {
                        'date_dadline': date_deadline,
                        }, context=context) 
                
                # XXX parcel 22  # parcel q 23

                # Product:
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code),
                    ], context=context)
                if product_ids:
                    product_id = product_ids[0]                        
                else:
                    # Try search in mapping code:
                    #product_id = code_mapping.get(
                    #    product_customer, False)
                    #if not product_id:    
                    move_history = False
                    error += \
                        '%s. File: %s no product code: %s<br/>\n' % (
                            i, f, default_code)
                    continue # import other only for log (order incomplete!)
                
                product_proxy = product_pool.browse(
                    cr, uid, product_id, context=context)
                # TODO onchange for calculate all other fields?????????????????
                data = line_pool.on_change_multi_discount(
                    cr, uid, False, discount_scale, context=context).get(
                        'value', {})

                data.update({                    
                    'order_id': order_id,
                    'sequence': sequence,
                    'product_id': product_id,
                    'product_uom_qty': product_uom_qty,
                    'price_unit': price_unit,
                    'name': product_proxy.name,
                    'product_uom': product_proxy.uom_id.id,
                    'date_deadline': date_deadline,
                    'multi_discount_rates': discount_scale,
                    # TODO discount, scale vat ecc.
                    })
                #import pdb; pdb.set_trace()
                try:    
                    tax_id = product_proxy.taxes_id[0].id
                    if tax_id: 
                        data['tax_id'] = [(6, 0, (tax_id, ))]
                except:
                    pass # TODO raise error    

                line_pool.create(cr, uid, data, context=context)
                _logger.info('Create line: %s' % data)            
            f2_in.close()    

            # -----------------------------------------------------------------
            # Agent file:
            # -----------------------------------------------------------------
            #f3_in = open(fn3, 'r')
            #f3_in.close()
            # XXX not used
                    
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
