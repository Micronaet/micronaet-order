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


class SaleOrderGeneralReportWizard(orm.TransientModel):
    """ Procurements depend on sale
    """
    _name = 'sale.order.general.report.wizard'
    _description = 'Sale general wizard'

    # --------------
    # Button events:
    # --------------
    def print_report(self, cr, uid, ids, context=None):
        """ Redirect to report passing parameters
        """
        wiz_proxy = self.browse(cr, uid, ids)[0]

        datas = {}

        datas['wizard'] = True  # started from wizard

        datas['discount_limit'] = ''
        datas['order_status'] = ''
        if wiz_proxy.report_type == 'deadlined':
            report_name = 'mx_order_list_report'
        elif wiz_proxy.report_type == 'extract':
            report_name = 'mx_extract_order_report'
        elif wiz_proxy.report_type == 'discount':
            report_name = 'mx_order_discount_line_report'

            # Translate discount as number
            discount_limit = wiz_proxy.discount_limit or False
            if discount_limit:
                res = self.pool.get(
                    'sale.order.line').on_change_multi_discount(
                        cr, uid, 0, discount_limit)['value']
                datas['discount_limit'] = res.get('discount', 0)
            else:
                datas['discount_limit'] = False

        else:  # 'line'
            report_name = 'mx_order_list_line_report'

        statistic_category = wiz_proxy.statistic_category_id
        if statistic_category:
            datas['statistic_category_id'] = \
                wiz_proxy.statistic_category_id.id
            datas['statistic_category_name'] = \
                wiz_proxy.statistic_category_id.name
        else:
            datas['statistic_category_id'] = False
            datas['statistic_category_name'] = ''

        datas['partner_id'] = wiz_proxy.partner_id.id or False
        datas['fiscal_position'] = wiz_proxy.fiscal_position
        datas['from_date'] = wiz_proxy.from_date or False
        datas['to_date'] = wiz_proxy.to_date or False
        datas['from_deadline'] = wiz_proxy.from_deadline or False
        datas['to_deadline'] = wiz_proxy.to_deadline or False
        # datas['only_remain'] = wiz_proxy.only_remain
        datas['data_type'] = wiz_proxy.data_type
        datas['report_type'] = wiz_proxy.report_type
        datas['data_sort'] = wiz_proxy.data_sort
        datas['order_status'] = wiz_proxy.order_status

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            }

    _columns = {
        'fiscal_position': fields.selection([
            ('italy', 'Italy'),
            ('extra', 'Not Italy'),
            ('all', 'All'),
            ], 'Fiscal position', required=True),
        'report_type': fields.selection([
            ('deadlined', 'Order deadline'),
            ('line', 'Order line deadline'),
            ('discount', 'Discount check'),
            ('extract', 'Extract order'),
            # ('grouped', 'Order grouped by frame'),
            ], 'Report type', required=True),
        'statistic_category_id': fields.many2one(
            'statistic.category', 'Categoria statistica'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'only_remain': fields.boolean(
            'Only remain',
            help='Show only element to produce'),

        'from_date': fields.date('Dalla data', help='Date >='),
        'to_date': fields.date('Alla data', help='Date <'),
        'from_deadline': fields.date('Dalla scadenza', help='Date deadline >='),
        'to_deadline': fields.date('alla scadenza', help='Date deadline <'),

        'discount_limit': fields.char('Discount', size=64),
        'order_status': fields.selection([
            ('all', 'All order'),
            ('open', 'Open order'),
            ('close', 'Close order'),
            ], 'Order status', required=True),

        'data_sort': fields.selection([
            ('number', 'Order number'),
            ('deadline', 'Order deadline'),
            ], 'Data sort', required=True),

        'data_type': fields.selection([
            ('ma', 'Original order'),
            ('oc', 'OC'),
            ('b', 'B(locked)'),
            ('s', 'S(suspended)'),
            ], 'Data type', required=True),
        }

    _defaults = {
        'fiscal_position': lambda *x: 'all',
        'report_type': lambda *x: 'deadlined',
        'only_remain': lambda *x: True,
        # 'to_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
        'data_sort': lambda *x: 'number',
        'data_type': lambda *x: 'oc',
        'discount_limit': lambda *x: '50 + 20',
        'order_status': lambda *x: 'open',
        }
