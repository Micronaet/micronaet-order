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

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrder
    """
    
    _inherit = 'sale.order.line'
    
    # -------------------------------------------------------------------------
    # Scheduler:
    # -------------------------------------------------------------------------
    def sale_order_bom_uncheked(self, cr, uid, context=None):
        ''' Report for order not BOM checked
        '''
        # ---------------------------------------------------------------------
        # Search data order line:
        # ---------------------------------------------------------------------
        excel_pool = self.pool.get('excel.writer')

        # Generate domain:
        domain = [
            ('order_id.state', 'not in', ('draft', 'cancel', 'sent')),
            ('order_id.mx_closed', '=', False),
            ('mx_closed', '=', False),
            ]

        if 'pricelist_order' in self._columns:
            domain.append(('order_id.pricelist_order', '=', False))

        if 'forecasted_production_id' in self._columns:
            domain.append(('order_id.forecasted_production_id', '=', False))

        _logger.info('Domain: %s' % (domain, ))    
        line_ids = self.search(cr, uid, domain, context=None)

        # ---------------------------------------------------------------------
        #                              Excel:
        # ---------------------------------------------------------------------
        ws_name = 'Righe ordine'
        excel_pool.create_worksheet(ws_name)

        # Write header:
        header = ['Ordine', 'Partner', 'Prodotto']   
        width = [20, 40, 20]
        excel_pool.column_width(ws_name, width)

        # Format: 
        excel_pool.set_format()
        excel_format = {
            'title': excel_pool.get_format('title'),
            'header': excel_pool.get_format('header'),
            'text': excel_pool.get_format('text'),
            }
        
        row = 0        
        excel_pool.write_xls_line(ws_name, row, [
            'Dettaglio ordini con distinte non controllate',
            ], excel_format['title'])

        row += 1
        excel_pool.write_xls_line(ws_name, row, header, excel_format['header'])
        
        for line in self.browse(
                cr, uid, line_ids, context=context):
            row += 1
            excel_pool.write_xls_line(ws_name, row, [
                line.order_id.name, 
                line.order_id.partner_id.name,
                line.product_id.default_code,
                ], excel_format['text'])
            
        return excel_pool.send_mail_to_group(cr, uid, 
            'sale_order_bom_problem.group_order_bom_check_mail',
            'Distinte non controllate negli ordini', 
            'In allegato gli ordini aperti senza DB controllate', 
            'controllo.xlsx', 
            context=context)
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
