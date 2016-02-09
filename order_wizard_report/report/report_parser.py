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
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)


class Parser(report_sxw.rml_parse):
    counters = {}
    last_record = 0
    
    def __init__(self, cr, uid, name, context):
        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_object_line': self.get_object_line,

            'get_datetime': self.get_datetime,
            'get_date': self.get_date,
            
            'get_filter_description': self.get_filter_description,
        })
        
    def get_filter_description(self, ):
        return self.filter_description
        
    def get_datetime(self):
        ''' Return datetime obj
        '''
        return datetime

    def get_date(self):
        ''' Return datetime obj
        '''
        return datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)

    # Utility for 2 report:
    def get_object_line(self, data):
        ''' Order line delivered
        '''
        _logger.info('Start report data: %s' % data)

        # Parameters for report management:
        sale_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')
        
        from_date = data.get('from_date', False)
        to_date = data.get('to_date', False)
        from_deadline = data.get('from_deadline', False)
        to_deadline = data.get('to_deadline', False)

        # ---------------------------------------------------------------------
        #                      Sale order filter
        # ---------------------------------------------------------------------
        # Default:
        domain = [
            ('state', 'not in', ('cancel', 'draft', 'sent')), # 'done'
            #('pricelist_order', '=', False), # needed? (yet in mx_closed
            ('mx_closed', '=', False), 
            ]

        # -------------------------
        # Start filter description:
        # -------------------------
        self.filter_description = _('Order open, not pricelist order')

        if from_date:
            domain.append(('date_order', '>=', from_date))
            self.filter_description += _(', date >= %s') % from_date
        if to_date:
            domain.append(('date_order', '<', to_date))
            self.filter_description += _(', date < %s') % to_date
        
        order_ids = sale_pool.search(self.cr, self.uid, domain)
        _logger.info('Found %s orders' % len(order_ids))

        # ---------------------------------------------------------------------
        #                      Sale order line filter
        # ---------------------------------------------------------------------
        domain = [('order_id', 'in', order_ids)]

        if from_deadline:
            domain.append(('date_deadline', '>=', from_deadline))
            self.filter_description += _(', deadline >= %s') % from_deadline
        if to_deadline:
            domain.append(('date_deadline', '<', to_deadline))
            self.filter_description += _(', deadline < %s') % to_deadline
            
        line_ids = line_pool.search(self.cr, self.uid, domain, 
            order='order_id, id')
        #res = []
        #_logger.info('Found %s order line' % len(line_ids))
        #for line in line_pool.browse(self.cr, self.uid, line_ids):
        #    if line.product_uom_qty - line.delivered_qty > 0.0:
        #        res.append(line.id)
            
        return line_pool.browse(self.cr, self.uid, line_ids)#res)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
