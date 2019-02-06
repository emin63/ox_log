"""A few useful utitlies.
"""

import datetime
import re
import json


def parse_date(date_str):
    """Parse a simple date string into a date.

    :param date_str:    Date string like 2019-02-03

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :return:  A datetime.date for the date_str.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:  The following illustrates example usage:

>>> from ox_log.core import utils
>>> utils.parse_date('2019-02-03')
datetime.date(2019, 2, 3)
>>> utils.parse_date('20190203')
datetime.date(2019, 2, 3)

    """
    if not date_str:
        return None
    my_re = re.compile(
        r'(?P<year>[0-9]{4})-*(?P<month>[0-9]{1,2})-*(?P<day>[0-9]{1,2})')
    match = my_re.search(date_str)
    result = datetime.date(int(match.group('year')), int(match.group(
        'month')), int(match.group('day')))
    return result


def log_data_to_list(log_data, max_items=10, re_filter='.*',
                     start_date=None, end_date=None):
    """Helper function to take eyap comments and format them into a list.
    """
    my_re = re.compile(re_filter)
    if max_items in ['', 'None', 'none', False, 'false', 0, '0']:
        max_items = None
    else:
        max_items = int(max_items)
    result = []
    for item in log_data:
        my_date = None
        if max_items is not None and len(result) >= max_items:
            break
        if not my_re.search(item.summary):
            continue
        if start_date:
            my_date = parse_date(item.timestamp)
            if my_date < start_date:
                continue  # date too early so skip
        if end_date:
            my_date = my_date if my_date else parse_date(item.timestamp)
            if my_date > end_date:
                continue  # date too late so skip
        result.append({
            'timestamp': item.timestamp, 'summary': item.summary,
            '__details_summary__': '%s : %s' % (
                item.timestamp, item.summary),
            'body': json.loads(item.body)})
    return result
