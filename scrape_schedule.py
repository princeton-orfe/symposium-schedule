import requests
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from playwright.sync_api import sync_playwright
import argparse
import json
import hashlib
import qrcode
from io import BytesIO
import tempfile
import os
import sys

DEFAULT_URL = "https://symposium.orfe.princeton.edu"

def get_schedule_url():
    """Get the schedule URL from environment variable or use default."""
    return os.environ.get('SCHEDULE_SOURCE', DEFAULT_URL) or DEFAULT_URL

def scrape_schedule(url=None):
    if url is None:
        url = get_schedule_url()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
        bypass_hdr = os.environ.get('BYPASS_HDR')
        if bypass_hdr:
            page.set_extra_http_headers({bypass_hdr: 'true'})
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)
        content = page.content()
        browser.close()
    
    # Check for maintenance mode
    if "Maintenance Mode" in content:
        raise Exception("The symposium website is currently in Maintenance Mode and the schedule is unavailable. Please try again later.")
    
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    ADVISOR_LABELS = ['ORFE Advisors:', 'ORFE Advisers:']
    GRADER_LABELS = ['PhD Candidate Graders:', 'PhD Candidates / Graduate Students:']
    rooms = {}
    current_room = None
    advisor_label = None  # first label seen wins
    grader_label = None  # first label seen wins
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in ['001 - Sherrerd Hall', '003 - Sherrerd Hall', '008 - Sherrerd Hall', '101 - Sherrerd Hall', '107 - Sherrerd Hall', '110 - Sherrerd Hall', '122 - Sherrerd Hall', '123 - Sherrerd Hall', '125 - Sherrerd Hall']:
            room = line.split(' - ')[0]
            current_room = room
            rooms[current_room] = {'advisors': '', 'graders': '', 'schedule': []}
        elif current_room and any(al in line for al in ADVISOR_LABELS) and any(gl in line for gl in GRADER_LABELS):
            matched_al = next(al for al in ADVISOR_LABELS if al in line)
            matched_gl = next(gl for gl in GRADER_LABELS if gl in line)
            if advisor_label is None:
                advisor_label = matched_al
            if grader_label is None:
                grader_label = matched_gl
            parts = line.split(matched_gl)
            rooms[current_room]['advisors'] = parts[0].replace(matched_al, advisor_label)
            rooms[current_room]['graders'] = grader_label + parts[1]
        elif current_room and any(al in line for al in ADVISOR_LABELS):
            matched_al = next(al for al in ADVISOR_LABELS if al in line)
            if advisor_label is None:
                advisor_label = matched_al
            rooms[current_room]['advisors'] = line.replace(matched_al, advisor_label)
        elif current_room and any(gl in line for gl in GRADER_LABELS):
            matched_gl = next(gl for gl in GRADER_LABELS if gl in line)
            if grader_label is None:
                grader_label = matched_gl
            # Normalize to the first-seen label
            rooms[current_room]['graders'] = line.replace(matched_gl, grader_label)
        elif current_room and ('am – ' in line or 'pm – ' in line):
            time = line
            i += 1
            presenter = ''
            while i < len(lines):
                next_line = lines[i]
                if next_line and next_line != 'Link downloads document':
                    presenter = next_line.split(' Link')[0]
                    break
                i += 1
            rooms[current_room]['schedule'].append((time, presenter))
        i += 1
    return rooms

def create_pdf(rooms, filename, keep_together=True, show_headers=False, include_title=True, qr_codes=False, base_url=None):
    if base_url is None:
        base_url = get_schedule_url()

    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']

    # Custom style for table text and advisors/graders
    table_style = ParagraphStyle(
        'TableStyle',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Helvetica',
        leading=20,  # Increased line spacing
    )

    # Custom style for room titles
    room_style = ParagraphStyle(
        'RoomStyle',
        parent=styles['Heading2'],
        fontSize=18,
        fontName='Helvetica-Bold',
        spaceAfter=12,
    )
    
    story = []
    if include_title:
        story.append(Paragraph("Class of 2026 ORFE Thesis Symposium Schedule", title_style))
        story.append(Spacer(1, 12))
    
    temp_files = []  # Track temporary files for cleanup
    
    for room, data in sorted(rooms.items()):
        room_elements = []
        
        if qr_codes:
            qr_data = f"{base_url}#_{room}---Sherrerd-Hall"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            # Save to temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.png')
            temp_files.append(temp_path)  # Track for cleanup
            try:
                qr_img.save(temp_path, format='PNG')
                # Create a table with room title and QR code side by side
                room_title = Paragraph(f"Room {room} - Sherrerd Hall", room_style)
                qr_image = Image(temp_path, 50, 50)  # 25% larger QR code
                # Create table data with room title left-aligned and QR code right-aligned
                header_data = [[room_title, qr_image]]
                header_table = Table(header_data, colWidths=[400, 65])  # Room title gets more space, QR code needs more width
                header_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),   # Room title left-aligned
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),  # QR code right-aligned
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertically center both
                    ('LEFTPADDING', (0, 0), (0, 0), 0),   # Remove left padding from room title
                    ('RIGHTPADDING', (0, 0), (0, 0), 0),  # Remove right padding from room title
                    ('TOPPADDING', (0, 0), (-1, -1), 0),  # Remove vertical padding
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))
                room_elements.append(header_table)
            finally:
                os.close(temp_fd)  # Close the file descriptor
        else:
            room_elements.append(Paragraph(f"Room {room} - Sherrerd Hall", room_style))
        
        if data['advisors']:
            room_elements.append(Paragraph(data['advisors'], table_style))
        if data['graders']:
            room_elements.append(Paragraph(data['graders'], table_style))
        room_elements.append(Spacer(1, 6))
        
        # Table for schedule
        table_data = []
        if show_headers:
            table_data.append(['Time', 'Presenter'])
        for time, presenter in data['schedule']:
            table_data.append([time, presenter])
        
        table = Table(table_data, colWidths=[200, 200])  # Adjust to fit within margins
        # table.hAlign = 'LEFT'  # Remove to center the table
        
        styles_list = []
        if show_headers:
            # Header row styling
            styles_list.extend([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 16),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('LEADING', (0,0), (-1,0), 18),
                # Data rows
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.whitesmoke]),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 14),
                ('LEADING', (0,1), (-1,-1), 16),
                ('TOPPADDING', (0,1), (-1,-1), 6),
                ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ])
        else:
            # All rows are data
            styles_list.extend([
                ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.whitesmoke]),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 14),
                ('LEADING', (0,0), (-1,-1), 16),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ])
        
        styles_list.extend([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ])
        
        table.setStyle(TableStyle(styles_list))
        room_elements.append(table)
        room_elements.append(Spacer(1, 12))
        
        if keep_together:
            story.append(KeepTogether(room_elements))
        else:
            story.extend(room_elements)
    
    doc.build(story)
    
    # Clean up temporary files
    for temp_path in temp_files:
        try:
            os.unlink(temp_path)
        except OSError:
            pass  # Ignore if file already deleted

def _shorten_time(time_str):
    """Extract just the start time from a time range like '9:00 am – 9:15 am' -> '9:00 am'."""
    for sep in [' – ', ' - ', '–', '-']:
        if sep in time_str:
            return time_str.split(sep)[0].strip()
    return time_str.strip()

def create_grid_pdf(rooms, filename, include_title=True):
    """Generate a landscape grid PDF showing all rooms side by side, matching the xlsx layout."""
    if not rooms:
        return
    page_width, page_height = landscape(letter)
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    # Collect all unique time slots in order, and detect break rows
    all_times = []
    seen = set()
    break_keywords = ['break', 'photo', 'lunch']
    for room in sorted(rooms.keys()):
        for time_str, presenter in rooms[room]['schedule']:
            if time_str not in seen:
                seen.add(time_str)
                all_times.append(time_str)

    # Build lookup: room -> {time_str: presenter}
    sorted_rooms = sorted(rooms.keys())
    room_schedules = {}
    for room in sorted_rooms:
        room_schedules[room] = {}
        for time_str, presenter in rooms[room]['schedule']:
            room_schedules[room][time_str] = presenter

    usable_width = page_width - 72  # account for margins
    time_col_width = 80
    room_col_width = (usable_width - time_col_width) / len(sorted_rooms)

    col_widths = [time_col_width] + [room_col_width] * len(sorted_rooms)

    # Paragraph styles for cells
    cell_style = ParagraphStyle(
        'GridCell', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica', alignment=1,  # center
        leading=11,
    )
    cell_bold = ParagraphStyle(
        'GridCellBold', parent=cell_style,
        fontName='Helvetica-Bold',
    )
    header_style = ParagraphStyle(
        'GridHeader', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold', alignment=1,
        leading=12,
    )
    advisor_style = ParagraphStyle(
        'GridAdvisor', parent=styles['Normal'],
        fontSize=7, fontName='Helvetica', alignment=1,
        leading=9,
    )
    advisor_label_style = ParagraphStyle(
        'GridAdvisorLabel', parent=advisor_style,
        fontName='Helvetica-Bold',
    )
    title_style = ParagraphStyle(
        'GridTitle', parent=styles['Title'],
        fontSize=16, fontName='Helvetica-Bold', alignment=1,
        leading=20,
    )
    break_style = ParagraphStyle(
        'GridBreak', parent=cell_style,
        fontName='Helvetica-Bold',
    )

    story = []
    if include_title:
        story.append(Paragraph("Class of 2026 ORFE Thesis Symposium Schedule", title_style))
        story.append(Spacer(1, 8))

    # Build the grid table data
    table_data = []

    # Row 1: Room headers
    header_row = [Paragraph('', header_style)]
    for room in sorted_rooms:
        header_row.append(Paragraph(f'SH {room}', header_style))
    table_data.append(header_row)

    # Row 2: Advisors — detect the label from the first room that has one
    advisor_prefixes = ['ORFE Advisors:', 'ORFE Advisers:']
    advisor_row_label = 'ORFE Advisors'
    for room in sorted_rooms:
        at = rooms[room].get('advisors', '')
        for prefix in advisor_prefixes:
            if at.startswith(prefix):
                advisor_row_label = prefix.rstrip(':')
                break
        if advisor_row_label != 'ORFE Advisors':
            break
    advisor_row = [Paragraph(advisor_row_label, advisor_label_style)]
    for room in sorted_rooms:
        advisor_text = rooms[room].get('advisors', '')
        for prefix in advisor_prefixes:
            advisor_text = advisor_text.replace(prefix, '').strip()
        advisor_row.append(Paragraph(advisor_text, advisor_style))
    table_data.append(advisor_row)

    # Row 3: Graders — detect the label from the first room that has one
    grader_prefixes = ['PhD Candidate Graders:', 'PhD Candidates / Graduate Students:']
    grader_row_label = 'PhD Graders'
    for room in sorted_rooms:
        gt = rooms[room].get('graders', '')
        for prefix in grader_prefixes:
            if gt.startswith(prefix):
                grader_row_label = prefix.rstrip(':')
                break
        if grader_row_label != 'PhD Graders':
            break
    grader_row = [Paragraph(grader_row_label, advisor_label_style)]
    for room in sorted_rooms:
        grader_text = rooms[room].get('graders', '')
        for prefix in grader_prefixes:
            grader_text = grader_text.replace(prefix, '').strip()
        grader_row.append(Paragraph(grader_text, advisor_style))
    table_data.append(grader_row)

    # Data rows: time slots
    for time_str in all_times:
        row = [Paragraph(_shorten_time(time_str), cell_style)]
        is_break = False
        for room in sorted_rooms:
            presenter = room_schedules[room].get(time_str, '')
            if any(kw in presenter.lower() for kw in break_keywords):
                is_break = True
            row.append(Paragraph(presenter, break_style if any(kw in presenter.lower() for kw in break_keywords) else cell_style))
        table_data.append(row)

    grid_table = Table(table_data, colWidths=col_widths)

    # Determine which data rows are break rows (offset by 3 header rows)
    grid_styles = [
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        # Advisor row
        ('BACKGROUND', (1, 1), (-1, 1), colors.HexColor('#D9E2F3')),
        # Grader row
        ('BACKGROUND', (1, 2), (-1, 2), colors.HexColor('#E2EFDA')),
        # Label column background for advisor/grader rows
        ('BACKGROUND', (0, 1), (0, 2), colors.HexColor('#F2F2F2')),

        # Global styles
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]

    # Alternating row backgrounds for data rows, highlight breaks
    header_rows = 3  # room header + advisors + graders
    for idx, time_str in enumerate(all_times):
        row_idx = header_rows + idx
        # Check if this is a break row
        row_is_break = False
        for room in sorted_rooms:
            presenter = room_schedules[room].get(time_str, '')
            if any(kw in presenter.lower() for kw in break_keywords):
                row_is_break = True
                break
        if row_is_break:
            grid_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#FFF2CC')))
        elif idx % 2 == 1:
            grid_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#F8F8F8')))

    grid_table.setStyle(TableStyle(grid_styles))
    story.append(grid_table)

    doc.build(story)


def create_grader_sheets(rooms, filename):
    """Generate a PDF with one grader sheet per presenter per room."""
    if not rooms:
        return
    from reportlab.lib.units import inch

    doc = SimpleDocTemplate(
        filename, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    usable_width = letter[0] - 1.5 * inch

    title_style = ParagraphStyle(
        'SheetTitle', parent=styles['Title'],
        fontSize=20, fontName='Helvetica-Bold', spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'SheetSubtitle', parent=styles['Title'],
        fontSize=14, fontName='Helvetica', spaceAfter=20,
    )
    presenter_style = ParagraphStyle(
        'PresenterName', parent=styles['Normal'],
        fontSize=18, fontName='Helvetica-Bold', spaceAfter=12,
    )
    info_style = ParagraphStyle(
        'InfoStyle', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica', spaceAfter=20,
    )
    label_style = ParagraphStyle(
        'LabelStyle', parent=styles['Normal'],
        fontSize=14, fontName='Helvetica-Bold', spaceAfter=8,
    )
    grade_cell_style = ParagraphStyle(
        'GradeCell', parent=styles['Normal'],
        fontSize=28, fontName='Helvetica-Bold', alignment=1,
        leading=28,
    )

    break_keywords = ['break', 'photo', 'lunch']
    story = []
    first_page = True

    for room in sorted(rooms.keys()):
        for time_str, presenter in rooms[room]['schedule']:
            if any(kw in presenter.lower() for kw in break_keywords):
                continue

            if not first_page:
                story.append(PageBreak())
            first_page = False

            # Header
            story.append(Paragraph("ORFE Thesis Symposium", title_style))
            story.append(Paragraph("Presentation Grader Sheet", subtitle_style))

            # Rule
            story.append(Table([['']], colWidths=[usable_width], rowHeights=[1],
                               style=[('LINEABOVE', (0, 0), (-1, 0), 1, colors.black)]))
            story.append(Spacer(1, 16))

            # Presenter info
            story.append(Paragraph(f"Presenter: {presenter}", presenter_style))
            story.append(Paragraph(f"Room {room} - Sherrerd Hall&nbsp;&nbsp;|&nbsp;&nbsp;{time_str}", info_style))

            # Evaluator line
            line = "_" * 60
            story.append(Paragraph(f"Your Name: {line}", label_style))
            story.append(Spacer(1, 20))

            # Grade section
            story.append(Paragraph("Presentation Quality (circle one):", label_style))
            story.append(Spacer(1, 8))

            grade_data = [[
                Paragraph('A\u2013', grade_cell_style),
                Paragraph('A', grade_cell_style),
                Paragraph('A+', grade_cell_style),
            ]]
            grade_table = Table(grade_data, colWidths=[150, 150, 150], rowHeights=[60])
            grade_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (0, 0), 2, colors.black),
                ('BOX', (1, 0), (1, 0), 2, colors.black),
                ('BOX', (2, 0), (2, 0), 2, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 16),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(grade_table)
            story.append(Spacer(1, 24))

            # Rule
            story.append(Table([['']], colWidths=[usable_width], rowHeights=[1],
                               style=[('LINEABOVE', (0, 0), (-1, 0), 1, colors.black)]))
            story.append(Spacer(1, 12))

            # Comments section
            story.append(Paragraph("Comments:", label_style))
            story.append(Spacer(1, 8))
            for _ in range(12):
                story.append(Table([['']], colWidths=[usable_width], rowHeights=[24],
                                   style=[('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey)]))

    if story:
        doc.build(story)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape symposium schedule and generate PDF or JSON.")
    parser.add_argument('--json', action='store_true', help="Output data as JSON instead of generating PDF.")
    parser.add_argument('--allow-breaks', action='store_true', help="Allow page breaks within room sections (default: keep rooms together).")
    parser.add_argument('--show-headers', action='store_true', help="Show table headers (Time, Presenter) in PDF.")
    parser.add_argument('--hash', action='store_true', help="Output hash of the schedule data instead of generating files.")
    parser.add_argument('--hash-file', type=str, help="Write hash to file as a side effect during generation.")
    parser.add_argument('--no-title', action='store_true', help="Exclude the title from PDF output.")
    parser.add_argument('--qr-codes', action='store_true', help="Include QR codes linking to each room's webpage anchor.")
    parser.add_argument('--grid', action='store_true', help="Generate a landscape grid PDF with all rooms side by side.")
    parser.add_argument('--grader-sheets', action='store_true', help="Generate backup grader sheets (one page per presenter).")
    args = parser.parse_args()

    try:
        rooms = scrape_schedule()
    except Exception as e:
        if "Maintenance Mode" in str(e):
            print(f"Error: {e}")
            sys.exit(1)
        else:
            raise

    if not rooms:
        print("Error: No rooms were found in the schedule. The page may be blocked or empty.")
        sys.exit(1)

    # Compute hash once, reuse for --hash, --hash-file, or both
    schedule_hash = hashlib.sha256(json.dumps(rooms, sort_keys=True).encode()).hexdigest()

    if args.hash_file:
        with open(args.hash_file, 'w') as f:
            f.write(schedule_hash)

    if args.hash:
        print(schedule_hash)
    elif args.json:
        json_output = json.dumps(rooms, indent=2)
        with open("symposium_schedule.json", "w") as f:
            f.write(json_output)
        print(json_output)
        # Also generate PDF when --json is specified
        create_pdf(rooms, "symposium_schedule.pdf", keep_together=not args.allow_breaks, show_headers=args.show_headers, include_title=not args.no_title, qr_codes=args.qr_codes)
        if args.grid:
            create_grid_pdf(rooms, "symposium_schedule_grid.pdf", include_title=not args.no_title)
        if args.grader_sheets:
            create_grader_sheets(rooms, "grader_sheets.pdf")
    else:
        create_pdf(rooms, "symposium_schedule.pdf", keep_together=not args.allow_breaks, show_headers=args.show_headers, include_title=not args.no_title, qr_codes=args.qr_codes)
        if args.grid:
            create_grid_pdf(rooms, "symposium_schedule_grid.pdf", include_title=not args.no_title)
        if args.grader_sheets:
            create_grader_sheets(rooms, "grader_sheets.pdf")