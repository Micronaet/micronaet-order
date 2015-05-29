# -*- coding: utf-8 -*-
###############################################################################
#
# OpenERP, Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
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

class SaleOrderLineMaster(orm.Model):
    ''' Master element for create a grouped quotation
    '''    
    _name = 'sale.order.line.master'
    _description = 'Master order line'
    _order = 'order_id desc, sequence, id'

    # Button events:
    def compute_subtotal(self, cr, uid, ids, context=None):
        ''' Calculate and write subtotal
        '''
        res = 0.0
        for item in self.browse(
                cr, uid, ids, context=context)[0].order_line_ids:
            res += item.price_subtotal or 0.0
        return self.write(cr, uid, ids, {
            'price_subtotal': res
            }, context=context)

    _columns = {
        'sequence': fields.integer(
            'Sequence', 
            help="Gives the sequence order when displaying master fields."),
        'name': fields.text(
            'Description', required=True,
            states={'draft': [('readonly', False)]}),
        'order_id': fields.many2one(
            'sale.order', 'Order Reference',
            ondelete='cascade', select=True, ),
        'pricelist_id': fields.related(
            'order_id',
            'pricelist_id',
            type='many2one',
            relation='product.pricelist', 
            string='Pricelist'),
        'date_order': fields.related(
            'order_id',
            'date_order',
            type='datetime', 
            string='Date order'),
        'partner_id': fields.related(
            'order_id',
            'partner_id',
            type='many2one',
            relation='res.partner', 
            string='Partner'),
        'fiscal_position': fields.related(
            'order_id',
            'fiscal_position',
            type='many2one',
            relation='account.fiscal.position', 
            string='Fiscal position'),
        'master_title': fields.text('Master title'),
        'master_note': fields.text('Master note'),
        'with_sub': fields.boolean('With subtotal'),
        'master_subtotal': fields.float(
            'Master subtotal', 
            digits=(16, 2)),
        'show_mode': fields.selection([
            ('none', 'Only master'),
            ('list', 'Master with element'),
            ('price', 'Master with element and price'),
            ], 'Show mode', required=True),
            
        # Not used for now:
        'product_id': fields.many2one(
            'product.product', 'Product', domain=[('sale_ok', '=', True)], 
            change_default=True, 
            ondelete='restrict'),

        #'invoice_lines': fields.many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_id', 'Invoice Lines', readonly=True, copy=False),
        #'invoiced': fields.function(_fnct_line_invoiced, string='Invoiced', type='boolean',
        #    store={
        #        'account.invoice': (_order_lines_from_invoice, ['state'], 10),
        #        'sale.order.line': (lambda self,cr,uid,ids,ctx=None: ids, ['invoice_lines'], 10)
        #    }),
        'price_unit': fields.float(
            'Unit Price',
            digits_compute= dp.get_precision('Product Price'), 
            states={'draft': [('readonly', False)]}),
        'price_subtotal': fields.float(
            'Subtotal',
            digits_compute=dp.get_precision('Product Price'), 
            states={'draft': [('readonly', False)]}),
        #'price_subtotal': fields.function(
        #    _amount_line, string='Subtotal', 
        #    digits_compute= dp.get_precision('Account')),
        #'price_reduce': fields.function(_get_price_reduce, type='float', 
        #    string='Price Reduce', 
        #    digits_compute=dp.get_precision('Product Price')),
        'tax_id': fields.many2many(
            'account.tax', 'sale_order_tax', 'order_line_id', 'tax_id', 
            'Taxes', states={'draft': [('readonly', False)]}),
        #'address_allotment_id': fields.many2one('res.partner', 
        #    'Allotment Partner',
        #    help="A partner to whom the particular product was allotment."),
        'product_uom_qty': fields.float(
            'Quantity', digits_compute= dp.get_precision('Product UoS'),
            states={'draft': [('readonly', False)]}),
        'product_uom': fields.many2one(
            'product.uom', 'Unit of Measure ',
            states={'draft': [('readonly', False)]}),
        'product_uos_qty': fields.float(
            'Quantity (UoS)', digits_compute= dp.get_precision('Product UoS'),
            states={'draft': [('readonly', False)]}),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'discount': fields.float(
            'Discount (%)', digits_compute= dp.get_precision('Discount'), 
            states={'draft': [('readonly', False)]}),
        #'th_weight': fields.float('Weight', readonly=True, 
        #    states={'draft': [('readonly', False)]}),
        #'state': fields.selection(
        #    [('cancel', 'Cancelled'),('draft', 'Draft'),
        #    ('confirmed', 'Confirmed'),('exception', 'Exception'),
        #    ('done', 'Done')],
        #    'Status', required=True, readonly=True, copy=False,),
        #'order_partner_id': fields.related(
        #    'order_id', 'partner_id', type='many2one', relation='res.partner',
        #    store=True, string='Customer'),
        #'salesman_id':fields.related('order_id', 'user_id', type='many2one', 
        #    relation='res.users', store=True, string='Salesperson'),
        #'company_id': fields.related('order_id', 'company_id', 
        #    type='many2one', relation='res.company', string='Company', 
        #    store=True, readonly=True),
        #'delay': fields.float('Delivery Lead Time', required=True, 
        #    readonly=True, states={'draft': [('readonly', False)]}),
        #'procurement_ids': fields.one2many(
        #    'procurement.order', 'sale_line_id', 'Procurements'),
        'state': fields.selection( # for problem in view (not used)
            [('draft', 'Draft')], 'State'),
    }


    _defaults = {
        #'product_uom' : _get_uom_id,
        'discount': 0.0,
        'product_uom_qty': 1,
        'product_uos_qty': 1,
        'sequence': 10,
        'price_unit': 0.0,
        #'delay': 0.0,
        'state': 'draft',
        }
    
    def product_uom_change(self, cursor, user, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, context=None):
        context = context or {}
        lang = lang or ('lang' in context and context['lang'])
        if not uom:
            return {'value': {'price_unit': 0.0, 'product_uom' : uom or False}}
        return self.product_id_change(cursor, user, ids, pricelist, product,
                qty=qty, uom=uom, qty_uos=qty_uos, uos=uos, name=name,
                partner_id=partner_id, lang=lang, update_tax=update_tax,
                date_order=date_order, context=context)
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='', partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        '''
        '''
        context = context or {}
        lang = lang or context.get('lang', False)
        if not partner_id:
            raise osv.except_osv(_('No Customer Defined!'), _('Before choosing a product,\n select a customer in the sales form.'))
        warning = False
        product_uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        context = {'lang': lang, 'partner_id': partner_id}
        partner = partner_obj.browse(cr, uid, partner_id)
        lang = partner.lang
        context_partner = {'lang': lang, 'partner_id': partner_id}

        if not product:
            return {'value': {'th_weight': 0,
                'product_uos_qty': qty}, 'domain': {'product_uom': [],
                   'product_uos': []}}
        if not date_order:
            date_order = time.strftime(DEFAULT_SERVER_DATE_FORMAT)

        result = {}
        warning_msgs = ''
        product_obj = product_obj.browse(cr, uid, product, context=context_partner)

        uom2 = False
        if uom:
            uom2 = product_uom_obj.browse(cr, uid, uom)
            if product_obj.uom_id.category_id.id != uom2.category_id.id:
                uom = False
        if uos:
            if product_obj.uos_id:
                uos2 = product_uom_obj.browse(cr, uid, uos)
                if product_obj.uos_id.category_id.id != uos2.category_id.id:
                    uos = False
            else:
                uos = False

        fpos = False
        if not fiscal_position:
            fpos = partner.property_account_position or False
        else:
            fpos = self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position)
        if update_tax: #The quantity only have changed
            result['tax_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, product_obj.taxes_id)

        if not flag:
            result['name'] = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context_partner)[0][1]
            if product_obj.description_sale:
                result['name'] += '\n'+product_obj.description_sale
        domain = {}
        if (not uom) and (not uos):
            result['product_uom'] = product_obj.uom_id.id
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
                uos_category_id = product_obj.uos_id.category_id.id
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
                uos_category_id = False
            result['th_weight'] = qty * product_obj.weight
            domain = {'product_uom':
                        [('category_id', '=', product_obj.uom_id.category_id.id)],
                        'product_uos':
                        [('category_id', '=', uos_category_id)]}
        elif uos and not uom: # only happens if uom is False
            result['product_uom'] = product_obj.uom_id and product_obj.uom_id.id
            result['product_uom_qty'] = qty_uos / product_obj.uos_coeff
            result['th_weight'] = result['product_uom_qty'] * product_obj.weight
        elif uom: # whether uos is set or not
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            q = product_uom_obj._compute_qty(cr, uid, uom, qty, default_uom)
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
            result['th_weight'] = q * product_obj.weight        # Round the quantity up

        if not uom2:
            uom2 = product_obj.uom_id
        # get unit price

        if not pricelist:
            warn_msg = _('You have to select a pricelist or a customer in the sales form !\n'
                    'Please set one before choosing a product.')
            warning_msgs += _("No Pricelist ! : ") + warn_msg +"\n\n"
        else:
            price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
                    product, qty or 1.0, partner_id, {
                        'uom': uom or result.get('product_uom'),
                        'date': date_order,
                        })[pricelist]
            if price is False:
                warn_msg = _("Cannot find a pricelist line matching this product and quantity.\n"
                        "You have to change either the product, the quantity or the pricelist.")

                warning_msgs += _("No valid pricelist line found ! :") + warn_msg +"\n\n"
            else:
                result.update({'price_unit': price})
        if warning_msgs:
            warning = {
                       'title': _('Configuration Error!'),
                       'message' : warning_msgs
                    }
        return {'value': result, 'domain': domain, 'warning': warning}
    

class SaleOrderLine(orm.Model):
    ''' Master element for create a grouped quotation
    '''    
    _inherit = 'sale.order.line'
    
    _columns = {
        'master_line_id': fields.many2one(
            'sale.order.line.master', 'Master parent', ondelete='set null'),
            
        }

class SaleOrderLineMaster(orm.Model):
    ''' For *many relations
    '''    
    _inherit = 'sale.order.line.master'
    
    _columns = {
        'order_line_ids': fields.one2many(
            'sale.order.line', 'master_line_id', 'Sub line'),
        }

class SaleOrder(orm.Model):
    ''' Add extra field for manage master orders
    '''    
    _inherit = 'sale.order'
    
    # Button event:
    def set_master_quotation(self, cr, uid, ids, context=None):
       ''' Set boolean 
       '''
       return self.write(cr, uid, ids, {
           'master_order': True
           }, context=context)

    def set_normal_quotation(self, cr, uid, ids, context=None):
       ''' Set boolean 
       '''
       return self.write(cr, uid, ids, {
           'master_order': False
           }, context=context)

    def _get_master_order(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for order in self.browse(cr, uid, ids, context=context):
            result[order.id] = 0.0
            if order.master_order:
                for line in order.master_line_ids:
                    result[order.id] += line.price_subtotal
        return result

    _columns = {
        'master_order': fields.boolean('Master order'),
        'master_line_ids': fields.one2many('sale.order.line.master',
            'order_id', 'Master line'),
        'master_subtotal': fields.function(
            _get_master_order, digits_compute=dp.get_precision('Account'), 
            string='Master subtotal',
            store=False,
            help="The subtotal line"),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
