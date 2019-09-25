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
import sys
import erppeek
import xlrd
import ConfigParser
import imaplib
import email

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cr = '\r\n'

# From config file:
cfg_file = os.path.expanduser('openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

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
message_pool = odoo.model('sale.order.message')
server_pool = odoo.model('sale.order.server')
product_pool = odoo.model('product.product')
partner_pool = odoo.model('res.partner')
user_pool = odoo.model('res.users')

server_ids= server_pool.search([
    ('scheduled', '=', True),
    ])

for mailbox in server_pool.browse(server_ids):    
    folder = mailbox.folder        
    server = mailbox.server
    port = mailbox.port
    username = mailbox.username
    password = mailbox.password
    SSL = mailbox.ssl

    # XXX create field for parameters?
    start = {
        'subject': 'ORDINE',
        'partner': 'CLIENTE',
        'article': 'ARTICOLO',
        'end': 'FINE',
        }
    hostname = str(server) #server = '%s:%s' % (server, port)

    # -------------------------------------------------------------------------
    # Read all email:
    # -------------------------------------------------------------------------
    try:
        if SSL:
            mail = imaplib.IMAP4_SSL(server)
        else:
            mail = imaplib.IMAP4(server)            
        mail.login(username, password)            
        mail.select(folder)
    except:
        raise osv.except_osv(
            _('Mail error'), 
            _('Cannot access mail server: %s' % hostname),
            )
            
    esit, result = mail.search(None, 'ALL')
    tot = 0
    for msg_id in result[0].split():
        tot += 1
        # Read and parse result:
        esit, result = mail.fetch(msg_id, '(RFC822)')
        eml_string = result[0][1]
        message = email.message_from_string(eml_string)
        record = {
            'To': '',
            'From': '',
            'Date': '',
            'Received': '',
            'Message-ID': '',
            'Subject': '',   
                 
            'Body': '',
            }
            
        # Populate parameters:
        for (param, value) in message.items():
            if param in record:
                record[param] += value

        # Populate body part:
        for part in message.walk():
            if part.get_content_type() in ('text/plain', 'text/html'):
                 record['Body'] += part.get_payload()
        
        # Auto user:
        # Try to search user from 'from address':
        # TODO create in res_users field: order_emails (list or sender)
        email_address = (
            record.get('From') or '').split('<')[-1].split('>')[0]
        user_id = 1 # Admin
        if email_address:
            user_ids = user_pool.search([
                ('login', '=', email_address),
                ])
            if user_ids:
                user_id = user_ids[0]
            
        # Parse body text:
        message_text = ''
        if record.get('Subject', '').startswith(start['subject']):
            text = record['Body']    
            switch = {
                'partner': False,
                'article': False,
                }
            data = {
                'partner': [], # 0. Name, 1. Street, 2. Country, 3. VAT...
                'article': [],
                }
            for line in text.split(cr):
                message_text += '%s\n' % line
                if line.startswith(start['partner']):
                    switch['partner'] = True
                    continue
                if line.startswith(start['article']):
                    switch['article'] = True
                    switch['partner'] = False
                    continue             
                if line.startswith(start['end']):
                    break
                
                if switch['partner']:
                     data['partner'].append(line.strip())
                elif switch['article']:
                     data['article'].append(line.strip())
                          
            # -----------------------------------------------------------------
            # Partner part:
            # -----------------------------------------------------------------
            try:
                partner_ids = partner_pool.search([
                    ('name', '=', data['partner'][0]),
                    ])
                partner_id = partner_ids[0]
            except:
                #_logger.error('Partner not found!')
                partner_id = False
            
            # -----------------------------------------------------------------
            # Detail:
            # -----------------------------------------------------------------
            for line in data['article']:
                row = line.split('*') # TODO do better
                
                # -------------------------------------------------------------
                # Product:
                # -------------------------------------------------------------
                line_error = False
                try:
                    default_code = row[0].strip().upper()
                
                    product_ids = product_pool.search([
                        ('default_code', '=', default_code),
                        ])
                    if product_ids:
                        product_id = product_ids[0]
                except:
                    line_error = True
                    #_logger.error('Product code not found %s!' % line)
                    product_id = False
                    
                # -------------------------------------------------------------
                # Quantity:
                # -------------------------------------------------------------
                try:
                    product_qty = clean_float(row[1])
                except:
                    line_error = True
                    #_logger.error('Quantity not found %s!' % line)
                    product_qty = 0.0    

                # -------------------------------------------------------------
                # Price:
                # -------------------------------------------------------------
                try:
                    price = clean_float(row[2])

                except:
                    line_error = True
                    #_logger.error('Price not found %s!' % line)
                    price = 0.0    

                # -------------------------------------------------------------
                # Discount:
                # -------------------------------------------------------------
                # TODO 

                if line_error:
                    # TODO log error
                    continue
            
            # TODO Check valid message
                                            
            # Create message:
            message = {
                'name': record.get('Message-ID'),
                'user_id': user_id,
                'partner_id': partner_id,
                'server_id': mailbox.id,
                'message_text': message_text,
                'original_text': message_text, # record.get('Body'),
                'error_text': '', # TODO             
                #'state': # TODO                     
                }
            try:
                message_pool.create(message)                    
                print 'Mesage imported: %s' % message
                # TODO Mark as deleted (or move)<<<< AFTER ALL!!:
                #mail.store(msg_id, '+FLAGS', '\\Deleted')
            except:
                print 'Not weel formed message: %s' % message
                continue


    # -------------------------------------------------------------------------
    # Close operations:    
    # -------------------------------------------------------------------------
    #mail.expunge() # TODO clean trash bin
    mail.close()
    mail.logout()        
