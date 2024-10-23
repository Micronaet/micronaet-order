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
import pdb
import sys
import logging
import openerp
import shutil
import csv
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


class CsvImportOrderElement(orm.Model):
    """ Model name: CsvImportOrderTrace
        Object for save list of type of order that could be imported
        Virtual import procedure that will be overridden from all
        extra modules
    """

    _inherit = 'csv.import.order.element'

    # -------------------------------------------------------------------------
    # Scheduled
    # -------------------------------------------------------------------------
    def scheduled_csv_import_order(self, cr, uid, context=None):
        """ Launch import via scheduled operation
        """
        # Launch normal operation with company4 code
        self._csv_import_order(cr, uid, 'company4', context=context)
        return True

    # -------------------------------------------------------------------------
    # Virtual procedure overridden:
    # -------------------------------------------------------------------------
    def _csv_import_order(self, cr, uid, code, context=None):
        """ Import procedure that will be called from modules (depend on this)
            code is the code of element to load (data.xml of every new mod.)
            Importation will be as data in table
        """
        def only_ascii(value):
            """ Remove not ascii char
            """
            res = ''
            value = (value or '').strip()
            for c in value:
                if ord(c) < 128:
                    res += c
                else:
                    res += '#'
            return res

        # ---------------------------------------------------------------------
        #                      PROCEDURE FOR IMPORT
        # ---------------------------------------------------------------------
        if code != 'company4':
            return super(CsvImportOrderElement, self)._csv_import_order(
                cr, uid, code, context=context)

        # ---------------------------------------------------------------------
        #                      Company 4 Import procedure:
        # ---------------------------------------------------------------------
        item_ids = self.search(cr, uid, [
            ('code', '=', code),
            ], context=context)
        if not item_ids:
            _logger.error(
                _('Import code not found: company4 (record deleted?)'))
            return False

        mapping_id = item_ids[0]

        # Pool used:
        log_pool = self.pool.get('log.importation')
        order_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')
        partner_pool = self.pool.get('res.partner')
        product_pool = self.pool.get('product.product')
        element_pool = self.pool.get('csv.import.order.element')
        mapping_pool = self.pool.get('csv.import.order.element.mapping')

        product_assign_ids = product_pool.search(cr, uid, [
            ('default_code', '=', 'ASSEGNARE'),
        ], context=context)
        if product_assign_ids:
            product_assign_id = product_assign_ids[0]
        else:
            product_assign_ids = 1  # todo?

        # ---------------------------------------------------------------------
        # Read parametric data:
        # ---------------------------------------------------------------------
        item_proxy = self.browse(cr, uid, item_ids, context=context)[0]
        _logger.info('Start import %s order' % item_proxy.name)

        # Folder used:
        base_folder = os.path.expanduser(item_proxy.filepath)
        in_folder = os.path.join(base_folder, 'IN')
        history_folder = os.path.join(base_folder, 'HISTORY')
        log_folder = os.path.join(base_folder, 'LOG')

        # 2 log files:
        log_scheduler = os.path.join(log_folder, 'scheduler.log')
        log_import = os.path.join(log_folder, 'import.log')

        # Open 2 log files:
        f_log_scheduler = open(log_scheduler, 'a')
        f_log_import = open(log_import, 'a')

        extension = item_proxy.fileextension or ''
        mask = item_proxy.filemask or ''  # starts with

        code_mapping = {}
        for mapping in item_proxy.mapping_ids:
            code_mapping[mapping.name] = mapping.product_id.id

        # ------------------
        # Start log message:
        # ------------------
        importation_id = log_pool.create(cr, uid, {
            'name': 'Import Company 4 order',
            'user_id': uid,
            # 'mode_id': 'order', # TODO search order element!!
            'note': False,
            'error': False,
            }, context=context)

        # Loop on files in folder:
        order_list = []
        for f in os.listdir(in_folder):
            if mask and not f.startswith(mask):
                continue

            if extension and not f.endswith(extension):
                continue

            if os.path.isfile(os.path.join(in_folder, f)):
                order_list.append(f)
        order_list.sort()

        # ---------------------------------------------------------------------
        # Log schedule start operation:
        # ---------------------------------------------------------------------
        self._csv_logmessage(
            f_log_scheduler,
            'Start import procedure, file selected: %s' % len(order_list),
            mode='info',
            verbose=True,
            )

        # ---------------------------------------------------------------------
        #                      Import order:
        # ---------------------------------------------------------------------
        # Init log elements:
        error = ''
        imported = 0
        for f in order_list:
            fullname = os.path.join(in_folder, f)
            history_fullname = os.path.join(history_folder, f)

            # Load read file:
            self._csv_logmessage(
                f_log_import,
                'Start read file: %s' % f,
                mode='info',
                verbose=True,
                )
            f_in = open(fullname, 'r')

            # reset header / footer element:
            order_id = False
            error_text = ''  # Reset every new order

            cols = 0
            for line in f_in:

                # Read as CSV:
                line = line.strip()
                line = line.split(';')
                if not cols:  # Header
                    cols = len(line)
                    continue

                if len(line) != cols:
                    error_text += 'File: %s riga con colonne differenti' % f
                    error += '%s<br/>\n' % error_text
                    self._csv_logmessage(
                        f_log_import,
                        error_text,
                        mode='error',
                    )
                    break  # jump file

                discount = [0.0, 0.0, 0.0, 0.0, 0.0, ]
                discount_promo = [0.0, 0.0, 0.0, 0.0, 0.0, ]
                (
                 # Header:
                 record_type, vat_supplier, destination_code, record_id,
                 order_number, document_date, supplier_country,
                 supplier_fiscal_code, customer_vat, customer_country,
                 customer_fiscal_code, destination_address,
                 destination_city, date_deadline,
                 order_gt, order_date, supplier_order,
                 payment_method, payment_condition, payment_iban,
                 supplier_order_origin, commission_rate,
                 commission_cost, transport_cost, label_cost,
                 package_cost, truck_number, truck_plate,
                 truck_without_plate, truck_flatbed, truck_extension_low,
                 truck_extension_long, parcel, pallet_epal, pallet_lost,
                 carrier_name, state,

                 # Detail:
                 sequence, ean13, default_code, supplier_code,
                 name, product_uom_qty, uom, uom_qty, price_unit, vat_rate,
                 discount[0], discount[1], discount[2],
                 discount[3], discount[4],
                 discount_promo[0], discount_promo[1], discount_promo[2],
                 discount_promo[3], discount_promo[4],
                 amount, amount_label, label_qty, intra_code,
                 intra_weight, intra_weight_net, intra_parcel,
                 passport_ruop, passport_lot, kit_qty, ean_parent,
                 family_code) = line

                if not order_id:  # First line create order header:
                    # ---------------------------------------------------------
                    #                     HEADER DATA:
                    # ---------------------------------------------------------
                    # A. Partner (from VAT):
                    # ---------------------------------------------------------
                    if len(customer_vat) == 11:
                        customer_vat = 'IT{}'.format(customer_vat)
                    partner_ids = partner_pool.search(cr, uid, [
                        ('vat', '=', customer_vat),
                        ('is_company', '=', True),
                        # todo add more filter?
                    ], context=context)

                    if not partner_ids:
                        error_text += '''
                            File: %s partner VAT %s not found in ODOO
                            ''' % (f, customer_vat)
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                        )
                        break  # jump file
                    partner_id = partner_ids[0]

                    # ---------------------------------------------------------
                    # B. Partner (from VAT):
                    # ---------------------------------------------------------
                    # todo Sale point:
                    # destination_code

                    # todo Destination
                    if destination_code:
                        destination_ids = partner_pool.search(cr, uid, [
                            ('edi_code', '=', destination_code),
                            ('type', '=', 'delivery'),
                        ], context=context)
                    else:
                        destination_ids = False

                    if not destination_ids:
                        error_text += '''
                            File: %s Destination Code %s not found in ODOO
                            ''' % (f, destination_code)
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                        )
                        break  # jump file
                    destination_id = destination_ids[0]

                    # ---------------------------------------------------------
                    # Search Order:
                    # ---------------------------------------------------------
                    # Search if there's a previous import (not done)
                    order_ids = order_pool.search(cr, uid, [
                        ('client_order_ref', '=', order_gt),
                        ('partner_id', '=', partner_id),
                        ('destination_partner_id', '=', destination_id),
                        ], context=context)

                    if order_ids:  # on same order:
                        error_text = 'Order yet present: %s' % order_gt
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        # todo delete detail and import?
                        break

                    # ---------------------------------------------------------
                    # Insert order:
                    # ---------------------------------------------------------
                    try:
                        order_data = order_pool.onchange_partner_id(
                            cr, uid, [], partner_id,
                            context=context).get('value', {})
                    except:
                        error_text = '''
                            Onchange partner data not
                            present in order %s!''' % order_gt
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        break  # No order creation jump file

                    order_data.update({
                        'importation_id': importation_id,
                        'partner_id': partner_id,
                        'date_order': self._csv_format_date(
                            order_date, mode='italian_2'),
                        'date_deadline': self._csv_format_date(
                            date_deadline, mode='italian_2'),
                        'client_order_ref': order_gt,
                        'destination_partner_id': destination_id,
                        })
                    order_id = order_pool.create(
                        cr, uid, order_data, context=context)

                # -------------------------------------------------------------
                #                          ROW DATA:
                # -------------------------------------------------------------
                # Product search:
                # -------------------------------------------------------------
                product_id = code_mapping.get(default_code)

                if not product_id:
                    product_ids = product_pool.search(cr, uid, [
                        ('default_code', '=', default_code),
                        ], context=context)
                    if product_ids:
                        product_id = product_ids[0]
                    else:
                        # Create a mapping for next time!
                        mapping_pool.create(cr, uid, {
                            'item_id': mapping_id,
                            'name': default_code,
                            'product_id': product_assign_id,
                        }, context=context)

                        error_text = \
                            '%s. File: %s no product: %s (update mapping!)' % (
                                sequence,
                                f,
                                default_code,
                                )
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        product_id = product_assign_id

                # todo onchange for extra data??
                data = {
                    'order_id': order_id,
                    'sequence': int(sequence) / 10000,
                    'product_id': product_id,
                    'product_uom_qty':
                        element_pool._csv_float(product_uom_qty),
                    'price_unit': element_pool._csv_float(price_unit),
                    'name': only_ascii(name),
                    'date_deadline': date_deadline,
                    # todo discount, scale vat ecc.
                    }

                # Discount:
                multi_discount_rate = '+'.join([
                    str(d) for d in discount if d
                ])
                if multi_discount_rate:
                    data_extra = line_pool.on_change_multi_discount(
                        cr, uid, False, multi_discount_rate,
                        context=context).get('value', {})
                    data.update(data_extra)

                line_pool.create(cr, uid, data, context=context)
                self._csv_logmessage(
                    f_log_import,
                    'Create line: %s' % data,
                    mode='info',
                    )

            # History file if not error:
            # todo restore: shutil.move(fullname, history_fullname)
            self._csv_logmessage(
                f_log_import,
                'History file: %s > %s' % (
                    fullname, history_fullname),
                mode='info',
                )
            imported += 1

        if error:
            log_pool.write(cr, uid, importation_id, {
                'error': error,
                }, context=context)

        # ---------------------------------------------------------------------
        # Log schedule end operation:
        # ---------------------------------------------------------------------
        self._csv_logmessage(
            f_log_scheduler,
            'End import procedure, file imported: %s / %s' % (
                imported,
                len(order_list),
                ),
            mode='info',
            verbose=True,
            )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Log importation',
            'res_model': 'log.importation',
            'res_id': importation_id,
            'view_type': 'form',
            'view_mode': 'form',
            # 'view_id': view_id,
            # 'target': 'new',
            # 'nodestroy': True,
            }
