#!/usr/bin/env python
# encoding: utf-8

"""
Script to generate spams.
"""

import random
import smtplib
import email.utils
from email.mime.text import MIMEText

MSG_FROM = 'spam@robotkingdom.lab'
MSG_TO = ['timothy.lee@104.com.tw', 'marlboromoo@gmail.com']
MAX = 20

def formataddr(addr):
    return email.utils.formataddr((addr.split('@')[0], addr))

def create_msg():
    msg = MIMEText('I have %i girl friends.' % (random.randint(1, 1000)))
    msg['From'] = formataddr(MSG_FROM)
    msg['To'] = ', '.join(formataddr(i) for i in MSG_TO)
    msg['Subject'] = 'ohya <3'
    return msg

def main():
    server = smtplib.SMTP('127.0.0.1', 1025)
    #server.set_debuglevel(True) # show communication with the server
    try:
        i = 0
        while i < MAX:
            print 'Sending message ...'
            msg = create_msg()
            server.sendmail(MSG_FROM, MSG_TO, msg.as_string())
            i += 1
    finally:
        server.quit()
        print 'Done!'

if __name__ == '__main__':
    main()
