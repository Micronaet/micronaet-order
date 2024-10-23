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
        pdb.set_trace()
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

        # Pool used:
        log_pool = self.pool.get('log.importation')
        order_pool = self.pool.get('sale.order')
        line_pool = self.pool.get('sale.order.line')
        partner_pool = self.pool.get('res.partner')
        partic_pool = self.pool.get('res.partner.product.partic')
        product_pool = self.pool.get('product.product')

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

        partner_id = item_proxy.partner_id.id
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
        comment = ''
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
            destination_partner_id = False
            date_deadline = False  # keep header in line!
            counter = 0  # row
            for line in f_in:
                counter += 1
                # Read as CSV:
                line = line.strip()
                line = line.split('|')

                if counter == 1:
                    # -----------------------------------------------------
                    #                     HEADER DATA:
                    # -----------------------------------------------------
                    # Read all header fields:
                    number = line[0] # customer order number
                    order_date = self._csv_format_date(line[1])
                    reference_code = line[2]
                    destination_code = line[3]
                    # payment_terms = line[4]
                    # currency = line[5]
                    # note = line[6]
                    total = line[7]
                    customer_id = line[8]
                    date_deadline = self._csv_format_date(line[9])

                    # Create order:
                    if destination_code:  # XXX mandatory?
                        destination_ids = partner_pool.search(cr, uid, [
                            ('parent_id', '=', partner_id),
                            ('csv_import_code', '=', destination_code),
                            ], context=context)
                        if destination_ids:
                            destination_partner_id = destination_ids[0]
                        else:
                            error_text += '''File: %s destination code %s
                                not found in ODOO''' % (
                                    f, destination_code)
                            error += '%s<br/>\n' % error_text
                            self._csv_logmessage(
                                f_log_import,
                                error_text,
                                mode='error',
                                )
                            break  # jump file
                    else:
                        error_text = '''
                            File: %s destination code %s
                            not found in file''' % (
                                f, destination_code)
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        break  # jump file

                    # Search if there's a previous import (not done)
                    order_ids = order_pool.search(cr, uid, [
                        ('client_order_ref', '=', number),
                        ('partner_id', '=', partner_id),
                        ], context=context)

                    if order_ids:  # on same order:
                        error_text = 'Order yet present: %s' % number
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        # TODO delete detail and import?
                        break

                    try:
                        onchange_data = order_pool.onchange_partner_id(
                            cr, uid, [], partner_id, context=context)[
                                'value']
                    except:
                        error_text = '''
                            Onchange partner data not
                            present in order %s!''' % number
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        break # No order creation jump file

                    onchange_data.update({
                        'importation_id': importation_id,
                        'partner_id': partner_id,
                        'date_order': order_date,
                        'date_deadline': date_deadline,
                        'client_order_ref': number,
                        'destination_partner_id': destination_partner_id,
                        })
                    order_id = order_pool.create(
                        cr, uid, onchange_data, context=context)
                    continue # header read

                # -------------------------------------------------------------
                #                          ROW DATA:
                # -------------------------------------------------------------
                if not order_id:
                    error_text = 'File: %s header not created' % (
                        f)
                    error += '%s<br/>\n' % error_text
                    self._csv_logmessage(
                        f_log_import,
                        error_text,
                        mode='error',
                        )
                    break # next order

                # ------------
                # Read fields:
                # ------------
                # TODO
                sequence = line[0]
                product_customer = line[1]
                product_code = line[2]
                description = line[3]
                ean = line[4]
                product_uom_qty = self._csv_c1_float(line[5])
                # uom_code = line[6]
                price_unit = self._csv_c1_float(line[7])
                # subtotal = line[8]
                date_deadline = self._csv_format_date(line[9])

                # Product:
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', product_code),
                    ], context=context)

                if product_ids:
                    product_id = product_ids[0]
                else:
                    # Try search in mapping code:
                    product_id = code_mapping.get(
                        product_customer, False)
                    if not product_id:
                        error_text = \
                            '%s. File: %s no product: %s>%s' % (
                                counter,
                                f,
                                product_customer,
                                product_code,
                                )
                        error += '%s<br/>\n' % error_text
                        self._csv_logmessage(
                            f_log_import,
                            error_text,
                            mode='error',
                            )
                        break # End import of this order

                # Partner - product partic:
                partic_ids = partic_pool.search(cr, uid, [
                    ('partner_id', '=', partner_id),
                    ('product_id', '=', product_id),
                    ], context=context)
                if partic_ids:
                    # TODO ask if correct
                    partic_pool.write(cr, uid, partic_ids[0], {
                        'partner_price': price_unit,
                        'partner_code': '%s - EAN %s' % (
                            product_customer, ean)
                        }, context=context)
                else: # create
                    partic_pool.create(cr, uid, {
                        'partner_id': partner_id,
                        'product_id': product_id,
                        'partner_price': price_unit,
                        'partner_code': '%s - EAN %s' % (
                            product_customer, ean)
                        }, context=context)

                # TODO onchange for extra data??
                data = {
                    'order_id': order_id,
                    'sequence': sequence,
                    'product_id': product_id,
                    'product_uom_qty': product_uom_qty,
                    'price_unit': price_unit,
                    'name': only_ascii(description),
                    'date_deadline': date_deadline,
                    # TODO discount, scale vat ecc.
                    }

                line_pool.create(cr, uid, data, context=context)
                self._csv_logmessage(
                    f_log_import,
                    'Create line: %s' % data,
                    mode='info',
                    )

            # History file if not error:
            shutil.move(fullname, history_fullname)
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
