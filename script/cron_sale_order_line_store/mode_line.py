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
from datetime import datetime

argv = sys.argv
if len(argv) == 2:
    open_mode = argv[-1].lower()
else:
    open_mode = 'fia'
print('Open Mode: %s' % open_mode)

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.%s.cfg' % open_mode)

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint


# Log file:
log_file = './log/%s_SALE_activity.log' % open_mode
log_f = open(log_file, 'a')
update = {}


def write_log(event, mode='INFO', verbose=True):
    """ Write log
    """
    log_f.write('%s. %s [%s] %s\n' % (
        datetime.now(),
        open_mode,
        mode,
        event,
    ))


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
    'http://%s:%s' % (server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
line_pool = odoo.model('sale.order.line')

# ----------------------------------------------------------------------------------------------------------------------
# Update state:
# ----------------------------------------------------------------------------------------------------------------------
line_ids = line_pool.search([
    ('order_id.state', 'not in', ('cancel', 'draft', 'sent', 'done')),
    ('state', '=', 'draft'),
])

counter = 0
total = len(line_ids)
write_log('Start update state: Tot. %s' % total)
if line_ids:
    for line in line_pool.browse(line_ids):
        counter += 1
        order = line.order_id
        print('%s / %s Update state order = %s line ID %s' % (counter, total, order.name, line.id))

write_log('End update: Tot. %s [UPD %s]' % (total, counter))

# -----------------------------------------------------------------------------
# Agente:
# -----------------------------------------------------------------------------
query_file = './sql/%s_order_agent.sql' % open_mode

line_ids = line_pool.search([
    # ('state', 'not in', ('cancel', 'draft', 'sent')),
    ('mx_agent_id', '=', False),
    ('order_id.partner_id.agent_id', '!=', False),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]

if line_ids:
    for line in line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            mx_agent_id = line.order_id.partner_id.agent_id.id
            print('Update %s of %s: %s' % (counter, total, mx_agent_id))
            query = \
                'UPDATE sale_order_line set mx_agent_id=%s WHERE id=%s;\n' % (
                    mx_agent_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1

        except:
            print('%s. %s: Error updating line, no agent %s' % (counter, total, line_id))
            update[query_file][1] += 1

query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (dbname, query_file)
    os.system(command)
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
else:
    write_log('No neet to update agent %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

if open_mode == 'fia':
    # -------------------------------------------------------------------------
    # Famiglia:
    # -------------------------------------------------------------------------
    query_file = './sql/%s_order_family.sql' % open_mode

    line_ids = line_pool.search([
        # ('state', 'not in', ('cancel', 'draft', 'sent')),
        ('family_id', '=', False),
        ('product_id.family_id', '!=', False),
        ])
    counter = 0
    total = len(line_ids)
    query_f = open(query_file, 'w')
    write_log('Start update %s: Tot. %s' % (query_file, total))
    update[query_file] = [0, 0]

    if line_ids:
        for line in line_pool.browse(line_ids):
            counter += 1
            try:
                line_id = line.id
                product_name = 'Non trovato'
                product = line.product_id
                product_name = product.name
                product_family_id = product.family_id.id
                print('Update %s of %s: %s' % (counter, total, product_family_id))

                query = \
                    'UPDATE sale_order_line set family_id=\'%s\' ' \
                    'WHERE id=%s;\n' % (product_family_id, line_id)
                query_f.write(query)  # Not work ORM with function fields
                update[query_file][0] += 1

            except:
                print('%s. %s: Error updating line %s >> %s' % (
                    counter, total, line_id, product_name))
                update[query_file][1] += 1
    query_f.close()
    if update[query_file][0] > 0:
        command = 'psql -d %s -a -f %s' % (dbname, query_file)
        write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))
        os.system(command)
    else:
        write_log('No neet to update family %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))

    # -------------------------------------------------------------------------
    # Update season:
    # -------------------------------------------------------------------------
    query_file = './sql/%s_order_season.sql' % open_mode
    line_ids = line_pool.search([
        # ('state', 'not in', ('cancel', 'draft', 'sent')),
        ('order_id.date_order', '!=', False),
        ('season_period', '=', False),
        ])
    counter = 0
    total = len(line_ids)
    query_f = open(query_file, 'w')
    write_log('Start update %s: Tot. %s' % (query_file, total))
    update[query_file] = [0, 0]

    if line_ids:
        for line in line_pool.browse(line_ids):
            counter += 1
            order = line.order_id
            date_order = order.date_order
            season_period = get_season_from_date(date_order)
            print('Update %s of %s: %s >> %s' % (counter, total, date_order, season_period))

            query = \
                'UPDATE sale_order_line set season_period=\'%s\' ' \
                'WHERE id=%s;\n' % (season_period, line.id)
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
    query_f.close()
    if update[query_file][0] > 0:
        command = 'psql -d %s -a -f %s' % (dbname, query_file)
        write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))
        os.system(command)
    else:
        write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))
