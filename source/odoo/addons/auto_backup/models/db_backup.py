# -*- coding: utf-8 -*-

import os
import datetime
import time
import socket

from odoo import models, fields, api, tools, _
from odoo.exceptions import Warning
import odoo

import logging
_logger = logging.getLogger(__name__)


try:
    from xmlrpc import client as xmlrpclib
except ImportError:
    import xmlrpclib


try:
    import paramiko
except ImportError:
    pass   # 对于不使用FTP备份的用户，没必要报错
    '''
    raise ImportError(
        'This module needs paramiko to automatically write backups to the FTP through SFTP. '
        'Please install paramiko on your system. (sudo pip3 install paramiko)')
    '''


def execute(connector, method, *args):
    res = False
    try:
        res = getattr(connector, method)(*args)
    except socket.error as error:
        _logger.critical('Error while executing the method "execute". Error: ' + str(error))
        raise error
    return res


class DbBackup(models.Model):
    _name = 'db.backup'
    _description = 'Backup configuration record'

    def get_db_list(self, host, port, context={}):
        uri = 'http://' + host + ':' + port
        conn = xmlrpclib.ServerProxy(uri + '/xmlrpc/db')
        db_list = execute(conn, 'list')
        return db_list

    def _get_db_name(self):
        dbName = self._cr.dbname
        return dbName

    # Columns for local server configuration
    host = fields.Char('Host', required=True, default='localhost')
    port = fields.Char('Port', required=True, default=8069)
    name = fields.Char('Database', required=True, help='Database you want to schedule backups for',
                       default=_get_db_name)
    folder = fields.Char('Backup Directory', help='Absolute path for storing the backups', required='True',
                         default='/odoo/backups')
    backup_type = fields.Selection([('zip', 'Zip'), ('dump', 'Dump')], 'Backup Type', required=True, default='zip')
    autoremove = fields.Boolean('Auto. Remove Backups',
                                help='If you check this option you can choose to automaticly remove the backup '
                                     'after xx days')
    days_to_keep = fields.Integer('Remove after x days',
                                  help="Choose after how many days the backup should be deleted. For example:\n"
                                       "If you fill in 5 the backups will be removed after 5 days.",
                                  required=True)

    # Columns for external server (SFTP)
    sftp_write = fields.Boolean('Write to external server with sftp',
                                help="If you check this option you can specify the details needed to write to a remote "
                                     "server with SFTP.")
    sftp_path = fields.Char('Path external server',
                            help='The location to the folder where the dumps should be written to. For example '
                                 '/odoo/backups/.\nFiles will then be written to /odoo/backups/ on your remote server.')
    sftp_host = fields.Char('IP Address SFTP Server',
                            help='The IP address from your remote server. For example 192.168.0.1')
    sftp_port = fields.Integer('SFTP Port', help='The port on the FTP server that accepts SSH/SFTP calls.', default=22)
    sftp_user = fields.Char('Username SFTP Server',
                            help='The username where the SFTP connection should be made with. This is the user on the '
                                 'external server.')
    sftp_password = fields.Char('Password User SFTP Server',
                                help='The password from the user where the SFTP connection should be made with. This '
                                     'is the password from the user on the external server.')
    days_to_keep_sftp = fields.Integer('Remove SFTP after x days',
                                       help='Choose after how many days the backup should be deleted from the FTP '
                                            'server. For example:\nIf you fill in 5 the backups will be removed after '
                                            '5 days from the FTP server.',
                                       default=30)
    send_mail_sftp_fail = fields.Boolean('Auto. E-mail on backup fail',
                                         help='If you check this option you can choose to automaticly get e-mailed '
                                              'when the backup to the external server failed.')
    email_to_notify = fields.Char('E-mail to notify',
                                  help='Fill in the e-mail where you want to be notified that the backup failed on '
                                       'the FTP.')

    def _check_db_exist(self):
        self.ensure_one()

        db_list = self.get_db_list(self.host, self.port)
        if not self.name in db_list:
            raise Warning(_('Error ! No such database exists!'))

    def test_sftp_connection(self, context=None):
        self.ensure_one()

        # Check if there is a success or fail and write messages
        message_title = ""
        message_content = ""
        error = ""
        has_failed = False

        for rec in self:
            db_list = self.get_db_list(rec.host, rec.port)
            path_to_write_to = rec.sftp_path
            ip_host = rec.sftp_host
            port_host = rec.sftp_port
            username_login = rec.sftp_user
            password_login = rec.sftp_password

            # Connect with external server over SFTP, so we know sure that everything works.
            try:
                s = paramiko.SSHClient()
                s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                s.connect(ip_host, port_host, username_login, password_login, timeout=10)
                sftp = s.open_sftp()
                message_title = _("Connection Test Succeeded!\nEverything seems properly set up for FTP back-ups!")
            except Exception as e:
                _logger.critical('There was a problem connecting to the remote ftp: ' + str(e))
                error += str(e)
                has_failed = True
                message_title = _("Connection Test Failed!")
                if len(rec.sftp_host) < 8:
                    message_content += "\nYour IP address seems to be too short.\n"
                message_content += _("Here is what we got instead:\n")
            finally:
                if s:
                    s.close()

        if has_failed:
            raise Warning(message_title + '\n\n' + message_content + "%s" % str(error))
        else:
            raise Warning(message_title + '\n\n' + message_content)

    @api.model
    def schedule_backup(self):
        conf_ids = self.search([])

        for rec in conf_ids:
            db_list = self.get_db_list(rec.host, rec.port)

            if rec.name in db_list:
                try:
                    if not os.path.isdir(rec.folder):
                        os.makedirs(rec.folder)
                except:
                    raise
                # Create name for dumpfile.
                bkp_file = '%s_%s.%s' % (time.strftime('%Y_%m_%d_%H_%M_%S'), rec.name, rec.backup_type)
                file_path = os.path.join(rec.folder, bkp_file)
                uri = 'http://' + rec.host + ':' + rec.port
                conn = xmlrpclib.ServerProxy(uri + '/xmlrpc/db')
                bkp = ''
                try:
                    # try to backup database and write it away
                    fp = open(file_path, 'wb')
                    odoo.service.db.dump_db(rec.name, fp, rec.backup_type)
                    fp.close()
                except Exception as error:
                    _logger.debug(
                        "Couldn't backup database %s. Bad database administrator password for server running at "
                        "http://%s:%s" % (rec.name, rec.host, rec.port))
                    _logger.debug("Exact error from the exception: " + str(error))
                    continue

            else:
                _logger.debug("database %s doesn't exist on http://%s:%s" % (rec.name, rec.host, rec.port))

            # Check if user wants to write to SFTP or not.
            if rec.sftp_write is True:
                try:
                    # Store all values in variables
                    dir = rec.folder
                    path_to_write_to = rec.sftp_path
                    ip_host = rec.sftp_host
                    port_host = rec.sftp_port
                    username_login = rec.sftp_user
                    password_login = rec.sftp_password
                    _logger.debug('sftp remote path: %s' % path_to_write_to)

                    try:
                        s = paramiko.SSHClient()
                        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        s.connect(ip_host, port_host, username_login, password_login, timeout=20)
                        sftp = s.open_sftp()
                    except Exception as error:
                        _logger.critical('Error connecting to remote server! Error: ' + str(error))

                    try:
                        sftp.chdir(path_to_write_to)
                    except IOError:
                        # Create directory and subdirs if they do not exist.
                        current_directory = ''
                        for dirElement in path_to_write_to.split('/'):
                            current_directory += dirElement + '/'
                            try:
                                sftp.chdir(current_directory)
                            except:
                                _logger.info('(Part of the) path didn\'t exist. Creating it now at ' + current_directory)
                                # Make directory and then navigate into it
                                sftp.mkdir(current_directory, 777)
                                sftp.chdir(current_directory)
                                pass
                    sftp.chdir(path_to_write_to)
                    # Loop over all files in the directory.
                    for f in os.listdir(dir):
                        if rec.name in f:
                            fullpath = os.path.join(dir, f)
                            if os.path.isfile(fullpath):
                                try:
                                    sftp.stat(os.path.join(path_to_write_to, f))
                                    _logger.debug(
                                        'File %s already exists on the remote FTP Server ------ skipped' % fullpath)
                                # This means the file does not exist (remote) yet!
                                except IOError:
                                    try:
                                        # sftp.put(fullpath, path_to_write_to)
                                        sftp.put(fullpath, os.path.join(path_to_write_to, f))
                                        _logger.info('Copying File % s------ success' % fullpath)
                                    except Exception as err:
                                        _logger.critical(
                                            'We couldn\'t write the file to the remote server. Error: ' + str(err))

                    # Navigate in to the correct folder.
                    sftp.chdir(path_to_write_to)

                    # Loop over all files in the directory from the back-ups.
                    # We will check the creation date of every back-up.
                    for file in sftp.listdir(path_to_write_to):
                        if rec.name in file:
                            # Get the full path
                            fullpath = os.path.join(path_to_write_to, file)
                            # Get the timestamp from the file on the external server
                            timestamp = sftp.stat(fullpath).st_atime
                            createtime = datetime.datetime.fromtimestamp(timestamp)
                            now = datetime.datetime.now()
                            delta = now - createtime
                            # If the file is older than the days_to_keep_sftp (the days to keep that the user filled in
                            # on the Odoo form it will be removed.
                            if delta.days >= rec.days_to_keep_sftp:
                                # Only delete files, no directories!
                                if sftp.isfile(fullpath) and (".dump" in file or '.zip' in file):
                                    _logger.info("Delete too old file from SFTP servers: " + file)
                                    sftp.unlink(file)
                    # Close the SFTP session.
                    sftp.close()
                except Exception as e:
                    _logger.debug('Exception! We couldn\'t back up to the FTP server..')
                    # At this point the SFTP backup failed. We will now check if the user wants
                    # an e-mail notification about this.
                    if rec.send_mail_sftp_fail:
                        try:
                            ir_mail_server = self.env['ir.mail_server']
                            message = "Dear,\n\nThe backup for the server " + rec.host + " (IP: " + rec.sftp_host + \
                                      ") failed.Please check the following details:\n\nIP address SFTP server: " + \
                                      rec.sftp_host + "\nUsername: " + rec.sftp_user + "\nPassword: " + \
                                      rec.sftp_password + "\n\nError details: " + tools.ustr(e) + \
                                      "\n\nWith kind regards"
                            msg = ir_mail_server.build_email("auto_backup@" + rec.name + ".com", [rec.email_to_notify],
                                                             "Backup from " + rec.host + "(" + rec.sftp_host +
                                                             ") failed",
                                                             message)
                            ir_mail_server.send_email(self._cr, self._uid, msg)
                        except Exception:
                            pass

            """
            Remove all old files (on local server) in case this is configured..
            """
            if rec.autoremove:
                directory = rec.folder
                # Loop over all files in the directory.
                for f in os.listdir(directory):
                    fullpath = os.path.join(directory, f)
                    # Only delete the ones wich are from the current database
                    # (Makes it possible to save different databases in the same folder)
                    if rec.name in fullpath:
                        timestamp = os.stat(fullpath).st_ctime
                        createtime = datetime.datetime.fromtimestamp(timestamp)
                        now = datetime.datetime.now()
                        delta = now - createtime
                        if delta.days >= rec.days_to_keep:
                            # Only delete files (which are .dump and .zip), no directories.
                            if os.path.isfile(fullpath) and (".dump" in f or '.zip' in f):
                                _logger.info("Delete local out-of-date file: " + fullpath)
                                os.remove(fullpath)
