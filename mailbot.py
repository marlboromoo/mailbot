#!/usr/bin/env python
# encoding: utf-8

"""
                        ___    ____            __      
 /'\_/`\            __ /\_ \  /\  _`\         /\ \__   
/\      \     __   /\_\\//\ \ \ \ \L\ \    ___\ \ ,_\  
\ \ \__\ \  /'__`\ \/\ \ \ \ \ \ \  _ <'  / __`\ \ \/  
 \ \ \_/\ \/\ \L\.\_\ \ \ \_\ \_\ \ \L\ \/\ \L\ \ \ \_ 
  \ \_\\ \_\ \__/.\_\\ \_\/\____\\ \____/\ \____/\ \__\
   \/_/ \/_/\/__/\/_/ \/_/\/____/ \/___/  \/___/  \/__/  - Tiny mail robot.

Author Timothy Lee <marlboromoo@gmail.com> 

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

LOGFILE = '/tmp/mailbot.log'
PIDFILE = '/tmp/mailbot.pid'
MAX_MAIL_PER_MINUTE = 10
MAX_MAIL_PER_HOUR = MAX_MAIL_PER_MINUTE * 60
ALERT_THRESHILD = 500 
BIND_ADDRESS = ('127.0.0.1', 1025)
SMTP_ADDRESS = ('127.0.0.1', 25)
BOT_ADDRESS = 'mailbot@localhost'
OP_ADDRESS = ['marlboromoo@gmail.com', 'timothy.lee@localhost']
PURGE_OVER_THRESHOLD = True
DEBUG = True

###############################################################################
#  MailBot <3
###############################################################################

BOTNAME = 'MailBot'
NEWLINE = '\n'
COMMASPACE = ', '
mailbot_instance = None

class BotsSMTPServer(PureProxy):

    """ Custom SMTP server to transfer message.
    SMTPServer is an old style class, see the follow link for more information:

    * http://pymotw.com/2/smtpd/index.html
    * http://hg.python.org/cpython/file/2.7/Lib/smtpd.py

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
            logging.warning('!! Fail to relay the message: : %s' % (refused))

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
        return True if self.counter < MAX_MAIL_PER_HOUR else False


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
        self.is_alive = None

    def start(self):
        """Start the MailBot.
        """
        logging.info("%s - tiny mail robot." % (BOTNAME))
        self.smtp = BotsSMTPServer(self.localaddr, self.remoteaddr)
        self.smtp.last_reset = int(time.time())
        self.is_alive = True
        #. smtp server
        self.smtp_thread = threading.Thread(
            target=asyncore.loop,
            kwargs= {'timeout' : 1})
        self.smtp_thread.setDaemon(True)
        self.smtp_thread.start()
        #. reseter
        self.reseter_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec': 3599, 'fun' : self.smtp.reset_counter}
        )
        self.reseter_thread.setDaemon(True)
        self.reseter_thread.start()
        #. checker
        self.checker_thread = threading.Thread(
            target=self._timer,
            kwargs={'sec' : 3600, 'fun' : self.flush_and_check}
        )
        self.checker_thread.setDaemon(True)
        self.checker_thread.start()

        logging.info("* Server listen at %s:%s." % (
            self.localaddr[0], self.localaddr[1]))
        #logging.info("* Quit the server with CONTROL+C.")
        self.notice(text='<3', subject='%s start!' % (BOTNAME))

    def stop(self):
        """Stop the MailBot.
        """
        if self.is_alive:
            logging.info('!! Stop the server ...')
            self.is_alive = False
            self.smtp.close() #. asyncore.dispatcher.close()
            logging.info("!! Waiting the threads ... ")
            self.smtp_thread.join()
            self.reseter_thread.join()
            self.checker_thread.join()
            logging.info("!! All threads stop. ")
            self.notice(text='<3', subject='%s stop!' % (BOTNAME))
            logging.info('!! Server stop.')

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
        if not DEBUG:
            self.stats()
        if emails > ALERT_THRESHILD:
            self.notice(text="There are %s emails in the queue." % (emails),
                        subject="Too many emails in the queue!!"
                       )
            #. purge the mail queue
            if PURGE_OVER_THRESHOLD:
                self.smtp.purge_queue()

    def flush(self):
        """Flush the mails in the queue.
        """
        logging.info("** Flush the mail queue.")
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
        except Exception, e:
            logging.warning("!! Fail to send the message: %s" % (str(e)))
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
            if self.is_alive:
                time.sleep(1)
                i += 1
                #print i
                if i == sec:
                    fun()
                    i = 0
            else:
                break

def sigterm_handler(signum, frame):
    """Handle the SIGTERM signal, yapdi will try to kill the process until the 
    process dies, so we have to purge the instance, see:

    * http://docs.python.org/2/library/signal.html
    * https://github.com/kasun/YapDi/blob/master/yapdi.py

    """
    global mailbot_instance
    if mailbot_instance:
        mailbot_instance.stop()
        #. purge the instance to prevent the signal spams.
        mailbot_instance = None

def main():
    #. logger
    logging.basicConfig(
        filename=LOGFILE,
        format='%(asctime)s - %(levelname)s - %(message)s',
        #datefmt='%Y-%M-%d %H:%M:%S',
        level=logging.DEBUG,
    )
    #. parse arg
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    args = parser.parse_args()
    daemon = yapdi.Daemon(pidfile=PIDFILE, stderr=LOGFILE)
    if args.action == 'start':
        print "Start %s ..." % (BOTNAME)
        #. daemonize
        if daemon.status():
            print "%s is already running!" % (BOTNAME)
            exit()
        retcode = daemon.daemonize()
        if retcode == yapdi.OPERATION_SUCCESSFUL:
            try:
                signal.signal(signal.SIGTERM, sigterm_handler)
                #. mailbot
                global mailbot_instance
                mailbot_instance = MailBot(BIND_ADDRESS, (SMTP_ADDRESS))
                mailbot_instance.start()
                while mailbot_instance:
                    if DEBUG:
                        mailbot_instance.stats()
                    time.sleep(1) 
            #. If something error, we can use CTRL+C to force the bot stop.
            except KeyboardInterrupt:
                mailbot_instance.stop()
            except Exception, e:
                mailbot_instance.notice(
                    text="Exception: %s" % (str(e)),
                    subject="%s error!" % (BOTNAME)
                )
        else:
            print('Daemonization failed!')
    if args.action == 'stop':
        print 'Stop %s ...' % (BOTNAME)
        if not daemon.status():
            print "%s is not running!" % (BOTNAME)
            exit()
        retcode = daemon.kill()
        if retcode == yapdi.OPERATION_FAILED:
            print "Trying to stop %s failed!" % (BOTNAME)
        else:
            print "Done."


if __name__ == '__main__':
    main()

