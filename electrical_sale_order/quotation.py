#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
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

class SaleOrderLine(orm.Model):
    """ Model name: Sale Order Line
    """
    
    _inherit = 'sale.order.line'
    
    # -------------------------------------------------------------------------
    # Function field:    
    # -------------------------------------------------------------------------
    def _get_line_sale_quotation(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate line data
        '''    
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            # -----------------------------------------------------------------     
            # Header data:
            # -----------------------------------------------------------------     
            order = line.order_id
            order_recharge = order.sale_recharge
            order_hour_cost = order.sale_hour_cost
            order_hour_revenue = order.sale_hour_revenue

            # -----------------------------------------------------------------     
            # Line input data:
            # -----------------------------------------------------------------     
            qty = line.product_uom_qty
            
            base = line.sale_base
            hour = line.sale_hour
            discount = line.sale_discount
            
            # -----------------------------------------------------------------     
            # Line calculated data:
            # -----------------------------------------------------------------     
            tot_base = qty * base
            discount_base = base * (100.0 - discount) / 100.0
            discount_base_tot = discount_base *  qty
            recharge = discount_base * (100.0 + order_recharge) / 100.0
            recharge_tot = recharge * qty
            
            hour_tot = hour * qty
            hour_cost = hour * order_hour_cost
            hour_revenue = hour * order_hour_revenue
            hour_cost_tot = hour_cost * qty
            hour_revenue_tot = hour_revenue * qty
            
            real_cost = discount_base_tot + hour_cost_tot
            real_revenue = recharge + hour_revenue # XXX
            total = recharge_tot + hour_revenue_tot
                
            res[line.id] = {
                'sale_tot_base': tot_base,
                'sale_discount_base': discount_base,
                'sale_discount_base_tot': discount_base_tot,
                'sale_recharge': recharge,
                'sale_recharge_tot': recharge_tot,
                'sale_hour_tot': hour_tot,
                'sale_hour_cost': hour_cost,
                'sale_hour_revenue': hour_revenue,
                'sale_hour_cost_tot': hour_cost_tot,
                'sale_hour_revenue_tot': hour_revenue_tot,
                'sale_real_cost': real_cost,
                'sale_real_revenue': real_revenue,
                'sale_total': total,
                }
        return res
                        

    _columns = {
        # ---------------------------------------------------------------------        
        # Input fields:
        # ---------------------------------------------------------------------        
        'sale_base': fields.float(
            'Base', digits_compute=dp.get_precision('Product Price')),
        'sale_hour': fields.float(
            'Hours', digits_compute=dp.get_precision('Product Price')),
        # TODO multi discount ?!?    
        'sale_discount': fields.float('Sale discount', digits=(16, 7)),
        
        # ---------------------------------------------------------------------        
        # Calculated fields:    
        # ---------------------------------------------------------------------        
        # Material:
        'sale_tot_base': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Base (tot.)', multi=True), 
            
        'sale_discount_base': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Discount Base (unit.)', multi=True), 
        'sale_discount_base_tot': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Discount Base (tot.)', multi=True), 
            
        'sale_recharge': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Recharge (unit.)', multi=True), 
        'sale_recharge_tot': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Recharge (tot.)', multi=True), 
            
        # Work:        
        'sale_hour_tot': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Hour (tot.)', multi=True), 
        'sale_hour_cost': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Hour cost', multi=True), 
        'sale_hour_revenue': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Hour revenue', multi=True), 
        'sale_hour_cost_tot': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Hour cost (tot.)', multi=True), 
        'sale_hour_revenue_tot': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Hour cost (tot.)', multi=True), 
            
        # Total:
        'sale_real_cost': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Real cost (unit.)', multi=True), 
        'sale_real_revenue': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Real revenue (unit.)', multi=True), 
            
        'sale_total': fields.function(
            _get_line_sale_quotation, method=True, 
            type='float', string='Total', multi=True), 
        }
        
class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """
    
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def update_unit_price_and_return(self, cr, uid, ids, context=None):
        ''' Save sale_real_cost in price_unit
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        # Pool used:
        line_pool = self.pool.get('sale.order.line')
        
        for line in self.browse(cr, uid, ids, context=context).order_line:
            line_pool.write(cr, uid, line.id, {
                'price_unit': line.sale_real_cost,
                }, context=context)
        return self.return_sale_view(cr, uid, ids, context=context)    
        
    def return_sale_view(self, cr, uid, ids, context=None):
        ''' Open normal view
        '''
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quotation view'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'sale.order',
            #'view_id': view_id, # False
            'views': [(False, 'form'),(False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }
        
    def open_cost_management_view(self, cr, uid, ids, context=None):
        ''' Open cost view management
        '''
        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid, 
            'electrical_sale_order', 'view_sale_order_for_cost_form')[1]
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cost management'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'sale.order',
            'view_id': view_id, # False
            'views': [(view_id, 'form'),(False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

    def dummy_button(self, cr, uid, ids, context=None):
        ''' Dummy button to update
        '''
        return True
        
    def update_base_price(self, cr, uid, ids, context=None):
        ''' Update base price depend on base selected
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        line_pool = self.pool.get('sale.order.line')
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        sale_base = order_proxy.sale_base
        
        update_db = {}
        for line in order_proxy.order_line:
            product = line.product_id
            if sale_base == 'last':
                cost = product.standard_price
            elif sale_base == 'net':
                cost = product.metel_net
            elif sale_base == 'discount':
                cost = product.metel_sale
            elif sale_base == 'pricelist':
                cost = product.lst_price
            else:  
                cost = 0.0 # XXX error!    
            update_db[line.id] = cost
             
            line_pool.write(cr, uid, line.id, {
                'sale_base': cost,
                }, context=context)
        
    # -------------------------------------------------------------------------
    # Function field:    
    # -------------------------------------------------------------------------
    def _get_header_sale_quotation(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate 
        '''    
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            # -----------------------------------------------------------------
            # Total data:
            # -----------------------------------------------------------------
            tot_base = 0.0
            tot_discount = 0.0
            
            tot_hour = 0.0
            tot_work_cost = 0.0
            tot_work_revenue = 0.0
            
            tot_cost = 0.0
            tot_revenue = 0.0
            total = 0.0

            # Calculate data from lines:                
            for line in order.order_line:
                tot_base += line.sale_tot_base
                tot_discount += line.sale_discount_base_tot
                tot_hour += line.sale_hour_tot
                tot_work_cost += line.sale_hour_cost_tot
                tot_work_revenue += line.sale_hour_revenue_tot
                tot_cost += line.sale_real_cost
                tot_revenue += line.sale_real_revenue
                total += line.sale_total

            margin = total - tot_cost
            if tot_cost:
                margin_perc = 100.0 * margin / tot_cost 
            else: 
                margin_perc = 0.0
                    
            res[order.id] = {
                'sale_tot_base': tot_base,
                'sale_tot_discount': tot_discount,
                'sale_tot_hour': tot_hour,
                'sale_tot_work_cost': tot_work_cost,
                'sale_tot_work_revenue': tot_work_revenue,
                'sale_tot_cost': tot_cost,
                'sale_tot_revenue': tot_revenue,
                'sale_total': total,
                'sale_margin': margin,
                'sale_margin_perc': margin_perc,
                }
        return res
        
    _columns = {
        # Input fields:
        'sale_recharge': fields.float(
            'Recharge', digits_compute=dp.get_precision('Product Price')),
        'sale_hour_cost': fields.float(
            'Hour cost', digits_compute=dp.get_precision('Product Price')),
        'sale_hour_revenue': fields.float(
            'Hour revenue', digits_compute=dp.get_precision('Product Price')),
        'sale_base': fields.selection([
            ('last', 'Last price'),
            ('net', 'Net price'),
            ('discount', 'Discount price'),
            ('pricelist', 'Metel pricelis'),
            ], 'Sale base'),

        # ---------------------------------------------------------------------        
        # Calculated fields:    
        # ---------------------------------------------------------------------        
        # Material:
        'sale_tot_base': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. Base', multi=True), 
        'sale_tot_discount': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. Discount', multi=True), 
        'sale_tot_hour': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. H.', multi=True), 
            
        # Work:    
        'sale_tot_work_cost': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. Work cost', multi=True), 
        'sale_tot_work_revenue': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. Work revenue', multi=True), 

        # Total:
        'sale_tot_cost': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. real cost', multi=True), 
        'sale_tot_revenue': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Tot. revenue', multi=True), 
        'sale_total': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Total', multi=True), 

        # Margin:
        'sale_margin': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Margin', multi=True), 
        'sale_margin_perc': fields.function(
            _get_header_sale_quotation, method=True, 
            type='float', string='Margin %', multi=True), 
        }
        
    _defaults = {
        'sale_base': lambda *x: 'pricelist',
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
