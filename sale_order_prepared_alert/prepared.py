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
import xlsxwriter
import pickle
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
    
    _pickle_order_line = '~/pickle_order_prepared_check.dmp'
    
    # -------------------------------------------------------------------------
    # Scheduler:
    # -------------------------------------------------------------------------
    def check_near_prepared_sale_order(self, cr, uid, context=None):
        ''' Check if order line pass discount assigned to partner
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def get_yet_used():
            ''' Read store file
            '''       
            filename = os.path.expanduser(self._pickle_order_line)
            try:
                f = open(filename, 'rb')
                res = pickle.load(f)                
                f.close()
                return res
            except:
                return []    
            
        def set_yet_used(yet_used):
            ''' Save store file
            '''            
            filename = os.path.expanduser(self._pickle_order_line)
            f = open(filename, 'wb')
            pickle.dump(yet_used, f)
            f.close()
            return True
            
        def write_xls_mrp_line(WS, row, line):
            ''' Write line in excel file
            '''
            col = 0
            for record in line:
                if len(record) == 2: # Normal text, format
                    WS.write(row, col, *record)
                else: # Rich format
                    WS.write_rich_string(row, col, *record)
                col += 1
            return True


        # ---------------------------------------------------------------------
        # Start prepare XLS file:
        # ---------------------------------------------------------------------
        remain_rate = 0.20 # 20% remain on total
        
        error_range = 0.01
        num_format = '0.#0'
        #num_format_0 = '0.#0'

        filename = '/tmp/check_near_prepared.xlsx'        
        _logger.info('Start create file %s' % filename)
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Da chiudere')
        WS1 = WB.add_worksheet('Segnalati in precedenza')

        # Format columns width:
        WS.set_column('A:A', 15)
        WS.set_column('B:B', 30)
        WS.set_column('C:C', 20)
        WS.set_column('D:G', 10)
        WS1.set_column('A:A', 15)
        WS1.set_column('B:B', 30)
        WS1.set_column('C:C', 20)
        WS1.set_column('D:G', 10)

        xls_format_db = {
            'header': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'font_name': 'Courier 10 pitch', # 'Arial'
                'font_size': 9,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#cfcfcf', # gray
                'border': 1,
                }),
            'text': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'left',
                'border': 1,
                }),                    
            'number': WB.add_format({
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
                
            # -------------------------------------------------------------
            # With text color:
            # -------------------------------------------------------------
            'heat1': WB.add_format({
                'font_color': 'black',
                'bg_color': '#ec4e4e',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            'heat2': WB.add_format({
                'font_color': 'black',
                'bg_color': '#f69999',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            'heat3': WB.add_format({
                'font_color': 'black',
                'bg_color': '#f1bcbc',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            'heat4': WB.add_format({
                'font_color': 'black',
                'bg_color': '#f3dfdf',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            'heat5': WB.add_format({
                'font_color': 'black',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'right',
                'border': 1,
                'num_format': num_format,
                }),
            }

        # ---------------------------------------------------------------------
        # Search data order:
        # ---------------------------------------------------------------------
        order_pool = self.pool.get('sale.order')
        
        # Generate domain:
        domain = [
            ('state', 'not in', ('draft', 'cancel', 'sent')),
            ('mx_closed', '=', False),
            ]
        if 'pricelist_order' in self._columns:
            domain.append(('pricelist_order', '=', False))
        if 'forecasted_production_id' in self._columns:
            domain.append(('forecasted_production_id', '=', False))
        _logger.info('Domain: %s' % (domain, ))    
        order_ids = order_pool.search(cr, uid, domain, context=None)

        # Write header:
        header = [
            ('Ordine', xls_format_db['header']),
            ('Partner', xls_format_db['header']),
            #('Prodotto', xls_format_db['header']),
            ('OC', xls_format_db['header']),
            ('B', xls_format_db['header']),
            ('Consegnato', xls_format_db['header']),
            ('Rimanenza da consegnare', xls_format_db['header']),
            ]   
        write_xls_mrp_line(WS, 0, header)
        write_xls_mrp_line(WS1, 0, header)
        
        yet_used = get_yet_used() or []
        _logger.info('Pickle previous list: %s' % len(yet_used))
        over_ids = []
        row = 0        
        row1 = 0        
        for order in order_pool.browse(
                cr, uid, order_ids, context=context):
            # Reset total:
            total_OC = 0
            total_B = 0
            total_D = 0
            
            # Populate total:
            for line in order.order_line:
                total_OC += line.product_uom_qty
                total_B += line.product_uom_maked_sync_qty
                total_D += line.product_delivered_qty
            
            # Total analysis:
            if total_B > total_D:
                total_remain = total_OC - total_B # to deliver
            else:
                total_remain = total_OC - total_D # to deliver
            order_remain_rate = total_remain / total_OC
            if order_remain_rate > remain_rate:
                continue # order not in delivery rate area
                
            over_ids.append(line.id)
            if order_remain_rate <= 0.02:
                format_heat = xls_format_db['heat1']
            elif order_remain_rate <= 0.05:
                format_heat = xls_format_db['heat2']
            elif order_remain_rate >= 0.10:
                format_heat = xls_format_db['heat3']
            elif order_remain_rate >= 0.15:
                format_heat = xls_format_db['heat4']
            else: # 0.20
                format_heat = xls_format_db['heat5']

            ('Ordine', xls_format_db['header']),
            ('Partner', xls_format_db['header']),
            #('Prodotto', xls_format_db['header']),
            ('OC', xls_format_db['header']),
            ('B', xls_format_db['header']),
            ('Consegnato', xls_format_db['header']),
            ('Rimanenza da consegnare', xls_format_db['header']),
                
            data = [
                (order.name, xls_format_db['text']),
                (order.partner_id.name, xls_format_db['text']),
                (total_OC, xls_format_db['number']),
                (total_B, xls_format_db['number']),
                (total_D, xls_format_db['number']),
                (order_remain_rate, format_heat),
                ]    
            write_xls_mrp_line(WS_use, position, data)            

        # Write pickle for current selection:
        set_yet_used(over_ids)
        _logger.info('Save pickle order list: %s' % len(over_ids))
        WB.close()

        # ---------------------------------------------------------------------
        # Send mail to group:
        # ---------------------------------------------------------------------
        xlsx_raw = open(filename, 'rb').read()
        #b64 = xlsx_raw.encode('base64')
        attachments = [('order_near_delivery.xlsx', xlsx_raw)]
        
        _logger.info('Sending status via mail: %s' % filename)

        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        server_pool = self.pool.get('ir.mail_server')
        
        group_id = model_pool.get_object_reference(
            cr, uid, 
            'sale_order_prepared_alert', 
            'group_prepared_team_mail')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)

        if row: # there's record in first sheet:
            _logger.info('Mail: there are records in sheet 1')
            subject = 'Invio automatico ordini in pronta consegna: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                )
        else:
            _logger.info('No mail: empty sheet 1')
            subject = 'NESSUNA VARIAZIONE ORDINI DA CONSEGNARE: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                )            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body=_('Notifica ordini in prossima consegna.'), 
            subject=subject,
            partner_ids=[(6, 0, partner_ids)],
            attachments=attachments, 
            context=context,
            )
        return True
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
