#!/usr/bin/env python
#
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#

import re
import sys

import mysql.connector

KILL_QUERY, KILL_CONNECTION, PRINT_PROCESS = range(3)

ID      = "Id"
USER    = "User"
HOST    = "Host"
DB      = "Db"
COMMAND = "Command"
TIME    = "Time"
STATE   = "State"
INFO    = "Info"

def _spec(info):
    """Create a server specification string from an info structure."""
    result = "{user}:*@{host}:{port}".format(**info)
    if "unix_socket" in info:
        result += ":" + info["unix_socket"]
    return result

def _obj2sql(obj):
    """Convert a Python object to an SQL object.

    This function convert Python objects to SQL values using the
    conversion functions in the database connector package."""
    from mysql.connector.conversion import MySQLConverter
    return MySQLConverter().quote(obj)

_SELECT_PROC_FRM = """
SELECT
  Id, User, Host, Db, Command, Time, State, Info
FROM
  INFORMATION_SCHEMA.PROCESSLIST{condition}"""

def _make_select(matches, use_regexp):
    """Generate a SELECT statement for matching the processes.
    """
    oper = 'REGEXP' if use_regexp else 'LIKE'
    conditions = []
    for field, pattern in matches:
        conditions.append("    {0} {1} {2}".format(field, oper, _obj2sql(pattern)))
    if len(conditions) > 0:
        condition = "\nWHERE\n" + "\n  AND\n".join(conditions)
    else:
        condition = ""
    return _SELECT_PROC_FRM.format(condition=condition)

_KILL_BODY = """
DECLARE kill_done INT;
DECLARE kill_cursor CURSOR FOR
  {select}
OPEN kill_cursor;
BEGIN
   DECLARE id BIGINT;
   DECLARE EXIT HANDLER FOR NOT FOUND SET kill_done = 1;
   kill_loop: LOOP
      FETCH kill_cursor INTO id;
      KILL {kill} id;
   END LOOP kill_loop;
END;
CLOSE kill_cursor;"""

_KILL_PROCEDURE = """
CREATE PROCEDURE {name} ()
BEGIN{body}
END"""

class ProcessGrep(object):
    def __init__(self, matches, actions=[], use_regexp=False):
        self.__select = _make_select(matches, use_regexp).strip()
        self.__actions = actions

    def sql(self, only_body=False):
        params = {
            'select': "\n      ".join(self.__select.split("\n")),
            'kill': 'CONNECTION' if KILL_CONNECTION in self.__actions else 'QUERY',
            }
        if KILL_CONNECTION in self.__actions or KILL_QUERY in self.__actions:
            sql = _KILL_BODY.format(**params)
            if not only_body:
                sql = _KILL_PROCEDURE.format(name="kill_processes",
                                             body="\n   ".join(sql.split("\n")))
            return sql
        else:
            return self.__select

    def execute(self, connections, **kwrds):
        from mysql.utilities.exception import EmptyResultError
        from ..common.options import parse_connection
        from ..common.format import format_tabular_list, format_vertical_list

        output = kwrds.get('output', sys.stdout)
        connector = kwrds.get('connector', mysql.connector)
        format = kwrds.get('format', "GRID")

        headers = ("Connection", "Id", "User", "Host", "Db",
                   "Command", "Time", "State", "Info")
        entries = []
        # Build SQL statement
        for info in connections:
            conn = parse_connection(info)
            if not conn:
                msg = "'%s' is not a valid connection specifier" % (info,)
                raise FormatError(msg)
            info = conn
            connection = connector.connect(**info)
            cursor = connection.cursor()
            cursor.execute(self.__select)
            for row in cursor:
                if KILL_QUERY in self.__actions:
                    cursor.execute("KILL {0}".format(row[0]))
                if KILL_CONNECTION in self.__actions:
                    cursor.execute("KILL {0}".format(row[0]))
                if PRINT_PROCESS in self.__actions:
                    entries.append(tuple([_spec(info)] + list(row)))
        
        # If output is None, nothing is printed
        if len(entries) > 0 and output:
            if format == "CSV":
                format_tabular_list(output, headers, entries,
                                    True, ',', True)
            elif format == "TAB":
                format_tabular_list(output, headers, entries,
                                    True, '\t', True)
            elif format == "VERTICAL":
                format_vertical_list(output, headers, entries)
            else: # Default is GRID
                format_tabular_list(output, headers, entries)
        elif PRINT_PROCESS in self.__actions:
            raise EmptyResultError("No matches found")

