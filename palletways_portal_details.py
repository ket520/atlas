import html
import re
from html.parser import HTMLParser


def clean_text(value):
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in value.splitlines()]
    return '\n'.join(line for line in lines if line)


class ConsignmentDetailsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headers = []
        self.rows = []
        self.cells = []
        self.sections = []
        self.heading = 'Consignment details'
        self.heading_parts = None
        self.skip_depth = 0

    def handle_starttag(self, tag, attributes):
        if tag in {'script', 'style'}:
            self.skip_depth += 1
        if tag in {'h1', 'h2', 'h3', 'h4', 'caption'}:
            self.heading_parts = []
        if tag == 'table':
            self.headers = []
        if tag == 'tr':
            self.rows.append([])
        if tag in {'td', 'th'} and self.rows:
            self.cells.append({'parts': [], 'row': self.rows[-1], 'header': tag == 'th'})
        if tag == 'br' and self.cells:
            self.cells[-1]['parts'].append('\n')

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.heading_parts is not None:
            self.heading_parts.append(data)
        if self.cells:
            self.cells[-1]['parts'].append(data)

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag in {'h1', 'h2', 'h3', 'h4', 'caption'} and self.heading_parts is not None:
            self.heading = clean_text(''.join(self.heading_parts)) or self.heading
            self.heading_parts = None
        if tag in {'td', 'th'} and self.cells:
            cell = self.cells.pop()
            cell['row'].append(clean_text(''.join(cell['parts'])))
            if cell['header']:
                self.headers.append(cell['row'][-1])
        if tag == 'tr' and self.rows:
            self.add_row(self.rows.pop())

    def add_row(self, cells):
        if cells == self.headers:
            return
        if len(cells) == len(self.headers) and 'Palletways Tracking ID' in self.headers:
            self.sections.append({
                'title': 'Consignment details',
                'fields': [
                    {'label': label, 'value': value}
                    for label, value in zip(self.headers, cells) if value
                ],
            })
            return
        if len(cells) != 2 or re.search(r'notes?|invoices?', self.heading, re.I):
            return
        label, value = cells
        label = label.rstrip(':').strip()
        internal_note = re.sub(r'[^a-z]', '', label.casefold()) == 'sysnote'
        if not label or not value or len(label) > 100 or internal_note:
            return
        section = next((item for item in self.sections if item['title'] == self.heading), None)
        if section is None:
            section = {'title': self.heading, 'fields': []}
            self.sections.append(section)
        fact = {'label': label, 'value': value}
        if fact not in section['fields']:
            section['fields'].append(fact)


def plain_text(source):
    return clean_text(html.unescape(re.sub(r'<[^>]+>', '', source)))


def extract_addresses(source):
    sections = []
    cards = re.findall(r'<h4\b[^>]*>(.*?)</h4>(.*?)</div>', source, re.I | re.S)
    for title, content in cards:
        title = plain_text(title)
        if title.casefold() not in {'from', 'to', 'delivery address', 'collection address'}:
            continue
        value = plain_text(re.sub(r'<br\s*/?>', '\n', content, flags=re.I))
        if value:
            sections.append({
                'title': title,
                'fields': [{'label': 'Address and contact', 'value': value}],
            })
    return sections


def extract_service_fields(source):
    fields = []
    for label in ('Delivery service', 'Transmitted due date', 'Billing Units'):
        pattern = re.escape(label) + r':\s*(.*?)(?:</div>|<br\s*/?>|</span>)'
        match = re.search(pattern, source, re.I | re.S)
        if match:
            value = plain_text(match.group(1))
            if value:
                fields.append({'label': label, 'value': value})
    return fields


def extract_consignment_details(source):
    parser = ConsignmentDetailsParser()
    parser.feed(source)
    sections = parser.sections + extract_addresses(source)
    service_fields = extract_service_fields(source)
    if service_fields:
        sections.append({'title': 'Service', 'fields': service_fields})
    return sections
