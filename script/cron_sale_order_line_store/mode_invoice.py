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


def get_season_from_date(date_invoice):
    """ Return season from date
    """
    start_month = '09'
    if not date_invoice:
        return False
    current_month = date_invoice[5:7]
    year = int(date_invoice[2:4])
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
invoice_line_pool = odoo.model('account.invoice.line')

# Log file:
log_file = './log/%s_INVOICE_activity.log' % open_mode
log_f = open(log_file, 'a')
update = {}


def write_log(event, mode='INFO', verbose=True):
    """ Write log
    """
    log_f.write('%s. [%s] %s\n' % (
        datetime.now(),
        mode,
        event,
    ))


# -----------------------------------------------------------------------------
# Zona:
# -----------------------------------------------------------------------------
query_file = './sql/%s_zone_state.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('zone_id', '=', False),
    ('invoice_id.partner_id.zone_id', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        line_id = line.id
        try:
            zone_id = line.invoice_id.partner_id.zone_id.id
            print('Update %s of %s: %s' % (counter, total, zone_id))
            query = \
                'UPDATE account_invoice_line SET zone_id=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    zone_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (counter, total, line_id))
query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
else:
    write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

# -----------------------------------------------------------------------------
# Regione:
# -----------------------------------------------------------------------------
query_file = './sql/%s_region_state.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('region_id', '=', False),
    ('invoice_id.partner_id.state_id.region_id', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            region_id = line.invoice_id.partner_id.state_id.region_id.id
            print('Update %s of %s: %s' % (counter, total, region_id))
            query = \
                'UPDATE account_invoice_line SET region_id=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    region_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (
                counter, total, line_id))
query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
else:
    write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

# -----------------------------------------------------------------------------
# Città (state_id):
# -----------------------------------------------------------------------------
query_file = './sql/%s_invoice_state.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('state_id', '=', False),
    ('invoice_id.partner_id.state_id', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            state_id = line.invoice_id.partner_id.state_id.id
            print('Update %s of %s: %s' % (counter, total, state_id))
            query = \
                'UPDATE account_invoice_line SET state_id=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    state_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (
                counter, total, line_id))
query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
else:
    write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

# -----------------------------------------------------------------------------
# Nazione:
# -----------------------------------------------------------------------------
query_file = './sql/%s_invoice_country.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('country_id', '=', False),
    ('invoice_id.partner_id.country_id', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            country_id = line.invoice_id.partner_id.country_id.id
            print('Update %s of %s: %s' % (counter, total, country_id))
            query = \
                'UPDATE account_invoice_line SET country_id=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    country_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (
                counter, total, line_id))
query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
else:
    write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

# -----------------------------------------------------------------------------
# Invoice date:
# -----------------------------------------------------------------------------
query_file = './sql/%s_invoice_date.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('date_invoice', '=', False),
    ('invoice_id.date_invoice', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
pdb.set_trace()
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            date_invoice = line.invoice_id.date_invoice
            if not date_invoice:
                print('Cannot update %s of %s: %s' % (counter, total, date_invoice))
                continue
            print('Update %s of %s: %s' % (counter, total, date_invoice))
            query = \
                'UPDATE account_invoice_line SET date_invoice=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    date_invoice, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (
                counter, total, line_id))
query_f.close()
command = 'psql -d %s -a -f %s' % (
    dbname,
    query_file,
)
write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
    query_file, total, update[query_file][0], update[query_file][1]))
os.system(command)

# -----------------------------------------------------------------------------
# Agente:
# -----------------------------------------------------------------------------
query_file = './sql/%s_invoice_agent.sql' % open_mode
line_ids = invoice_line_pool.search([
    ('mx_agent_id', '=', False),
    ('invoice_id.partner_id.agent_id', '!=', False),
    ('type', '=', 'out_invoice'),
    ])
counter = 0
total = len(line_ids)
query_f = open(query_file, 'w')
write_log('Start update %s: Tot. %s' % (query_file, total))
update[query_file] = [0, 0]
if line_ids:
    for line in invoice_line_pool.browse(line_ids):
        counter += 1
        try:
            line_id = line.id
            mx_agent_id = line.invoice_id.partner_id.agent_id.id
            print('Update %s of %s: %s' % (counter, total, mx_agent_id))
            query = \
                'UPDATE account_invoice_line SET mx_agent_id=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    mx_agent_id, line_id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
        except:
            update[query_file][1] += 1
            print('%s. %s: Error updating line %s' % (
                counter, total, line_id))
query_f.close()
if update[query_file][0] > 0:
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
else:
    write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))

if open_mode == 'fia':
    # -------------------------------------------------------------------------
    # Famiglia:
    # -------------------------------------------------------------------------
    query_file = './sql/%s_invoice_family.sql' % open_mode

    line_ids = invoice_line_pool.search([
        ('family_id', '=', False),
        ('product_id.family_id', '!=', False),
        ('type', '=', 'out_invoice'),
        ])
    counter = 0
    total = len(line_ids)
    query_f = open(query_file, 'w')
    write_log('Start update %s: Tot. %s' % (query_file, total))
    update[query_file] = [0, 0]

    if line_ids:
        for line in invoice_line_pool.browse(line_ids):
            counter += 1
            try:
                line_id = line.id
                product_name = 'Non trovato'
                product = line.product_id
                product_name = product.name
                product_family_id = product.family_id.id
                print('Update %s of %s: %s' % (
                    counter, total, product_family_id))

                query = \
                    'UPDATE account_invoice_line SET family_id=\'%s\' ' \
                    'WHERE id=%s;\n' % (
                        product_family_id, line_id,
                    )
                query_f.write(query)  # Not work ORM with function fields
                update[query_file][0] += 1
            except:
                print('%s. %s: Error updating line %s >> %s' % (
                    counter, total, line_id, product_name))
                update[query_file][1] += 1
    query_f.close()
    if update[query_file][0]:
        command = 'psql -d %s -a -f %s' % (
            dbname,
            query_file,
        )
        write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))
        os.system(command)
    else:
        write_log('No need to update %s: Tot. %s [UPD %s - ERR %s]' % (
            query_file, total, update[query_file][0], update[query_file][1]))

    # -------------------------------------------------------------------------
    # Update season:
    # -------------------------------------------------------------------------
    query_file = './sql/%s_invoice_season.sql' % open_mode
    line_ids = invoice_line_pool.search([
        ('type', '=', 'out_invoice'),
        ('season_period', '=', False),
        ])
    counter = 0
    total = len(line_ids)
    query_f = open(query_file, 'w')
    write_log('Start update %s: Tot. %s' % (query_file, total))
    update[query_file] = [0, 0]

    if line_id:
        for line in invoice_line_pool.browse(line_ids):
            counter += 1
            invoice = line.invoice_id
            date_invoice = invoice.date_invoice
            season_period = get_season_from_date(date_invoice)
            print('Update %s of %s: %s >> %s' % (
                counter, total, date_invoice, season_period))

            query = \
                'UPDATE account_invoice_line set season_period=\'%s\' ' \
                'WHERE id=%s;\n' % (
                    season_period, line.id,
                )
            query_f.write(query)  # Not work ORM with function fields
            update[query_file][0] += 1
    query_f.close()
    command = 'psql -d %s -a -f %s' % (
        dbname,
        query_file,
    )
    write_log('End update %s: Tot. %s [UPD %s - ERR %s]' % (
        query_file, total, update[query_file][0], update[query_file][1]))
    os.system(command)
