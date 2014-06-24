#!/usr/bin/env python
# encoding: utf-8
# @author Robin Schneider <ypid23@aol.de>
# @licence GPLv3 <http://www.gnu.org/licenses/gpl.html>
#
# Implementation of the work flow explained here: http://superuser.com/a/717689
# In short: Uses the database from cdcat to copy wanted files.

# modules {{{
import gzip, os, sys, logging
import xml.etree.ElementTree as ET
import argparse
# }}}

# module wide variables {{{
SCRIPT_URL = 'https://github.com/ypid/scripts/blob/master/cdcat-parser/cdcat-parser.py'
# }}}

class CdcatDatabase: # {{{
    """
    Class which implements functions to parse a cdcat database and generate
    copy scripts based on it.
    """

    def __init__(self, directory_separator=os.path.sep, shell='sh'):
        self._executing_shell_to_file_suffix = {
            'sh': 'sh',
            'cmd': 'bat',
            }
        self._executing_shell = shell
        self._directory_separator = directory_separator
        self.__name_of_base_path_variable = 'media_id_'
        self.__name_of_target_path_variable = 'target_path'
        self.__base_filename = None
        self._generate_formats = None
        # robocopy parameters {{{
        self._robocopy_parameter_string = '-s -r:2 -w:3' \
            + ' -log+:"target\\log-%date:~6,4%-%date:~0,2%-%date:~3,2%' \
            + ' _%time:~0,2%-%time:~3,2%-%time:~6,2%.log" -tee'
        # http://technet.microsoft.com/de-de/library/cc733145%28v=ws.10%29.aspx
        # /s:   Copies subdirectories. Note that this option excludes empty
        #       directories. (Empty directories are not consider as useful).
        # /r:<N>:   Specifies the number of retries on failed copies.
        #           The default value of N is 1,000,000 (one million retries).
        # /w:<N>:   Specifies the wait time between retries, in seconds.
        #           The default value of N is 30 (wait time 30 seconds).
        # /log+:<LogFile>:  Writes the status output to the log file
        #                   (appends the output to the existing log file).
        # /tee: Writes the status output to the console window,
        #       as well as to the log file.
        # }}}

    def parse_gzip_file(self, gzip_file, generate_formats=['git-annex']):
        """
        Parse cdcat database and generate the copy script using the specified
        programs (in generate_formats).

        :param gzip_file: path to the gzipped XML file from cdcat.
        :param generate_formats: list with the program which should be used in
            the copy script (default is git-annex).
        """
        self.__base_filename = gzip_file
        if gzip_file[-4:] == '.hcf':
            self.__base_filename = gzip_file[:-4]
        self._generate_formats = generate_formats
        gzip_file_fh = gzip.open(gzip_file, 'rb')
        xml_object = ET.ElementTree(ET.fromstring(gzip_file_fh.read()))
        gzip_file_fh.close()
        self._for_xml_object(xml_object)

    def parse_uncompressed_xml_file(self, xml_file, generate_formats=['git-annex']):
        """
        Parse cdcat database and generate the copy script using the specified
        programs (in generate_formats).

        :param gzip_file: path to the unzipped XML file from cdcat.
        :param generate_formats: list with the program which should be used in
            the copy script (default is git-annex).
        """
        self._generate_formats = generate_formats
        xml_object = ET.parse(xml_file)
        self._for_xml_object(xml_object)

    def _for_xml_object(self, xml_object):
        self._start_line_comment_token = u'#' # default is sh style comment
        if 'sh' == self._executing_shell:
            self._start_line_comment_token = u'#'
            logging.info(u'Generating copy script for sh (common Linux and Unix shell for scripting)')
        if 'cmd' == self._executing_shell:
            self._start_line_comment_token = u'rem'
            logging.info(u'Generating copy script for Windows cmd')

        catalog = xml_object.getroot()
        self._for_catalog(catalog)

    def _for_catalog(self, catalog):
        logging.info(
            u'Parsing catalog called "%s" owned by "%s" …',
            catalog.attrib['name'],
            catalog.attrib['owner']
            )
        count = 1
        for media in catalog.findall('media'):
            self.__media_id = count
            self._for_media(media)
            count += 1

    def _for_media(self, media):
        logging.info(u'Parsing media: %s', media.attrib['name'])
        self.__cur_copy_script_fh = open(
            '%s.%d.%s' % (
                self.__base_filename,
                self.__media_id,
                self._get_script_file_extention()
            ), 'w')
        if 'sh' == self._executing_shell:
            print '#!/bin/sh'
        print '%s This OS dependent copy script was generated by %s' % (
            self._start_line_comment_token,
            SCRIPT_URL
            )
        print '%s You will need to change the base path to the media "%s" and the target path.\n' % (
            self._start_line_comment_token,
            media.attrib['name']
            )
        if 'sh' == self._executing_shell:
            print '%s%d="%s"' % (
                self.__name_of_base_path_variable,
                self.__media_id, media.attrib['name']
                )
        if 'cmd' == self._executing_shell:
            print 'set %s%d=%s' % (
                self.__name_of_base_path_variable,
                self.__media_id, media.attrib['name']
                )
        print '%s Path to the base directory of the media (same as the one selected in cdcat for this media).\n' % (
                self._start_line_comment_token,
                )
        if 'cmd' == self._executing_shell:
            print 'set %s=d:\\external_disk\\' % \
                self.__name_of_target_path_variable
        print '%s The copy script will create one directory for each media under "%s".' % (
                self._start_line_comment_token,
                self._get_expandable_variable(self.__name_of_target_path_variable)
                )
        print '\n%s Do not change the following commands.' % \
            self._start_line_comment_token \
            + ' They can be regenerated be the script after altering the database with cdcat' \
            + ' (in case you want to select other files as listed here).'
        self._for_dir(media, '', '', None)
        if 'cmd' == self._executing_shell:
            print 'pause'

    # helper functions {{{
    def _get_script_file_extention(self):
        return self._executing_shell_to_file_suffix[self._executing_shell]

    def _get_expandable_variable(self, name):
        """
        Returns the script language dependent variable which will expand to the
        base path of the source where the data is located.
        """
        if 'sh' == self._executing_shell:
            return '${%s%d}' % (name, self.__media_id)
        if 'cmd' == self._executing_shell:
            return '%%%s%d%%' % (name, self.__media_id)

    def _copy_node(self, node):
        category = node.find('category')
        if category is not None:
            is_number = True
            try:
                i = int(category.text)
            except ValueError:
                is_number = False
            return is_number
        else:
            return None

    def _get_path(self, cur_path, node):
        if 'media' in node.tag:
            return ''
            # Media name is not file path.
        else:
            if cur_path is '':
                return node.attrib['name']
            else:
                return self._directory_separator.join([
                    cur_path, node.attrib['name']
                ])
    # }}}

    # generate copy script entry for node {{{
    def _add_to_copy_list(self, base_path, cur_path, file_path, unwanted, node_type):
        unwanted = [item for item in unwanted if item is not None]
        node_path = cur_path if node_type is 'dir' else file_path
        source_node_path = self._directory_separator.join([base_path, node_path])
        logging.debug(u'Include %s %s', node_type, node_type)
        if 'git-annex' in self._generate_formats:
            unwanted = ['--exclude=\'%s\'' % item for item in unwanted]
            # print 'mkdir -p \'%s\' && pushd \'%s\'' % (cur_path, cur_path)
            # print 'git annex get \'%s\' %s' % (source_node_path, ' '.join(unwanted))
            print 'git annex get \'%s\' %s' % (node_path, ' '.join(unwanted))
            # print 'git annex copy \'%s\' %s' % (node_path, ' '.join(unwanted))
            # print 'popd'
        if 'robocopy' in self._generate_formats:
            unwanted = ['\'%s\'' % item for item in unwanted]
            if len(unwanted) != 0:
                logging.warning(
                    'robocopy does not support to exclude files or directories.'
                    + ' Directories(s) or file(s) "%s" will be copied although they where excluded.' % (
                        ' '.join(unwanted)
                        )
                    )

            print 'robocopy "%s%s%s" "%s\\%s" %s' % (
                self._get_expandable_variable(self.__name_of_base_path_variable),
                self._directory_separator, node_path,
                self._get_expandable_variable(self.__name_of_target_path_variable),
                cur_path,
                self._robocopy_parameter_string
                )
    # }}}

    # for file {{{
    def _for_file(self, file_node, base_path, cur_path, implicit_wanted_node):
        file_path = self._get_path(cur_path, file_node)

        explicit_wanted_node = self._copy_node(file_node)
        wanted_node = explicit_wanted_node if explicit_wanted_node is not None else implicit_wanted_node

        if wanted_node is False:
            # if explicit_wanted_node is False and implicit_wanted_node is True:
            #     return file_path
            logging.debug(u'Not file %s', file_path)
            return file_path
        elif wanted_node is True:
            if explicit_wanted_node is True and implicit_wanted_node is not True:
                self._add_to_copy_list(
                    base_path,
                    cur_path,
                    file_path, [], 'file')
            else:
                # File is already included from a upper directory.
                return None
    # }}}

    # for dir {{{
    def _for_dir(self, dir_node, base_path, cur_path, implicit_wanted_node):
        cur_path = self._get_path(cur_path, dir_node)
        explicit_wanted_node = self._copy_node(dir_node)
        if implicit_wanted_node is False and explicit_wanted_node is not True:
            logging.debug(u'Not dir %s (excluded from upper dir)' % cur_path)
            return cur_path

        wanted_node = explicit_wanted_node if explicit_wanted_node is not None else implicit_wanted_node
        unwanted = []
        for directory_node in dir_node.findall('directory'):
            unwanted.append(self._for_dir(directory_node, base_path, cur_path, wanted_node))
        for file_node in dir_node.findall('file'):
            unwanted.append(self._for_file(file_node, base_path, cur_path, wanted_node))
        if wanted_node is True:
            self._add_to_copy_list(base_path, cur_path, None, unwanted, 'dir')
        if explicit_wanted_node is False:
            return cur_path
    # }}}
# }}}

def main(catalog_file): # {{{
    # cdcat_db_object = CdcatDatabase(directory_separator = '\\', shell = 'sh')
    cdcat_db_object = CdcatDatabase(directory_separator = '\\', shell = 'cmd')
    # cdcat_db_object._robocopy_parameter_string = 'test'
    cdcat_db_object.parse_gzip_file(catalog_file, generate_formats=['robocopy'])
    # cdcat_db_object.parse_gzip_file(catalog_file, generate_formats=[ 'git-annex' ])

if __name__ == '__main__':
    logging.basicConfig(
        format='# %(levelname)s: %(message)s',
        # level=logging.DEBUG,
        level=logging.INFO,
        )
    logging.info(u'Running cdcat-parser: %s' % SCRIPT_URL)
    if len(sys.argv) > 1:
        catalog_file = sys.argv[1]
    else:
        raise SystemExit(
            'Not enough parameters.'
            + ' 1. File path to catalog file.'
            + ' The copy scripts will be named after the catalog filename with different suffixes.'
            )
    main(catalog_file)
# }}}
