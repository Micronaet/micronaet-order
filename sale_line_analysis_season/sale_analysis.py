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
    """ Model name: Sale order line
    """
    _inherit = 'sale.order.line'

    def _get_season_from_date(self, date_order):
        """ Return season from date
        """
        start_month = '09'
        if not date_order:
            return False
        current_month = date_order[5:7]
        year = int(date_order[2:4])
        if current_month >= start_month: # [09 : 12]
            return '%02d-%02d' % (year, year + 1)
        else: # [01 : 08]
            return '%02d-%02d' % (year - 1, year)

    def _get_season_from_sale_line(self, cr, uid, ids, context=None):
        """ Change family in product
        """
        line_pool = self.pool.get('sale.order.line')
        line_ids = line_pool.search(cr, uid, [
            ('order_id', 'in', ids),
            ], context=context)
        _logger.warning('Change season order line as order change date')
        return line_ids

    # -------------------------------------------------------------------------
    # Field function:
    # -------------------------------------------------------------------------
    def _get_season_from_sale_date(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._get_season_from_date(
                line.order_id.date_order)
        return res

    _columns = {
        'season_period': fields.function(
            _get_season_from_sale_date, method=True,
            type='char', size=30, string='Season',
            store={
                'sale.order':
                    (_get_season_from_sale_line, ['date_order'], 10),
                }
            )
        }
