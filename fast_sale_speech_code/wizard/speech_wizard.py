# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleOrderLine(orm.Model):
    """ Model name: StructureBlockValue
    """
    
    _inherit = 'sale.order.line'
    
    _columns = {
        'to_confirm_code': fields.boolean('Confirm code'),
        }

class StructureBlockValue(orm.Model):
    """ Model name: StructureBlockValue
    """
    
    _inherit = 'structure.block.value'
    
    def name_search(self, cr, uid, name, args=None, operator='ilike', 
            context=None, limit=80):
        """ Return a list of tupples contains id, name, as internally its calls 
            {def name_get}
            result format : {[(id, name), (id, name), ...]}
            
            @param cr: cursor to database
            @param uid: id of current user
            @param name: name to be search 
            @param args: other arguments
            @param operator: default operator is ilike, it can be change
            @param context: context arguments, like lang, time zone
            @param limit: returns first n ids of complete result, default it is 80
            
            @return: return a list of tupples contains id, name
        """
        
        if not args:
            args = []
        if not context:
            context = {}
        ids = []
        
        if name:
            ids = self.search(cr, uid, [
                ('code', 'ilike', name),
                ] + args, limit=limit)
        if not ids:
            ids = self.search(cr, uid, [
                ('name', operator, name),
                ] + args, limit=limit)
        return self.name_get(cr, uid, ids, context=context)
    
    def name_get(self, cr, uid, ids, context=None):
        """ Return a list of tupples contains id, name.
            result format : {[(id, name), (id, name), ...]}
            
            @param cr: cursor to database
            @param uid: id of current user
            @param ids: list of ids for which name should be read
            @param context: context arguments, like lang, time zone
            
            @return: returns a list of tupples contains id, name
        """
        
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]            
        res = []
        for record in self.browse(cr, uid, ids, context=context):
            if context.get('only_code', False):
                res.append((record.id, '[%s] %s' % (record.code, record.name)))
            else:
                res.append((record.id, record.name))
        return res

class SaleOrderSpeechProductWizard(orm.TransientModel):
    ''' Wizard for generate code
    '''
    _name = 'sale.order.speech.product.wizard'

    def onchange_blocks_information(self, cr, uid, ids, structure_id, 
            block_parent_id, block_fabric_id, block_frame_id, block_color_id,
            block_partic_id, context=None):
        ''' Generate product code
        '''            
        res = {'value': {}}
        value_pool = self.pool.get('structure.block.value')
        product_pool = self.pool.get('product.product')

        if not structure_id:
            return res
            
        if block_parent_id:
            value_proxy = value_pool.browse(
                cr, uid, block_parent_id, context=context)
            block_parent = value_proxy.code
        else:
            block_parent = '***'    

        if block_fabric_id:
            value_proxy = value_pool.browse(
                cr, uid, block_fabric_id, context=context)
            block_fabric = '%-3s' % value_proxy.code
        else:
            block_fabric = '   '    
            
        if block_frame_id:
            value_proxy = value_pool.browse(
                cr, uid, block_frame_id, context=context)
            block_frame = '%-2s' % value_proxy.code
            
        else:
            block_frame = '  '    

        if block_color_id:
            # TODO check in color is in range or fabric here
            value_proxy = value_pool.browse(
                cr, uid, block_color_id, context=context)
            block_color = '%-4s' % value_proxy.code
        else:
            block_color = '****'    

        if block_partic_id:
            value_proxy = value_pool.browse(
                cr, uid, block_partic_id, context=context)
            block_partic = '%1s' % value_proxy.code
        else:
            block_partic = '' # XXX not present = nothing    
            
        code = '%s%s%s%s%s' % (
            block_parent,
            block_fabric,
            block_frame,
            block_color,
            block_partic,
            )
        res['value']['code'] = code

        if '*' not in code:
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', code)], context=context)                
            if product_ids:
                product_proxy = product_pool.browse(
                    cr, uid, product_ids, context=context)[0]
                res['value']['product_id'] = product_proxy.id
                res['value']['lst_price'] = product_proxy.lst_price
                
        return res    
            

    # --------------------
    # Wizard button event:
    # --------------------
    def get_to_confirm_product(self, cr, uid, default_code, context=None):
        ''' Create or retur ID of to assign product
        '''
        product_pool = self.pool.get('product.product')        
        return product_pool.create(cr, uid, {
            'name': 'DA CONFERMARE %s' % default_code,
            'default_code': default_code,
            # TODO uom,
            }, context=context)
    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
       
        # Pool used:
        line_pool = self.pool.get('sale.order.line') 
        order_pool = self.pool.get('sale.order') 
        product_pool = self.pool.get('product.product')
        
        # Read parameters:
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        default_code = wiz_proxy.code
        lst_price = wiz_proxy.lst_price
        product_uom_qty = wiz_proxy.quantity
        product = wiz_proxy.product_id
        if not product:
            product_id = self.get_to_confirm_product(
                cr, uid, default_code, context=context)
            to_confirm_code = True    
            product = product_pool.browse(
                cr, uid, product_id, context=context)
            name = default_code
        else:    
            name = product.name
            to_confirm_code = False
                    
        # Get order header:                    
        order_id = context.get('active_id')
        parent = order_pool.browse(cr, uid, order_id, context=context)
        
        data = line_pool.product_id_change_with_wh(cr, uid, False,
            parent.pricelist_id.id,
            product.id,
            product_uom_qty, # product_uom_qty
            False,
            product_uom_qty, #product_uos_qty
            False,
            product.name,
            parent.partner_id.id, 
            False, 
            True, 
            parent.date_order, 
            False,# TODO product_packaging, 
            parent.fiscal_position.id, 
            False, 
            parent.warehouse_id.id, 
            context=context,
            ).get('value', {})
        
        data.update({
            'order_id': order_id,
            'product_id': product.id,
            'to_confirm_code': to_confirm_code,
            })
        line_pool.create(cr, uid, data, context=context)    
        
        return {
            'type': 'ir.actions.act_window_close'
            }

    _columns = {
        'product_id': fields.many2one(
            'product.product', 'Product', 
            help='Product selected in sale order line'),
        'quantity': fields.float('Q.ty', digits=(16, 2), required=True),
        'lst_price': fields.float('Price', digits=(16, 2), required=True),
        'discount_scale': fields.char('DIscount scale', size=64),
        'structure_id': fields.many2one(
            'structure.structure', 'Structure', required=True),
        'block_parent_id': fields.many2one(
            'structure.block.value', 'Parent', required=True),
        'block_fabric_id': fields.many2one(
            'structure.block.value', 'Fabric', required=True),
        'block_frame_id': fields.many2one(
            'structure.block.value', 'Frame'),
        'block_color_id': fields.many2one(
            'structure.block.value', 'Color', required=True),
        'block_partic_id': fields.many2one(
            'structure.block.value', 'Partic'),
        'code': fields.char('Code', size=13),    
        }
        
    _defaults = {
        'quantity': lambda *x: 1.0,
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
