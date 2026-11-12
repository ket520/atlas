import unittest

from palletways_portal_details import extract_consignment_details


class PalletwaysPortalDetailsTests(unittest.TestCase):
    def test_consignment_addresses_and_dates_keep_source_values(self):
        source = '''<h3>Consignment Details</h3><table>
          <tr><th>Consignment Number:</th><td>0900615-41</td></tr>
          <tr><td>Service:</td><td>Premium &amp; Tail lift</td></tr>
          <tr><td>Due Date:</td><td>12/11/2026 09:00</td></tr></table>
          <h3>Delivery Address</h3><table>
          <tr><td>Address:</td><td>10 Test Street<br>Test Town</td></tr>
          <tr><td>Telephone:</td><td>0123456789</td></tr></table>'''
        sections = extract_consignment_details(source)
        self.assertEqual([section['title'] for section in sections], ['Consignment Details', 'Delivery Address'])
        self.assertEqual(sections[0]['fields'][1]['value'], 'Premium & Tail lift')
        self.assertEqual(sections[0]['fields'][2]['value'], '12/11/2026 09:00')
        self.assertEqual(sections[1]['fields'][0]['value'], '10 Test Street\nTest Town')

    def test_notes_invoices_and_internal_notes_do_not_become_consignment_facts(self):
        source = '''<h3>Details</h3><table>
          <tr><td>SysNote:</td><td>Internal text</td></tr>
          <tr><td>Sys Note:</td><td>Internal text</td></tr>
          <tr><td>Weight:</td><td>30 kg</td></tr></table>
          <h3>Consignment Notes</h3><table><tr><td>POC</td><td>Unverified</td></tr></table>
          <h3>Invoices</h3><table><tr><td>INV1</td><td>100</td></tr></table>'''
        sections = extract_consignment_details(source)
        self.assertEqual(sections, [{'title': 'Details', 'fields': [{'label': 'Weight', 'value': '30 kg'}]}])

    def test_duplicate_fields_and_script_contents_are_ignored(self):
        source = '''<h3>Details</h3><table>
          <tr><td>Reference:</td><td>REF1<script>private()</script></td></tr>
          <tr><td>Reference:</td><td>REF1</td></tr></table>'''
        self.assertEqual(extract_consignment_details(source)[0]['fields'], [{'label': 'Reference', 'value': 'REF1'}])

    def test_login_inputs_are_not_read_as_consignment_fields(self):
        self.assertEqual(extract_consignment_details('<form><input type="password" value="not-a-detail"></form>'), [])

    def test_portal_header_row_and_address_card(self):
        source = """<table><tr><th>Palletways Tracking ID</th><th>Units</th></tr>
        <tr><td>60000000000</td><td>1 @ 200kg</td></tr></table>
        <div><h4>To</h4>Test Recipient<br>Test Road</div>
        <span>Delivery service: Premium</span>"""
        sections = extract_consignment_details(source)
        self.assertEqual(sections[0]['fields'][1], {'label': 'Units', 'value': '1 @ 200kg'})
        self.assertEqual(sections[1]['fields'][0]['value'], 'Test Recipient\nTest Road')
        self.assertEqual(sections[2]['fields'][0]['value'], 'Premium')
