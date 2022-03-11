import logging
import lxml.etree
from loguru import logger


# Formatter to remove patterns from log output
class RedactingFormatter:
    def __init__(self, patterns=None, source_fmt=None):
        super().__init__()
        self.patterns = patterns
        self.fmt = source_fmt

    def format(self, record):
        scrubbed = record["message"]
        for pattern in self.patterns:
            scrubbed = scrubbed.replace(pattern, "")
        record["extra"]["scrubbed"] = scrubbed
        return self.fmt


# Handler to intercept logging messages for loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Process log file for Cronitor
def process_logfile(logfile, terms=None):
    with open(logfile) as logs:
        lines = logs.readlines()
        log_list = []
        for line in lines:
            if any(term in line for term in terms):
                log_list.append(line)
        return "".join(log_list)


def parse_form(box, sort):
    form_dict = {}
    txt = lxml.etree.HTML(box.content)
    js = str(txt.xpath(f"//script[contains(text(), 'window.OverDrive.{sort} =')]/text()")[0]).strip()
    split_1 = js.split(sep=" = ")
    for i in range(0, len(split_1)):
        if "window.OverDrive." + sort in split_1[i]:
            form_dict = split_1[i + 1].strip().split(';')[0]
            break
    return dict(json.loads(form_dict))

def craft_booklist(loans_page):
    book_dict = parse_form(loans_page, "mediaItems")
    book_list_parse = []
    for i in book_dict:
        book_format = book_dict[i]['overDriveFormat']['id']
        book_title = book_dict[i]['title']
        book_id = book_dict[i]['id']
        book_parse = {
            'id': book_id,
            'title': book_title,
            'format': book_format,
        }
        book_list_parse.append(book_parse)
    return book_list_parse