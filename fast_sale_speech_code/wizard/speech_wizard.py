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

class StructureBlockValue(orm.Model):
    """ Model name: StructureBlockValue
    """
    
    _inherit = 'structure.block.value'
    
    def name_search(self, cr, uid, name, args=None, operator='ilike', 
            context=None, limit=80):
        """ Return a list of tupples contains id, name, as internally its calls {def name_get}
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

class SaleOorderSpeechProductWizard(orm.TransientModel):
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
            block_fabric = '***'    
            
        if block_frame_id:
            value_proxy = value_pool.browse(
                cr, uid, block_frame_id, context=context)
            block_frame = '%-2s' % value_proxy.code
        else:
            block_frame = '**'    

        if block_color_id:
            value_proxy = value_pool.browse(
                cr, uid, block_color_id, context=context)
            block_color = '%-4s' % value_proxy.code
        else:
            block_color = '****'    

        if block_partic_id:
            value_proxy = value_pool.browse(
                cr, uid, block_color_id, context=context)
            block_partic = '%1s' % value_proxy.code
        else:
            block_partic = '' # XXX not present = nothing    
            
        #if structure_id and block_parent_id and block_fabric_id and \
        #        block_frame_id and block_color_id:
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
                res['value']['product_id'] = product_ids[0]
                    
        return res    
            
    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        
        return {
            'type': 'ir.actions.act_window_close'
            }

    _columns = {
        'product_id': fields.many2one(
            'product.product', 'Product', 
            help='Product selected in sale order line'),
        'quantity': fields.float('Q.ty', digits=(16, 2), required=True),
        'structure_id': fields.many2one(
            'structure.structure', 'Structure', required=True),
        'block_parent_id': fields.many2one(
            'structure.block.value', 'Parent', required=True),
        'block_fabric_id': fields.many2one(
            'structure.block.value', 'Fabric', required=True),
        'block_frame_id': fields.many2one(
            'structure.block.value', 'Frame', required=True),
        'block_color_id': fields.many2one(
            'structure.block.value', 'Color', required=True),
        'block_partic_id': fields.many2one(
            'structure.block.value', 'Partic'),
        'code': fields.char('Code', size=13),    
            
        #'note': fields.text(
        #    'Annotation',
        #    help='Annotation about production opened with selected product'),
        }
        
    _defaults = {
        'quantity': lambda *x: 1.0,
    #    'product_id': lambda s, cr, uid, c: s.default_product_id(cr, uid, context=c),
    #    'note': lambda s, cr, uid, c: s.default_note(cr, uid, context=c),
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
