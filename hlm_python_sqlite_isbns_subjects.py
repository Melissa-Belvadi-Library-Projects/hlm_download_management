import sys
import os
import sqlite3
import re

def clean_line(line):
    # Remove all single quotes, double quotes, and apostrophes
    #line = line.replace('"', '').replace("'", '').replace("`", '')
    return line

def clean_isbn(isbn):
    # Remove all hyphens from the ISBN
    return isbn.replace('-', '')

def split_preserving_empty_columns(line):
    # Use regex to split the line while preserving empty columns, including consecutive tabs
    return re.split(r'\t', line)

def process_tsv(input_file):
    print("Step 1: Read the UTF-16 file directly and split lines into columns")
    with open(input_file, 'r', encoding='utf-16') as infile:
        headers_line = infile.readline().rstrip('\n')
        headers = split_preserving_empty_columns(headers_line)
        data = [(line.rstrip('\n'), split_preserving_empty_columns(line.rstrip('\n'))) for line in infile]

    print(f"Header columns: {headers}")
    print(f"Number of header columns: {len(headers)}")

    print("Step 2: Rename specific columns")
    column_renames = {
        'UserDefinedField1': 'StaffOnlyNotes',
        'UserDefinedField2': 'OtherInfoAboutThisTitle',
        'UserDefinedField3': 'SpecialNotesAboutParticularVolumes',
        'UserDefinedField4': 'UPEIAccessNote',
        'UserDefinedField5': 'CallNumber'
    }
    headers = [column_renames.get(header, header) for header in headers]

    print("Step 3: Replace spaces with underscores and plus sign with \"Plus\"")
    headers = [header.replace(' ', '_').replace('+', 'Plus') for header in headers]

    print(f"Processed header columns: {headers}")
    print(f"Number of processed header columns: {len(headers)}")

    print("Step 4: Create SQLite database and table")
    db_file = os.path.splitext(os.path.basename(input_file))[0] + '.db'
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    create_table_sql = 'CREATE TABLE main (' + ', '.join([f'"{header}" TEXT' for header in headers]) + ')'
    cursor.execute(create_table_sql)

    print("Step 5: Create unique index on KBID and PackageName")
    cursor.execute('CREATE UNIQUE INDEX idx_kbid_packagename ON main (KBID, PackageName)')

    print("Step 6: Create non-unique indexes")
    for column in ['Title', 'ResourceType', 'PackageName', 'VendorName']:
        cursor.execute(f'CREATE INDEX idx_{column} ON main ({column})')

    print("Step 7: Create kbid_isbns table")
    cursor.execute('CREATE TABLE kbid_isbns (KBID TEXT, ISBN TEXT, PrintOrE TEXT)')

    print("Step 8: Create unique index on kbid_isbns")
    cursor.execute('CREATE UNIQUE INDEX idx_kbid_isbn_printore ON kbid_isbns (KBID, ISBN, PrintOrE)')

    print("Step 9: Create kbid_subjects table")
    cursor.execute('CREATE TABLE kbid_subjects (KBID TEXT, Subject TEXT)')

    print("Step 10: Create unique index on kbid_subjects")
    cursor.execute('CREATE UNIQUE INDEX idx_kbid_subject ON kbid_subjects (KBID, Subject)')

    print("Step 11: Populate kbid_isbns and kbid_subjects tables")
    problem_file = 'problem_' + os.path.basename(input_file)
    problem_count = 0
    max_problems = 5

    with open(problem_file, 'w', encoding='utf-16') as problem_outfile:
        for original_line, row in data:
            if len(row) != len(headers):
                problem_count += 1
                print(f"Problem {problem_count}: Incorrect number of columns. Expected {len(headers)}, got {len(row)}")
                # Replace tabs with [TAB] for easier counting
                modified_original_line = original_line.replace('\t', '[TAB]')
                print(f"Original Line: {modified_original_line}")
                print(f"Processed Line: {row}")
                problem_outfile.write(original_line + '\n')
                if problem_count >= max_problems:
                    print(f"Halting after {max_problems} problem lines.")
                    break
                continue
            cleaned_row = [clean_line(value) for value in row]
            if any(len(value) > 20000 for value in cleaned_row):
                problem_count += 1
                print(f"Problem {problem_count}: Column value exceeds 20000 characters")
                print(f"Original Line: {original_line}")
                print(f"Processed Line: {cleaned_row}")
                problem_outfile.write(original_line + '\n')
                if problem_count >= max_problems:
                    print(f"Halting after {max_problems} problem lines.")
                    break
                continue
            cursor.execute('INSERT OR IGNORE INTO main VALUES (' + ', '.join(['?'] * len(headers)) + ')', cleaned_row)
            kbid = cleaned_row[headers.index('KBID')]
            if 'OnlineISBN' in headers:
                online_isbns = cleaned_row[headers.index('OnlineISBN')].split('|')
                for isbn in online_isbns:
                    if isbn:
                        cleaned_isbn = clean_isbn(isbn)
                        cursor.execute('INSERT OR IGNORE INTO kbid_isbns (KBID, ISBN, PrintOrE) VALUES (?, ?, ?)', (kbid, cleaned_isbn, 'Ebook'))
            if 'PrintISBN' in headers:
                print_isbns = cleaned_row[headers.index('PrintISBN')].split('|')
                for isbn in print_isbns:
                    if isbn:
                        cleaned_isbn = clean_isbn(isbn)
                        cursor.execute('INSERT OR IGNORE INTO kbid_isbns (KBID, ISBN, PrintOrE) VALUES (?, ?, ?)', (kbid, cleaned_isbn, 'Print'))
            if 'Subject' in headers:
                subjects = cleaned_row[headers.index('Subject')].split('|')
                for subject in subjects:
                    if subject:
                        cursor.execute('INSERT OR IGNORE INTO kbid_subjects (KBID, Subject) VALUES (?, ?)', (kbid, subject))

    print("Step 12: Create non-unique indexes for kbid_isbns table")
    cursor.execute('CREATE INDEX idx_kbid ON kbid_isbns (KBID)')
    cursor.execute('CREATE INDEX idx_isbn ON kbid_isbns (ISBN)')

    print("Step 13: Create non-unique indexes for kbid_subjects table")
    cursor.execute('CREATE INDEX idx_kbid_subjects_kbid ON kbid_subjects (KBID)')
    cursor.execute('CREATE INDEX idx_kbid_subjects_subject ON kbid_subjects (Subject)')

    conn.commit()
    conn.close()

    print("Processing complete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    process_tsv(input_file)

