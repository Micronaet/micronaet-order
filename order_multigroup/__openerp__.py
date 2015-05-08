# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Sale Order Multigroup',
    'version': '0.0.1',
    'category': 'Sale/Order',    
    'description': """
Every order has some particular elements called master line that manage
a subgroup of details so, in order, the module create the N sub lines as 
invisible sale.order.line but in offer we see only master and the total is
sum(elements).
The master fields has also a title and note elements that could be printed
in sale.order.
When the order is confirmed we see all lines that are used for unload stock
location.
    """,    
    'author': 'Micronaet s.r.l.',
    'website': 'http://www.micronaet.it',
    'depends': [
        'base',
        'sale',
        'report_aeroo',
        ],
    'init_xml': [], 
    'data': [
        #'security/ir.model.access.csv',
        'sale_view.xml',        
        'report/order_report.xml',
        #'data/hr_timesheet_invoice_data.xml',
        ],
    'demo_xml': [],
    'active': False, 
    'installable': True, 
    }
