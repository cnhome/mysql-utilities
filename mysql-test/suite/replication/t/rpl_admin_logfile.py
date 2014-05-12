#
# Copyright (c) 2010, 2014, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

"""
rpl_admin_logfile test.
"""

import os
import stat

import mutlib
import rpl_admin

from mysql.utilities.exception import MUTLibError


_LOGNAME = "temp_log.txt"


class test(rpl_admin.test):
    """test replication administration commands
    This tests checks handling of accessibility of the log file (BUG#14208415)
    """

    def check_prerequisites(self):
        if self.servers.get_server(0).check_version_compat(5, 6, 5):
            raise MUTLibError("Test requires server version prior to 5.6.5")
        return self.check_num_servers(1)

    def setup(self):
        self.res_fname = "result.txt"
        return rpl_admin.test.setup(self)

    def run(self):
        master_conn = self.build_connection_string(self.server1).strip(' ')
        slave_conn = self.build_connection_string(self.server2).strip(' ')

        # For this test, it's OK when master and slave are the same
        master_str = "--master={0}".format(master_conn)
        slave_str = "--slave={0}".format(slave_conn)

        # command used in test cases: replace 3 element with location of
        # log file.
        cmd = [
            "mysqlrpladmin.py",
            master_str,
            slave_str,
            "--log={0}".format(_LOGNAME),
            "health",
        ]

        # Test Case 1
        test_num = 1
        comment = "Test Case {0} - Log file is newly created".format(test_num)
        res = mutlib.System_test.run_test_case(
            self, 0, ' '.join(cmd), comment)
        if not res:
            raise MUTLibError("{0}: failed".format(comment))

        # Test Case 2
        test_num += 1
        comment = "Test Case {0} - Log file is reopened".format(test_num)
        res = mutlib.System_test.run_test_case(
            self, 0, ' '.join(cmd), comment)
        if not res:
            raise MUTLibError("{0}: failed".format(comment))

        # Test Case 3
        test_num += 1
        comment = ("Test Case {0} - Log file can not be "
                   "written to".format(test_num))
        os.chmod(_LOGNAME, stat.S_IREAD)  # Make log read-only
        res = mutlib.System_test.run_test_case(
            self, 2, ' '.join(cmd), comment)
        if not res:
            raise MUTLibError("{0}: failed".format(comment))

        # Mask out non-deterministic data
        rpl_admin.test.do_masks(self)
        self.remove_result("NOTE: Log file 'temp_log.txt' does not exist. "
                           "Will be created.")

        return True

    def get_result(self):
        return self.compare(__name__, self.results)

    def record(self):
        return self.save_result_file(__name__, self.results)

    def cleanup(self):
        try:
            os.chmod(_LOGNAME, stat.S_IWRITE)
            os.unlink(_LOGNAME)
        except OSError:
            if self.debug:
                print "# failed removing temporary log file {0}".format(
                    _LOGNAME)
        return rpl_admin.test.cleanup(self)
