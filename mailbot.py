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

NEWLINE = '\n'
COMMASPACE = ', '
MAX_MAIL_PER_MINUTE = 10
MAX_MAIL_PER_HOUR = MAX_MAIL_PER_MINUTE * 60
ALERT_THRESHILD = 20 
BOT_ADDRESS = 'MailBot@cylee.com'
OP_ADDRESS = ['marlboromoo@gmail.com', 'timothy.lee@104.com.tw']

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
        #. Debug mesasges
        #print type(peer), type(mailfrom), type(rcpttos), type(data)
        #print "Receiving message from:", peer
        #print "Message addressed from:", mailfrom
        #print "Message addressed to:", rcpttos
        #print "Message length:", len(data)
        #print "Message body:", data
        #data = self._fix_header(peer, data)
        #print "Message body after fix:", data

        #. Relay mail
        if self._under_threshold():
            self._relay(mailfrom, rcpttos, data)
        #. Put in queue
        else:
            self.mail_queue.append((peer, mailfrom, rcpttos, data))
        return

    def flush_message(self):
        """Flush the message in mail queue
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

    def reset_counter(self):
        """@todo: Docstring for reset_counter.
        :returns: @todo
        """
        self.counter = 0
        self.last_reset = int(time.time())

    def _relay(self, mailfrom, rcpttos, data):
        """Relay the message
        :returns: @todo

        """
        refused = self._deliver(mailfrom, rcpttos, data)
        self.counter += 1
        if refused:
            print '! We got some refusals:', refused

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
        """Start the MailBot
        """
        self.smtp = BotsSMTPServer(self.localaddr, self.remoteaddr)
        self.smtp.last_reset = time.time()
        self.is_start = True
        #. smtp server
        self.smtp_thread = threading.Thread(
            target=asyncore.loop,
            kwargs= {'timeout' : 1})
        self.smtp_thread.start()
        #. reseter
        self.reseter_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec': 60, 'fun' : self.smtp.reset_counter}
        )
        self.reseter_thread.start()
        #. cleaner
        self.cleaner_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec' : 60, 'fun' : self.flush}
        )
        self.cleaner_thread.start()
        #. checker
        self.checker_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec' : 60, 'fun' : self.check}
        )
        self.checker_thread.start()

    def stop(self):
        """Stop the MailBot
        """
        self.is_start = False
        self.smtp.close() #. asyncore.dispatcher.close()
        self.smtp_thread.join()
        self.reseter_thread.join()
        self.cleaner_thread.join()
        self.checker_thread.join()

    def count(self):
        """Count the mails in the queue.

        :returns: Numbers of mail in the queue.

        """
        return len(self.smtp.mail_queue)

    def stats(self):
        """@todo: Docstring for stats.
        :returns: @todo

        """
        #. TODO: prettier output, more stats.
        return self.smtp.counter

    def check(self):
        """@todo: Docstring for check.
        :returns: @todo

        """
        emails = self.count()
        if emails > ALERT_THRESHILD:
            self.notice(text="There are %s emails in the queue." % (emails),
                        subject="Too many emails in the queue!!"
                       )

    def flush(self):
        """Flush the mails in the queue.
        """
        i = 0
        mails = self.count()
        while i < mails:
            #. Reach the rate limit.
            if not self.smtp.flush_message():
                break
            i += 1

    def notice(self, text, subject):
        """@todo: Docstring for notice.
        :returns: @todo

        """
        msg = self._create_msg(text, BOT_ADDRESS, OP_ADDRESS, subject)
        self._send_msg(msg, BOT_ADDRESS, OP_ADDRESS)

    def _send_msg(self, msg, from_, to):
        """@todo: Docstring for _send_msg.

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
        """@todo: Docstring for _formataddr.

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
                print i
                if i == sec:
                    fun()
                    i = 0
            else:
                break

def main():
    print "MailBot - tiny mail robot."
    bot = MailBot(('127.0.0.1', 1025), ('127.0.0.1', 25))
    print "* Server listen at %s:%s." % \
    (bot.localaddr[0], bot.localaddr[1])
    print "* Quit the server with CONTROL+C."
    try:
        bot.start()
        bot.notice(text='<3', subject='MailBot start!')
        while True:
            #print bot.count()
            print bot.stats(), bot.count()
            #. Sleep to caught the KeyboardInterrupt exception.
            #. See: http://goo.gl/zcLYdT
            time.sleep(1) 
    except KeyboardInterrupt:
        print '\n! Stop the server ...'
        bot.notice(text='<3', subject='MailBot stop!')
        bot.stop()

if __name__ == '__main__':
    main()

