import sys
import re
import datetime


# returns None on error
def parse_skype_datetime(s: str) -> datetime.datetime:
    ret = None
    # format IS: "2016-04-12T12:18:47.321Z"
    m = re.match(r'(\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)\.(\d+)Z', s)
    if m is None:
        sys.stderr.write('parse_skype_datetime(): Failed to parse string '
                         '[{0}], regex mismatch.\n'.format(s))
        return None
    try:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        second = int(m.group(6))
        ms = int(m.group(7))
    except ValueError:
        sys.stderr.write('parse_skype_datetime(): Failed to parse string '
                         '[{0}], failed to convert to int.\n'.format(s))
        return None

    # class datetime.datetime(year, month, day, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    # TODO: should we always pass timezone here? or it will be OK without timezone...
    ret = datetime.datetime(year, month, day, hour=hour, minute=minute, second=second,
                            microsecond=ms*1000, tzinfo=datetime.timezone.utc)
    return ret
