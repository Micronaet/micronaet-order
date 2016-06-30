#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _

class Parser(report_sxw.rml_parse):
    counters = {}
    
    def __init__(self, cr, uid, name, context):
        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
        })
    
    def get_objects(self, ):    
        ''' Check company parameter and return order with residual
        '''
        context = {}
        cr = self.cr
        uid = self.uid
        
        # ------------------------
        # Read company parameters:
        # ------------------------
        company_pool = self.pool.get('res.company')
        company_ids = company_pool.search(cr, uid, [], context=context)
        company_proxy = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
            
        amount_untaxed = company_proxy.residual_order_value
        residual_remain_perc = company_proxy.residual_remain_perc     
        if not (amount_untaxed and residual_remain_perc):
            raise osv.except_osv(
                _('Parameter error'), 
                _('Setup parameters in company form!'),
                )
        
        # -----------------------------
        # Read order residual to close:
        # -----------------------------
        # Read order not closed:
        order_pool = self.pool.get('sale.order')
        domain = [
            ('state', 'not in', ('cancel', 'sent', 'draft')),
            ('mx_closed', '=', False),
            ('amount_untaxed', '<=', amount_untaxed),
            # TODO forecast order?
            ]
        # for forecast order (used in production module)    
        if 'forecasted_production_id' in order_pool._columns.keys():
            domain.append(('forecasted_production_id', '=', False))
            
        res = []
        order_ids = order_pool.search(cr, uid, domain, context=context)
        for order in order_pool.browse(cr, uid, order_ids, context=context):
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
            if residual <= order.amount_untaxed * (
                    residual_remain_perc / 100.0):     
                res.append((order, lines, residual))
                
        # Check residual information:
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
