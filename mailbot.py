#!/usr/bin/env python
# encoding: utf-8

"""
Tiny mail robot.
Reference: http://pymotw.com/2/smtpd/index.html
"""

from smtpd import PureProxy
import asyncore
import smtplib
import email.utils
from email.mime.text import MIMEText
import threading
import time
import argparse
import signal
import logging

import yapdi

###############################################################################
#  EDIT ME <3
###############################################################################

NEWLINE = '\n'
COMMASPACE = ', '
MAX_MAIL_PER_MINUTE = 10
MAX_MAIL_PER_HOUR = MAX_MAIL_PER_MINUTE * 60
ALERT_THRESHILD = 20 
BOT_ADDRESS = 'MailBot@cylee.com'
OP_ADDRESS = ['marlboromoo@gmail.com', 'timothy.lee@104.com.tw']
PURGE_OVER_THRESHOLD = True
DEBUG = True

###############################################################################
#  MailBot <3
###############################################################################

class BotsSMTPServer(PureProxy):

    """ Custom SMTP server to transfer message.
    SMTPServer is an old style class, see the follow link for more information:
    http://hg.python.org/cpython/file/2.7/Lib/smtpd.py
    """
    mail_queue = []
    counter = 0 
    last_reset = None #. in Epoch.

    def process_message(self, peer, mailfrom, rcpttos, data):
        """Handle messages from the client.

        :peer: a tuple containing (ipaddr, port) of the client.
        :mailfrom: raw address the client coming from.
        :rcpttos: a list of raw addresses to deliver the message to.
        :data: entire full text of the mesasge.
        :returns: None for a normal '250 Ok' response or response string.

        """
        #. Relay mail
        if self._under_threshold():
            logging.info(
                ">> Relay message - mailfrom: %s, rcpttos: %s" % (
                    mailfrom, rcpttos))
            self._relay(mailfrom, rcpttos, data)
        #. Put in queue
        else:
            logging.info(
                "++ Queue message - mailfrom: %s, rcpttos: %s" % (
                    mailfrom, rcpttos))
            self.mail_queue.append((peer, mailfrom, rcpttos, data))
        return

    def flush_message(self):
        """Flush the message in mail queue.

        :returns: True if flush a message else False

        """
        if len(self.mail_queue) > 0:
            peer, mailfrom, rcpttos, data = self.mail_queue.pop(0)
            if self._under_threshold():
                self._relay(mailfrom, rcpttos, data)
                return True
            else:
                self.mail_queue.insert(0, (peer, mailfrom, rcpttos, data))
        return False

    def purge_queue(self):
        """Purge the mail queue.
        """
        logging.info("!! Purge the mail queue.")
        self.mail_queue = []

    def reset_counter(self):
        """Reset the mail counter.
        """
        logging.info("** Reset the counter.")
        self.counter = 0
        self.last_reset = int(time.time())

    def _relay(self, mailfrom, rcpttos, data):
        """Relay the message.
        """
        refused = self._deliver(mailfrom, rcpttos, data)
        self.counter += 1
        if refused:
            logging.info('!! We got some refusals:', refused)

    def _fix_header(self, peer, data):
        """Insert 'X-Peer' mail header.

        :peer: a tuple containing (ipaddr, port) of the client.
        :data: entire full text of the mesasge.
        :returns: data with 'X-Peer' mail header.

        """
        lines = data.split(NEWLINE)
        # Look for the last header
        i = 0
        for line in lines:
            if not line:
                break
            i += 1
        lines.insert(i, 'X-Peer: %s' % (peer[0]))
        return NEWLINE.join(lines)

    def _under_threshold(self):
        """Check if reach rate limit.

        :returns: True if not reach rate limit else False.

        """
        return True if self.counter < MAX_MAIL_PER_MINUTE else False


class MailBot(object):

    """ Tiny mail robot.
    """

    def __init__(self, localaddr, remoteaddr):
        """Initial the MailBot.

        :localaddr: (address, port)
        :remotedddr: (address, port)

        """
        self.localaddr = localaddr
        self.remoteaddr = remoteaddr
        self.is_start = None

    def start(self):
        """Start the MailBot.
        """
        logging.info("MailBot - tiny mail robot.")
        self.smtp = BotsSMTPServer(self.localaddr, self.remoteaddr)
        self.smtp.last_reset = int(time.time())
        self.is_start = True
        #. smtp server
        self.smtp_thread = threading.Thread(
            target=asyncore.loop,
            kwargs= {'timeout' : 1})
        self.smtp_thread.setDaemon(True)
        self.smtp_thread.start()
        #. reseter
        self.reseter_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec': 60, 'fun' : self.smtp.reset_counter}
        )
        self.reseter_thread.setDaemon(True)
        self.reseter_thread.start()
        #. checker
        self.checker_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec' : 60, 'fun' : self.flush_and_check}
        )
        self.checker_thread.setDaemon(True)
        self.checker_thread.start()
        logging.info("* Server listen at %s:%s." % (
            self.localaddr[0], self.localaddr[1]))
        logging.info("* Quit the server with CONTROL+C.")
        self.notice(text='<3', subject='MailBot start!')

    def stop(self):
        """Stop the MailBot.
        """
        logging.info('!! Stop the server ...')
        self.is_start = False
        self.smtp.close() #. asyncore.dispatcher.close()
        #. TODO: Gracefully stop the threads.
        #logging.info("!! Waiting the threads ... ")
        #self.smtp_thread.join()
        #self.reseter_thread.join()
        #self.checker_thread.join()
        #logging.info("!! All threads stop. ")
        self.notice(text='<3', subject='MailBot stop!')
        logging.info('Done.')

    def count(self):
        """Count the mails in the queue.

        :returns: Numbers of mail in the queue.

        """
        return len(self.smtp.mail_queue)

    def stats(self):
        """ Print the status of BotsSMTPServer.
        """
        logging.info("** Counter: %s, Queue: %s, Reset: %s " % (
            self.smtp.counter,
            self.count(),
            self.smtp.last_reset,
        ))

    def check(self):
        """Check the status of BotsSMTPServer.
        """
        logging.info("** Check the mail queue.")
        emails = self.count()
        if emails > ALERT_THRESHILD:
            self.notice(text="There are %s emails in the queue." % (emails),
                        subject="Too many emails in the queue!!"
                       )
            #. purge the mail queue
            if PURGE_OVER_THRESHOLD:
                self.smtp.purge_queue()
        if not DEBUG:
            self.stats()

    def flush(self):
        """Flush the mails in the queue.
        """
        logging.info("%s ** Flush the mail queue.")
        i = 0
        mails = self.count()
        while i < mails:
            #. Reach the rate limit.
            if not self.smtp.flush_message():
                break
            i += 1

    def flush_and_check(self):
        """Flush the mail queue first then check the mail queue stats.
        """
        self.flush()
        self.check()

    def notice(self, text, subject):
        """Notice the operators.
        """
        msg = self._create_msg(text, BOT_ADDRESS, OP_ADDRESS, subject)
        self._send_msg(msg, BOT_ADDRESS, OP_ADDRESS)

    def _send_msg(self, msg, from_, to):
        """Send message, like a MUA.

        :msg: MIME message.
        :from_: the sender's email address.
        :to: a list of the recipient's email addresss.
        :returns: @todo

        """
        try:
            server = smtplib.SMTP(self.remoteaddr[0], self.remoteaddr[1])
            server.sendmail(from_, to, msg.as_string())
        finally:
            server.quit()

    def _create_msg(self, message, from_, to, subject):
        """Create raw mail message.

        :message: text to send.
        :from_: the sender's email address.
        :to: a list of the recipient's email addresss.
        :returns: MIME message.

        """
        msg = MIMEText(message)
        msg['From'] = self._formataddr(from_)
        msg['To'] = COMMASPACE.join([self._formataddr(i) for i in to])
        msg['Subject'] = subject
        return msg

    def _formataddr(self, addr):
        """Like the 'email.utils.formataddr' but generate the sender name automatic.

        :addr: email address.
        :returns: the string value suitable for an RFC 2822 From/To/Cc header

        """
        return email.utils.formataddr((addr.split('@')[0], addr))

    def _timer(self, sec, fun):
        """Reset the stats of BotsSMTPServer
        """
        i = 0
        while True:
            if self.is_start:
                time.sleep(1)
                i += 1
                #print i
                if i == sec:
                    fun()
                    i = 0
            else:
                break

def sigterm_handler(signum, frame):
    """Handle the SIGTERM signal.
    See: http://docs.python.org/2/library/signal.html
    """
    raise KeyboardInterrupt

def main():
    #. logger
    logging.basicConfig(
        filename='/tmp/mailbot.log',
        format='%(asctime)s - %(levelname)s - %(message)s',
        #datefmt='%Y-%M-%d %H:%M:%S',
        level=logging.DEBUG
    )
    #. parse arg
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    args = parser.parse_args()
    daemon = yapdi.Daemon(pidfile='/tmp/mailbot.pid')
    if args.action == 'start':
        logging.info('Start MailBot ...')
        #. daemonize
        daemon.daemonize()
        try:
            #. Handle the SIGTERM: https://github.com/kasun/YapDi/blob/master/yapdi.py
            signal.signal(signal.SIGTERM, sigterm_handler)
            #. mailbot
            bot = MailBot(('127.0.0.1', 1025), ('127.0.0.1', 25))
            bot.start()
            while True:
                if DEBUG:
                    bot.stats()
                time.sleep(1) 
        except KeyboardInterrupt:
            bot.stop()
    if args.action == 'stop':
        logging.info('Stop MailBot ...')
        daemon.kill()

if __name__ == '__main__':
    main()

