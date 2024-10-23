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
import xlrd
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


class SaleOrderCsvImportWizard(orm.TransientModel):
    """ Wizard to import CSV product updating price
    """
    _name = 'sale.order.csv.import.wizard'

    # -------------------------------------------------------------------------
    # Utility function
    # -------------------------------------------------------------------------
    def preserve_window(self, cr, uid, ids, context=None):
        """ Create action for return the same open wizard window
        """
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[
            ('model', '=', 'product.product.csv.import.wizard'),
            ('name', '=', 'Create production order')  # TODO needed?
            ], context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Wizard create production order',
            'res_model': 'mrp.production.create.wizard',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'nodestroy': True,
            }

    # --------------
    # Wizard button:
    # --------------
    def action_import_csv(self, cr, uid, ids, context=None):
        """ Import pricelist and product description
        """
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        return self.pool.get('csv.import.order.element')._csv_import_order(
            cr, uid, wiz_proxy.item_id.code, context=context)

    _columns = {
        'item_id': fields.many2one(
            'csv.import.order.element',
            'Import order for partner', required=True),
        'note': fields.text('Note'),
        }
