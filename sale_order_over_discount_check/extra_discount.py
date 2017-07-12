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
    # Scheduler:
    # -------------------------------------------------------------------------
    def check_extra_discount_sale_order(self,, cr, uid, context=None):
        ''' Check if order line pass discount assigned to partner
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
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
        filename = '/tmp/check_discount_rate.xlsx'        
        _logger.info('Start create file %s' % filename)
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Sconti')

        # Format columns width:
        WS.set_column('A:A', 30)

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
            'bg_red': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'bg_color': '#ff420e',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'left',
                'border': 1,
                'num_format': num_format,
                }),
            'bg_green': WB.add_format({
                'bold': True, 
                'font_color': 'black',
                'bg_color': '#99cc66',
                'font_name': 'Courier 10 pitch',
                'font_size': 9,
                'align': 'left',
                'border': 1,
                'num_format': num_format,
                }),
            }

        # ---------------------------------------------------------------------
        # Search data order line:
        # ---------------------------------------------------------------------
        line_pool = self.pool.get('sale.order.line')
        line_ids = self.search(cr, uid, [
            ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
            ('order_id.mx_closed', '=', False),
            ('order_id.pricelist_order', '=', False),
            ('mx_closed', '=', False),
            ], context=None)
            
        error_range = 0.01
        
        # Write header:
        header = [
            ('Partner', xls_format_db['text']),
            ('Sconto', xls_format_db['number']),
            ('Sconto vendita', xls_format_db['number']),
            ('Sconto partner', xls_format_db['number']),
            ('Extra', xls_format_db['number']),
            ]    
        write_xls_mrp_line(WS, 0, header)
        over_ids = []
        row = 0
        for line in self.browse(
                cr, uid, line_ids, context=context):
            partner_discount_rate = line.order_id.partner_id.discount_value
            total = line.product_uom_qty * line.price_unit 
            real_total = price_subtotal
            sale_discount = total - real_total
            partner_discount = total * partner_discount_rate
            extra = sale_discount <= partner_discount 
            if extra > error_range:
                continue
            row += 1
            over_ids.append(line.id)
            data = [
                (line.order_id.partner_id.name, xls_format_db['text']),
                (partner_discount_rate, xls_format_db['number']),
                (sale_discount, xls_format_db['number']),
                (partner_discount, xls_format_db['number']),
                (extra, xls_format_db['number']),
                ]    
            write_xls_mrp_line(WS, row, data)            
        return True
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: