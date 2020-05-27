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

    def send_sale_order_email_check(self, cr, uid, context=None):
        ''' Generate email for check deadline status
        '''
        query = '''
            SELECT name 
            FROM res_partner 
            WHERE 
                email_invoice_id is null and 
                email is null and 
                id IN (
                    SELECT distinct partner_id 
                    FROM sale_order 
                    WHERE 
                        state not in ('cancel', 'draft', 'sent') and 
                        forecasted_production_id is null);
        '''
        cr.execute(query)
        partner_name = [item[0] for item in cr.fetchall()]        
        
        if not partner_name:    
            _logger.info('No email missed in partner with order found!')
            return True
        
        body = '<table>'    
        for name in partner_name:
            body += '''<tr><td>%s</td></tr>''' % name
        body += '</table>'
            
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------        
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        
        group_id = model_pool.get_object_reference(
            cr, uid, 
            'auto_order_deadline_check', 
            'group_order_email_report_admin')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False,
            type='email', 
            body=body, 
            subject='Partner con ordini senza mail fatturazione o mail: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            context=context,
            )
        return True    
        
    def send_sale_order_line_deadline_check(
            self, cr, uid, context=None):
        ''' Generate email for check deadline status
        '''
        if context is None:
            context = {
                'lang': 'it_IT',
                }

        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [
            ('order_id.state', 'not in', ('cancel', 'draft', 'sent')),
            ('order_id.forecasted_production_id', '=', False),
            ('order_id.mx_closed', '=', False),
            ('date_deadline', '=', False),
            ], context=context)
        # TODO check also over 365 days
        
        if not sol_ids:    
            _logger.info('No deadline order found!')
            return True
        
        body = ''    
        for line in sol_pool.browse(cr, uid, sol_ids, context=context):
            body += '''
                <tr>
                    <td>%s</td><td>%s</td><td>%s</td>
                    <td>%s</td><td>%s</td><td>%s</td>
                    
                </tr>''' % (
                    line.order_id.name,
                    line.partner_id.name,
                    line.order_id.date_order,

                    line.product_id.default_code,
                    line.name,
                    line.product_uom_qty,                
                    )
        body = '''
            <table>
                <tr>
                <td>Ordine</td><td>Partner</td><td>Data</td>
                <td>Codice</td><td>Nome</td><td>Q.</td>
                </tr>
                <tr>%s</tr>
            </table>''' % body
            
        # ---------------------------------------------------------------------
        # Send report:
        # ---------------------------------------------------------------------
        
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        
        group_id = model_pool.get_object_reference(
            cr, uid, 
            'auto_order_deadline_check', 
            'group_order_deadline_report_admin')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False,
            type='email', 
            body=body, 
            subject='Ordini senza la scadenza: %s' % (
                datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
                ),
            partner_ids=[(6, 0, partner_ids)],
            context=context,
            )
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
