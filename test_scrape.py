import unittest
import json
import argparse
import hashlib
from unittest.mock import patch, MagicMock
from reportlab.platypus import Table
from scrape_schedule import scrape_schedule, create_pdf, create_grid_pdf, _shorten_time

class TestScrapeSchedule(unittest.TestCase):
    def test_scrape_returns_dict(self):
        rooms = scrape_schedule()
        self.assertIsInstance(rooms, dict)
    
    def test_has_at_least_one_room(self):
        rooms = scrape_schedule()
        if not rooms:
            self.skipTest("Live scrape returned no rooms (likely Cloudflare blocked without BYPASS_HDR)")
        self.assertGreater(len(rooms), 0)
    
    def test_each_room_has_required_keys(self):
        rooms = scrape_schedule()
        for room, data in rooms.items():
            self.assertIn('advisors', data)
            self.assertIn('graders', data)
            self.assertIn('schedule', data)
            self.assertIsInstance(data['schedule'], list)
    
    def test_each_room_has_at_least_one_schedule_item(self):
        rooms = scrape_schedule()
        for room, data in rooms.items():
            self.assertGreater(len(data['schedule']), 0)
    
    def test_schedule_items_are_tuples(self):
        rooms = scrape_schedule()
        for room, data in rooms.items():
            for item in data['schedule']:
                self.assertIsInstance(item, tuple)
                self.assertEqual(len(item), 2)
                self.assertIsInstance(item[0], str)  # time
                self.assertIsInstance(item[1], str)  # presenter

    def test_hash_generation(self):
        """Test that hash generation produces consistent results."""
        rooms = scrape_schedule()
        hash1 = hashlib.sha256(json.dumps(rooms, sort_keys=True).encode())
        hash2 = hashlib.sha256(json.dumps(rooms, sort_keys=True).encode())
        self.assertEqual(hash1.hexdigest(), hash2.hexdigest())

    def test_json_output_format(self):
        """Test that JSON output is properly formatted."""
        rooms = scrape_schedule()
        json_output = json.dumps(rooms, indent=2)
        parsed = json.loads(json_output)
        
        # Check that we have the same keys
        self.assertEqual(set(parsed.keys()), set(rooms.keys()))
        
        # Check structure for each room
        for room in rooms:
            self.assertIn('advisors', parsed[room])
            self.assertIn('graders', parsed[room])
            self.assertIn('schedule', parsed[room])
            self.assertIsInstance(parsed[room]['schedule'], list)
            
            # Check that schedule items are lists (tuples become lists in JSON)
            for item in parsed[room]['schedule']:
                self.assertIsInstance(item, list)
                self.assertEqual(len(item), 2)
                self.assertIsInstance(item[0], str)  # time
                self.assertIsInstance(item[1], str)  # presenter

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_pdf_basic(self, mock_doc_template):
        """Test PDF creation with basic options."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc
        
        rooms = scrape_schedule()
        create_pdf(rooms, "test.pdf")
        
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_pdf_with_qr_codes(self, mock_doc_template):
        """Test PDF creation with QR codes enabled."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc
        
        rooms = scrape_schedule()
        create_pdf(rooms, "test.pdf", qr_codes=True)
        
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_pdf_without_title(self, mock_doc_template):
        """Test PDF creation without title."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc
        
        rooms = scrape_schedule()
        create_pdf(rooms, "test.pdf", include_title=False)
        
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_grid_pdf_basic(self, mock_doc_template):
        """Test grid PDF creation with basic options."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc

        rooms = {
            '101': {
                'advisors': 'ORFE Advisors: Smith',
                'graders': 'PhD Candidate Graders: Jones',
                'schedule': [('9:00 am – 9:15 am', 'Alice')],
            },
            '103': {
                'advisors': 'ORFE Advisors: Doe',
                'graders': 'PhD Candidate Graders: Lee',
                'schedule': [('9:00 am – 9:15 am', 'Bob')],
            },
        }
        create_grid_pdf(rooms, "test_grid.pdf")

        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()
        # Verify landscape orientation was used (page width > height)
        call_kwargs = mock_doc_template.call_args
        pagesize = call_kwargs[1].get('pagesize') if call_kwargs[1] else None
        if pagesize:
            self.assertGreater(pagesize[0], pagesize[1])

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_grid_pdf_without_title(self, mock_doc_template):
        """Test grid PDF creation without title."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc

        rooms = {
            '101': {
                'advisors': 'ORFE Advisors: Smith',
                'graders': 'PhD Candidate Graders: Jones',
                'schedule': [('9:00 am – 9:15 am', 'Alice')],
            },
        }
        create_grid_pdf(rooms, "test_grid.pdf", include_title=False)

        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_grid_pdf_has_all_rooms(self, mock_doc_template):
        """Test grid PDF includes all rooms as columns."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc

        rooms = {
            '101': {
                'advisors': 'ORFE Advisors: Smith',
                'graders': 'PhD Candidate Graders: Jones',
                'schedule': [('9:00 am – 9:15 am', 'Alice')],
            },
            '103': {
                'advisors': 'ORFE Advisors: Doe',
                'graders': 'PhD Candidate Graders: Lee',
                'schedule': [('9:00 am – 9:15 am', 'Bob')],
            },
            '107': {
                'advisors': 'ORFE Advisors: Park',
                'graders': 'PhD Candidate Graders: Kim',
                'schedule': [('9:00 am – 9:15 am', 'Carol')],
            },
        }
        create_grid_pdf(rooms, "test_grid.pdf")

        # Inspect the story passed to build
        build_call = mock_doc.build.call_args
        story = build_call[0][0]
        # Find the Table in the story (skip title Paragraph and Spacer)
        grid_table = None
        for element in story:
            if isinstance(element, Table):
                grid_table = element
                break
        self.assertIsNotNone(grid_table)
        # The header row should have len(rooms) + 1 columns (time col + room cols)
        header_row = grid_table._cellvalues[0]
        self.assertEqual(len(header_row), len(rooms) + 1)

    def test_shorten_time_range(self):
        """Test that time range strings are shortened to start time only."""
        self.assertEqual(_shorten_time('9:00 am – 9:15 am'), '9:00 am')
        self.assertEqual(_shorten_time('10:15 am – 10:45 am'), '10:15 am')
        self.assertEqual(_shorten_time('1:00 pm – 1:15 pm'), '1:00 pm')

    def test_shorten_time_no_range(self):
        """Test that non-range time strings pass through unchanged."""
        self.assertEqual(_shorten_time('Lunch in Atrium'), 'Lunch in Atrium')
        self.assertEqual(_shorten_time('10:00 am'), '10:00 am')

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_grid_pdf_uses_short_times(self, mock_doc_template):
        """Test that grid PDF displays shortened start times, not full ranges."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc

        rooms = {
            '101': {
                'advisors': 'ORFE Advisors: Smith',
                'graders': 'PhD Candidate Graders: Jones',
                'schedule': [
                    ('9:00 am – 9:15 am', 'Alice'),
                    ('9:15 am – 9:30 am', 'Bob'),
                ],
            }
        }
        create_grid_pdf(rooms, "test_grid.pdf")

        build_call = mock_doc.build.call_args
        story = build_call[0][0]
        grid_table = None
        for element in story:
            if isinstance(element, Table):
                grid_table = element
                break
        self.assertIsNotNone(grid_table)
        # Row index 3 is the first data row (after header, advisors, graders)
        time_cell = grid_table._cellvalues[3][0]
        # The Paragraph text should be the shortened time
        self.assertIn('9:00 am', time_cell.text)
        self.assertNotIn('9:15 am', time_cell.text)

    def test_command_line_parsing(self):
        """Test command line argument parsing."""
        parser = argparse.ArgumentParser(description="Scrape symposium schedule and generate PDF or JSON.")
        parser.add_argument('--json', action='store_true', help="Output data as JSON instead of generating PDF.")
        parser.add_argument('--allow-breaks', action='store_true', help="Allow page breaks within room sections (default: keep rooms together).")
        parser.add_argument('--show-headers', action='store_true', help="Show table headers (Time, Presenter) in PDF.")
        parser.add_argument('--hash', action='store_true', help="Output hash of the schedule data instead of generating files.")
        parser.add_argument('--hash-file', type=str, help="Write hash to file as a side effect during generation.")
        parser.add_argument('--no-title', action='store_true', help="Exclude the title from PDF output.")
        parser.add_argument('--qr-codes', action='store_true', help="Include QR codes linking to each room's webpage anchor.")
        parser.add_argument('--grid', action='store_true', help="Generate a landscape grid PDF with all rooms side by side.")

        # Test default arguments
        args = parser.parse_args([])
        self.assertFalse(args.json)
        self.assertFalse(args.allow_breaks)
        self.assertFalse(args.show_headers)
        self.assertFalse(args.hash)
        self.assertIsNone(args.hash_file)
        self.assertFalse(args.no_title)
        self.assertFalse(args.qr_codes)
        self.assertFalse(args.grid)

        # Test all flags set
        args = parser.parse_args(['--json', '--allow-breaks', '--show-headers', '--hash', '--hash-file', 'out.txt', '--no-title', '--qr-codes', '--grid'])
        self.assertTrue(args.json)
        self.assertTrue(args.allow_breaks)
        self.assertTrue(args.show_headers)
        self.assertTrue(args.hash)
        self.assertEqual(args.hash_file, 'out.txt')
        self.assertTrue(args.no_title)
        self.assertTrue(args.qr_codes)
        self.assertTrue(args.grid)

    @patch('scrape_schedule.SimpleDocTemplate')
    def test_create_grid_pdf_alt_grader_label(self, mock_doc_template):
        """Test grid PDF uses alternate grader label when present."""
        mock_doc = MagicMock()
        mock_doc_template.return_value = mock_doc

        rooms = {
            '101': {
                'advisors': 'ORFE Advisors: Smith',
                'graders': 'PhD Candidates / Graduate Students: Jones',
                'schedule': [('9:00 am – 9:15 am', 'Alice')],
            },
        }
        create_grid_pdf(rooms, "test_grid.pdf")

        build_call = mock_doc.build.call_args
        story = build_call[0][0]
        grid_table = None
        for element in story:
            if isinstance(element, Table):
                grid_table = element
                break
        self.assertIsNotNone(grid_table)
        # Row 2 (index 2) is the grader row; column 0 is the label
        grader_label_cell = grid_table._cellvalues[2][0]
        self.assertIn('PhD Candidates / Graduate Students', grader_label_cell.text)
        # Column 1 should have names only, no prefix
        grader_names_cell = grid_table._cellvalues[2][1]
        self.assertIn('Jones', grader_names_cell.text)
        self.assertNotIn('PhD', grader_names_cell.text)

    @patch('scrape_schedule.sync_playwright')
    def test_scrape_normalizes_grader_labels(self, mock_playwright):
        """Test that inconsistent grader labels are normalized to the first seen."""
        mock_page = MagicMock()
        mock_page.content.return_value = """<html><body>
        101 - Sherrerd Hall
        ORFE Advisors: Smith
        PhD Candidate Graders: Jones
        9:00 am – 9:15 am
        Alice
        107 - Sherrerd Hall
        ORFE Advisors: Doe
        PhD Candidates / Graduate Students: Lee
        9:00 am – 9:15 am
        Bob
        </body></html>"""

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_context = MagicMock()
        mock_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_context

        rooms = scrape_schedule()
        # First label seen is "PhD Candidate Graders:", so both should use it
        self.assertTrue(rooms['101']['graders'].startswith('PhD Candidate Graders:'))
        self.assertTrue(rooms['107']['graders'].startswith('PhD Candidate Graders:'))
        self.assertIn('Jones', rooms['101']['graders'])
        self.assertIn('Lee', rooms['107']['graders'])

    @patch('scrape_schedule.sync_playwright')
    def test_scrape_accepts_alt_grader_label_first(self, mock_playwright):
        """Test that when the alternate label appears first, it becomes canonical."""
        mock_page = MagicMock()
        mock_page.content.return_value = """<html><body>
        101 - Sherrerd Hall
        ORFE Advisors: Smith
        PhD Candidates / Graduate Students: Jones
        9:00 am – 9:15 am
        Alice
        107 - Sherrerd Hall
        ORFE Advisors: Doe
        PhD Candidate Graders: Lee
        9:00 am – 9:15 am
        Bob
        </body></html>"""

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_context = MagicMock()
        mock_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_context

        rooms = scrape_schedule()
        # First label seen is "PhD Candidates / Graduate Students:", so both should use it
        self.assertTrue(rooms['101']['graders'].startswith('PhD Candidates / Graduate Students:'))
        self.assertTrue(rooms['107']['graders'].startswith('PhD Candidates / Graduate Students:'))

    @patch('scrape_schedule.sync_playwright')
    def test_maintenance_mode_detection(self, mock_playwright):
        """Test that maintenance mode is properly detected and raises exception."""
        # Mock the page content to contain maintenance mode text
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>The website is currently in Maintenance Mode. Please check back later.</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_context = MagicMock()
        mock_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_context

        # Test that maintenance mode raises exception
        with self.assertRaises(Exception) as context:
            scrape_schedule()

        self.assertIn("Maintenance Mode", str(context.exception))
        self.assertIn("unavailable", str(context.exception))

    @patch('scrape_schedule.sync_playwright')
    def test_bypass_header_set_when_env_var_present(self, mock_playwright):
        """Test that the bypass header is set when BYPASS_HDR env var is present."""
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>No schedule data</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_context = MagicMock()
        mock_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_context

        with patch.dict('os.environ', {'BYPASS_HDR': 'x-wdsoit-bot-bypass'}):
            scrape_schedule()
        mock_page.set_extra_http_headers.assert_called_once_with({'x-wdsoit-bot-bypass': 'true'})

    @patch('scrape_schedule.sync_playwright')
    def test_bypass_header_not_set_when_env_var_absent(self, mock_playwright):
        """Test that no bypass header is set when BYPASS_HDR env var is absent."""
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>No schedule data</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_context = MagicMock()
        mock_context.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__.return_value = mock_context

        with patch.dict('os.environ', {}, clear=True):
            scrape_schedule(url='https://example.com')
        mock_page.set_extra_http_headers.assert_not_called()

if __name__ == '__main__':
    unittest.main()