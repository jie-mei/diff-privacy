import sys
import logging
try:
    import curses
except ImportError:
    curses = None


def _support_color():
    color = False
    if curses and hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
        try:
            curses.setupterm()
            if curses.tigetnum("colors") > 0:
                color = True
        except Exception:
            pass
        return color


class LogFormatter(logging.Formatter):
    DEFAULT_FORMAT = '%(color)s[%(module)s:%(lineno)4d]%(end_color)s %(message)s'
    DEFAULT_DATE_FORMAT = '%y%m%d %H:%M:%S'
    DEFAULT_COLORS = {
        logging.DEBUG:   8, # Gray
        logging.INFO:    2, # Green
        logging.WARNING: 3, # Yellow
        logging.ERROR:   1, # Red
    }

    def __init__(self,
                 color=True,
                 fmt=DEFAULT_FORMAT,
                 datefmt=DEFAULT_DATE_FORMAT,
                 colors=DEFAULT_COLORS):
        logging.Formatter.__init__(self, datefmt=datefmt)
        self._fmt = fmt

        # Set up color if we are in a tty and curses is installed.
        self._colors = {}
        unicode_type = unicode if isinstance(b'', type('')) else str
        if color and _support_color():
            fg_color = (curses.tigetstr("setaf") or
                        curses.tigetstr("setf") or
                        "")
            for levelno, code in colors.items():
                self._colors[levelno] = unicode_type(
                        curses.tparm(fg_color, code), "ascii")
                self._normal = unicode_type(curses.tigetstr("sgr0"), "ascii")
        else:
            self._normal = ''

    def format(self, record):
        # Add indentation after line break
        indent = len(record.module) + 8
        #indent = len(record.module) + len(str(record.lineno)) + 4
        record.message = ('\n' + ' ' * indent).join(record.getMessage().split('\n'))

        # Add color
        if record.levelno in self._colors:
            record.color = self._colors[record.levelno]
            record.end_color = self._normal
        else:
            record.color = record.end_color = ''

        return self._fmt % record.__dict__


def setup_logger(logger, level=logging.DEBUG):
    logger.setLevel(level)

    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(LogFormatter())
    hdlr.setLevel(level)
    logger.addHandler(hdlr)


log = logging.getLogger("default")
setup_logger(log)
