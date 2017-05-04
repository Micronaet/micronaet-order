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

class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """    
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    def get_company_order_residual_filter(self, cr, uid, context=None):
        ''' Read company and return parameter
        '''
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
        return (
            company_proxy.residual_order_value,
            company_proxy.residual_remain_perc,
            )
            
    def get_order_with_residual_part(self, cr, uid, context=None):
        ''' Check company parameter and return order with residual
        '''
        
        (amount_untaxed, residual_remain_perc) = \
            self.get_company_order_residual_filter(
                cr, uid, context=context)
        if not(amount_untaxed and residual_remain_perc):
            raise osv.except_osv(
                _('Parameter error'), 
                _('Setup parameters in company form!'),                
                )
        _logger.warning(
           'Company parameter, order total <= %s, remain rate: %s%s!' % (
               amount_untaxed,
               residual_remain_perc,
               '%',
               ))
        
        # -----------------------------
        # Read order residual to close:
        # -----------------------------
        # Read order not closed:
        domain = [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', False),
            ('amount_untaxed', '<=', amount_untaxed),
            # TODO forecast order?
            ]
        # for forecast order (used in production module)    
        if 'forecasted_production_id' in self._columns:
            domain.append(('forecasted_production_id', '=', False))
            
        res = []
        order_ids = self.search(cr, uid, domain, context=context)
        for order in self.browse(cr, uid, order_ids, context=context):
            residual = 0.0
            lines = []
            for line in order.order_line:
                if line.mx_closed:
                    continue
                remain = line.product_uom_qty - line.delivered_qty
                #line.product_uom_delivered_qty
                if remain <= 0.0:
                    continue
                residual += remain * line.price_subtotal / line.product_uom_qty
                lines.append(line)
                
            # Test if order need to be print:    
            if residual and residual <= order.amount_untaxed * (
                    residual_remain_perc / 100.0):     
                res.append((order, lines, residual))
                
        # Check residual information:
        return res
    
    def send_order_minimal_residual_scheduler(self, cr, uid, context=None):
        ''' Generate PDF with data and send mail
        '''    
        # Company information
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
        company_name = company_proxy.partner_id.name
        
        # Get residual list:
        res = self.get_order_with_residual_part( 
            cr, uid, context=context)

        # ---------------------------------------------------------------------
        # Report parameters:
        # ---------------------------------------------------------------------
        # Pool used:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')

        # Parameters:
        datas = {
            # Report setup:
            'model': 'sale.order',
            'active_id': False,
            'active_ids': [],
            'context': context,
            }

        report_name = 'custom_mx_profora_invoice_pdf_report'
        #report_name = 'custom_mx_profora_invoice_report'
        extension = 'pdf' # odt
        subject_mask = '%s: ordine %%s %%s ha residuo minimo' % company_name
                    
        # Get list of recipients:
        group_id = model_pool.get_object_reference(
            cr, uid, 'close_residual_order', 'group_close_residual_report')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        residual_notified_ids = []
        for order, lines, remain in res:
            if order.residual_notified:
                _logger.warning('Order yet notified: %s' % order.name)
                continue
            # Check if order is yet notified
            # -----------------------------------------------------------------
            # Generate the report
            # -----------------------------------------------------------------
            # datas update:
            datas['active_id'] = order.id
            datas['active_ids'] = [order.id]
            
            try:
                result, extension = openerp.report.render_report(
                    cr, uid, [order.id], report_name, datas, context)
                attachments = [(
                    'Order_%s.%s' % (order.name, extension),
                    result,
                    )]
            except:
                _logger.error('Error generation residual order %s [%s]' % (
                    order.name,
                    sys.exc_info(),
                    ))
                attachments = []    
                #continue # next report

            body = 'Rimanente: %s su totale: %s<br/>\n' % (
                remain,
                order.amount_untaxed,
                )
            for line in lines:
                body += 'Cod.: %s residuo: %s<br/>\n' % (
                    line.product_id.default_code or '???',
                    line.product_uom_qty - line.delivered_qty,
                    )

            # -----------------------------------------------------------------
            # Send report:
            # -----------------------------------------------------------------
            thread_pool.message_post(cr, uid, False, 
                type='email', 
                body=body, 
                subject=subject_mask % (                    
                    order.name,
                    order.partner_id.name,
                    ),
                partner_ids=[(6, 0, partner_ids)],
                attachments=attachments,#[('Completo.odt', result)], 
                context=context,
                )
            residual_notified_ids.append(order.id)    

        # Mark as notified (no more mail):            
        if residual_notified_ids:
            self.write(cr, uid, residual_notified_ids, {
                'residual_notified': True,
                }, context=context)  
            _logger.info('Marked as notified all order mailed: %s' % (
                residual_notified_ids, 
                ))
        return True    
                
    # -------------------------------------------------------------------------
    # Button force close:
    # -------------------------------------------------------------------------
    def force_close_residual_order(self, cr, uid, ids, context=None):
        ''' Force order and line closed:
        '''
        assert len(ids) == 1, 'Force only one order a time'        
        
        sol_pool = self.pool.get('sale.order.line')
        order_proxy = self.browse(cr, uid, ids, context=context)

        # --------------------------------------
        # Read data for log and get information:
        # --------------------------------------
        html_log = ''
        line_ids = []
        for line in order_proxy.order_line:
            if not line.mx_closed:
                line_ids.append(line.id)
                html_log += '''
                    <tr>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                    </tr>\n''' % (
                        line.product_id.default_code,
                        line.product_uom_qty,
                        line.delivered_qty,
                        line.product_uom_qty - line.delivered_qty,
                        )
        
        # -----------
        # Force line:
        # -----------
        sol_pool.write(cr, uid, line_ids, {
            'mx_closed': True,
            'forced_close': True,            
            }, context=context)
        
        # -------------
        # Force header:
        # -------------
        self.write(cr, uid, ids, {
            'mx_closed': True,
            'forced_close': True,            
            }, context=context)
        
        # --------------------------
        # Log message for operation:
        # --------------------------
        if html_log:
            message = _('''
                <p>Forced close of order, open line:</p>
                <table class='oe_list_content'>
                    <tr>
                        <td class='oe_list_field_cell'>Prod.</td>
                        <td class='oe_list_field_cell'>Order</td>
                        <td class='oe_list_field_cell'>Delivered</td>
                        <td class='oe_list_field_cell'>Residual</td>
                    </tr>
                    %s
                </table>
                ''') % html_log
                
            # Send message
            self.message_post(cr, uid, ids, body=message, context=context)
        return True
        
    _columns = {
        'forced_close': fields.boolean('Forced close', 
            help='Order force closed'),
        'residual_notified': fields.boolean('Residual notified by mail'),
        }

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """    
    _inherit = 'sale.order.line'

    _columns = {
        'forced_close': fields.boolean('Forced close', 
            help='Order force closed'),
        }

class ResCompany(orm.Model):
    """ Model name: Res Company
    """    
    _inherit = 'res.company'

    _columns = {
        'residual_management_alert':fields.boolean('Residual management'),
        'residual_order_value': fields.float(
            'Residual order value', digits=(16, 2), 
            help='Max value for total order with residual alert'), 
        'residual_remain_perc': fields.float(
            'Residual remain perc', digits=(16, 2), 
            help='Residual % remain for alert message, es. < 10% to delivery'), 
        }
        
    _defaults = {
        'residual_order_value': lambda *x: 1000.0,
        'residual_remain_perc': lambda *x: 10.0,
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
