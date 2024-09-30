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
import pdb
import sys
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.fia')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint


def get_season_from_date(date_order):
    """ Return season from date
    """
    start_month = '09'
    if not date_order:
        return False
    current_month = date_order[5:7]
    year = int(date_order[2:4])
    if current_month >= start_month:  # [09 : 12]
        return '%02d-%02d' % (year, year + 1)
    else:  # [01 : 08]
        return '%02d-%02d' % (year - 1, year)


# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
line_pool = odoo.model('sale.order.line')

# -----------------------------------------------------------------------------
# Agente:
# -----------------------------------------------------------------------------
query_file = 'order_agent.sql'

line_ids = line_pool.search([
    ('state', 'not in', ('cancel', 'draft', 'sent')),
    ('mx_agent_id', '=', False),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
for line in line_pool.browse(line_ids):
    counter += 1
    try:
        line_id = line.id
        mx_agent_id = line.order_id.partner_id.agent_id.id
        print('Update %s of %s: %s' % (counter, total, mx_agent_id))
        query = \
            'UPDATE sale_order_line set mx_agent_id=\'%s\' WHERE id=%s;\n' % (
                mx_agent_id, line_id,
            )
        query_f.write(query)  # Not work ORM with function fields
    except:
        print('%s. %s: Error updating line %s' % (
            counter, total, line_id))
query_f.close()
command = 'psql -d %s -a -f %s' % (
    dbname,
    query_file,
)
os.system(command)

# -----------------------------------------------------------------------------
# Famiglia:
# -----------------------------------------------------------------------------
query_file = 'order_family.sql'

line_ids = line_pool.search([
    ('state', 'not in', ('cancel', 'draft', 'sent')),
    ('family_id', '=', False),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
for line in line_pool.browse(line_ids):
    counter += 1
    try:
        line_id = line.id
        product_name = 'Non trovato'
        product = line.product_id
        product_name = product.name
        product_family_id = product.product_family_id.id
        print('Update %s of %s: %s' % (counter, total, product_family_id))

        query = \
            'UPDATE sale_order_line set family_id=\'%s\' WHERE id=%s;\n' % (
                product_family_id, line_id,
            )
        query_f.write(query)  # Not work ORM with function fields
    except:
        print('%s. %s: Error updating line %s >> %s' % (
            counter, total, line_id, product_name))

query_f.close()

command = 'psql -d %s -a -f %s' % (
    dbname,
    query_file,
)
os.system(command)

# -----------------------------------------------------------------------------
# Update season:
# -----------------------------------------------------------------------------
query_file = 'order_season.sql'
line_ids = line_pool.search([
    ('state', 'not in', ('cancel', 'draft', 'sent')),
    ('season_period', '=', False),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
for line in line_pool.browse(line_ids):
    counter += 1
    order = line.order_id
    date_order = order.date_order
    season_period = get_season_from_date(date_order)
    print('Update %s of %s: %s >> %s' % (
        counter, total, date_order, season_period))

    query = \
        'UPDATE sale_order_line set season_period=\'%s\' WHERE id=%s;\n' % (
            season_period, line.id,
        )
    query_f.write(query)  # Not work ORM with function fields

query_f.close()
command = 'psql -d %s -a -f %s' % (
    dbname,
    query_file,
)
os.system(command)

