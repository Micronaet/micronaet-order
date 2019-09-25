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
        mail_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        cr = '\r\n'
        folder = mail_proxy.folder
        
        # TODO change:        
        server = 'imap.gmail.com'
        port = '993'
        username = 'ced@fiam.it'
        password = 'vainRyg8'
        SSL = True
        folder = 'INBOX'

        # XXX create field for parameters?
        start = {
            'subject': 'ORDINE',
            'partner': 'CLIENTE',
            'article': 'ARTICOLO',
            'end': 'FINE',
            }
        hostname = server #server = '%s:%s' % (server, port)

        # -----------------------------------------------------------------
        # Read all email:
        # -----------------------------------------------------------------
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
            email_address = (
                record.get('From') or '').split('<')[-1].split('>')[0]
            # TODO find user user_id = 1
                
            #if email_address:
            #    # Search user:
            #    user_ids = user_pool.search(cr, uid, [
            #        ('email', '=', email_address),
            #        ], context=context)d
            #    if user_ids:
            #        user_id = user_ids[0]

            # Parse body text:
            import pdb; pdb.set_trace() 
            if record.get('Subject', '').startswith(start['subject']):
                text = record['Body']    
                switch = {
                    'partner': False,
                    'article': False,
                    }
                data = {
                    'partner': [],
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
                              
                # TODO create sale.order.message
                # partner cercarlo nel database
                # articoli vedrificare il codice 
                # errori di confersione numerici 
                
                # usare: data
            

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
            'Server name', size=64, required=True, 
            help='Server mail name, ex. mail.google.com'),
        'folder': fields.char(
            'Folder name', size=64, required=True, 
            help='Folder where check the messages'),
        'server': fields.char(
            'Server', size=64, required=True, 
            help='Indirizzo server mail'),
        
            
        # TODO
        }
        
    _defaults = {
        'folder': lambda *x: 'INBOX',
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
            
        # TODO
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
