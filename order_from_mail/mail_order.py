#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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
import logging
import openerp
import imaplib
import email

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

class SaleOrderServer(orm.Model):
    """ Model name: SaleOrderServer
    """
    
    _name = 'sale.order.server'
    _description = 'Mail server'
    _order = 'name'
    
    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def force_download_new_mail(self, cr, uid, ids, context=None):
        ''' Button to force read current mailbox
        '''
        def clean_float(value):
            ''' Clean float from text
            '''
            try:
                return float(value.replace(' ', '').replace(',', '.'))
            except:
                return 0.0    
            
        # Pool used:
        user_pool = self.pool.get('res.users')
        partner_pool = self.pool.get('res.partner')
        product_pool = self.pool.get ('product.product')
        message_pool = self.pool.get('sale.order.message')


        mail_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        cr = '\r\n'
        folder = mail_proxy.folder        
        server = mail_proxy.server
        port = mail_proxy.port
        username = mail_proxy.username
        password = mail_proxy.password
        SSL = mail_proxy.ssl

        # XXX create field for parameters?
        start = {
            'subject': 'ORDINE',
            'partner': 'CLIENTE',
            'article': 'ARTICOLO',
            'end': 'FINE',
            }
        hostname = str(server) #server = '%s:%s' % (server, port)

        # -----------------------------------------------------------------
        # Read all email:
        # -----------------------------------------------------------------
        try:
            if SSL:
                mail = imaplib.IMAP4(server)            
                #mail = imaplib.IMAP4_SSL(server)
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
            user_id = uid # Current user
            if email_address:
                user_ids = user_pool.search(cr, uid, [
                    ('login', '=', email_address),
                    ], context=context)
                if user_ids:
                    user_id = user_ids[0]
                
            # Parse body text:
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
                              
                # -------------------------------------------------------------
                # Partner part:
                # -------------------------------------------------------------
                try:
                    partner_ids = partner_pool.search(cr, uid, [
                        ('name', '=', data['partner'][0]),
                        ], context=context)
                    partner_id = partner_ids[0]
                except:
                    _logger.error('Partner not found!')
                    partner_id = False
                
                # -------------------------------------------------------------
                # Detail:
                # -------------------------------------------------------------
                for line in data['article']:
                    row = line.split('*') # TODO do better
                    
                    # ---------------------------------------------------------
                    # Product:
                    # ---------------------------------------------------------
                    line_error = False
                    try:
                        default_code = row[0].strip().upper()
                    
                        product_ids = product_pool.search(cr,uid, [
                            ('default_code', '=', default_code),
                            ], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                    except:
                        line_error = True
                        _logger.error('Product code not found %s!' % line)
                        product_id = False
                        
                    # ---------------------------------------------------------
                    # Quantity:
                    # ---------------------------------------------------------
                    try:
                        product_qty = clean_float(row[1])
                    except:
                        line_error = True
                        _logger.error('Quantity not found %s!' % line)
                        product_qty = 0.0    

                    # ---------------------------------------------------------
                    # Price:
                    # ---------------------------------------------------------
                    try:
                        price = clean_float(row[2])
                    except:
                        line_error = True
                        _logger.error('Price not found %s!' % line)
                        price = 0.0    

                    # ---------------------------------------------------------
                    # Discount:
                    # ---------------------------------------------------------
                    # TODO 

                    if line_error:
                        # TODO log error
                        continue
                                                
                # Create message:
                message_pool.create(cr, uid, {
                    'name': record.get('Message-ID'),
                    'user_id': user_id,
                    'partner_id': partner_id,
                    'server_id': ids[0],
                    'message_text': record.get('Body'),
                    'original_text': record.get('Body'),
                    'error_text': '', # TODO             
                    #'state': # TODO                     
                    }, context=context)                    


            # TODO Mark as deleted (or move)<<<< AFTER ALL!!:
            # mail.store(msg_id, '+FLAGS', '\\Deleted')

        # -----------------------------------------------------------------
        # Close operations:    
        # -----------------------------------------------------------------
        #mail.expunge() # TODO clean trash bin
        mail.close()
        mail.logout()        
        return True
    
    # -------------------------------------------------------------------------
    # Scheduled action:
    # -------------------------------------------------------------------------
    
    _columns = {
        'name': fields.char(
            'Name', size=64, required=True, 
            help='Mailbox name, ex.: Sales for Fiam'),            
        'server': fields.char(
            'Server name', size=64, required=True, 
            help='Server mail name, ex. mail.google.com'),            
        'folder': fields.char(
            'Folder name', size=64, required=True, 
            help='Folder where check the messages'),
        'port': fields.integer('Port Server', required=True, 
            help='Port Server, ex.: 993'),
        'username': fields.char(
            'Username', size=64, required=True, 
            help='Username, ex. sales@example.it'),
        'password': fields.char(
            'Password', size=64, required=True),
        'ssl': fields.boolean('SSL', help='Server has SSL protocol'),
        'scheduled': fields.boolean(
            'Scheduled', help='Will be lauched in schedule interval'),
        } 
        
    _defaults = {
        'folder': lambda *x: 'INBOX',
        'port': lambda *x: 993,
        }    

class SaleOrderMessage(orm.Model):
    """ Model name: SaleOrderMail
    """
    
    _name = 'sale.order.message'
    _description = 'Mail order received'
    _order = 'name'
    
    _columns = {
        'name': fields.char(
            'Message ID', size=80, required=True, 
            help='ID of message on mail server'),

        'user_id': fields.many2one(
            'res.users', 'Sender',
            help='User who send the email order'),
        'partner_id': fields.many2one(
            'res.partner', 'Partner', help='Sale order partner (if found)'),
        'order_id': fields.many2one(
            'sale.order', 'Sale order',            
            help='Sale order created from this message'),
        'server_id': fields.many2one(
            'sale.order.server', 'Server',            
            help='Mail server where message was downloaded'),
            
        'message_text': fields.text(
            'Text', help='Text message extracted from mail'),
        'original_text': fields.text(
            'Original message',
            help='Original message extracted from mail'),
        'error_text': fields.text(
            'Error message', help='Error found in text message'),
            
        'state': fields.selection([
            ('draft', 'Draft'),
            ('error', 'Error'),
            ('done', 'Done'),           
            ], 'State'),            
        }

    _defaults = {
        'state': lambda *x: 'draft',
        }
 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
