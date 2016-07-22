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


import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)



class Parser(report_sxw.rml_parse):
    counters = {}
    
    def __init__(self, cr, uid, name, context):
        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            'get_filter': self.get_filter,
        })

    # --------
    # Utility:
    # --------
    def get_company_filter(self, ):
        ''' Read company and return parameter
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
        return (
            company_proxy.residual_order_value,
            company_proxy.residual_remain_perc,
            )

    def get_filter(self, ):    
        ''' Calculate filter depend on 
        '''
        return _(
            'Tot. <=%s, rim. <=%s') % self.get_company_filter()
        
        (amount_untaxed, residual_remain_perc) = self.get_company_filter()
    
    def get_objects(self, ):    
        ''' Check company parameter and return order with residual
        '''
        context = {}
        cr = self.cr
        uid = self.uid
        
        (amount_untaxed, residual_remain_perc) = self.get_company_filter()
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
            if residual and residual <= order.amount_untaxed * (
                    residual_remain_perc / 100.0):     
                res.append((order, lines, residual))
                
        # Check residual information:
        return res
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
