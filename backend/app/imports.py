"""Transient statement parsing and owner-scoped, idempotent confirmation."""
import csv
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError
from defusedxml.common import DefusedXmlException
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .database import get_db
from .models import Category, CategoryLabel, Transaction, User
from .schemas import ImportConfirm, TransactionCreate
from .security import current_user
from .intelligence.categorizer import save_label, suggest_category

router = APIRouter(prefix='/api/imports', tags=['Statement imports'])
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
ALIASES = {
    'transaction_date': ['date', 'transactiondate', 'valuedate', 'postingdate', 'posteddate', 'txndate'],
    'description': ['description', 'transactiondescription', 'details', 'narration', 'particulars', 'memo', 'transactiondetails'],
    'merchant': ['merchant', 'payee', 'beneficiary', 'vendor'],
    'amount': ['amount', 'transactionamount', 'value'],
    'debit': ['debit', 'debitamount', 'withdrawal', 'withdrawals', 'paidout'],
    'credit': ['credit', 'creditamount', 'deposit', 'deposits', 'paidin'],
    'transaction_type': ['type', 'transactiontype', 'direction', 'drcr', 'debitcredit'],
    'category': ['category', 'categoryname'],
}

def normalized(value):
    return ' '.join(str(value or '').strip().casefold().split())

def fingerprint(record):
    """Category/source changes do not turn the same statement row into a new transaction."""
    if isinstance(record, dict):
        return (str(record['transaction_date']), normalized(record['description']), money_key(record['amount']), record['transaction_type'], normalized(record.get('merchant')))
    return (record.transaction_date.isoformat(), normalized(record.description), money_key(record.amount), record.transaction_type, normalized(record.merchant))

def money_key(value):
    return format(Decimal(value), '.2f')

def existing_fingerprints(db, user_id, dates):
    if not dates:
        return set()
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user_id, Transaction.transaction_date >= min(dates), Transaction.transaction_date <= max(dates))).all()
    return {fingerprint(row) for row in rows}

def parse_amount(value):
    raw = str(value).strip()
    if raw.casefold() in ('', 'nan', 'none', '-', '—'):
        return Decimal(0)
    negative = raw.startswith('(') and raw.endswith(')') or bool(re.search(r'\bDR\s*$', raw, re.I))
    raw = re.sub(r'(?i)\b(?:LKR|RS|CR|DR)\b\.?', '', raw)
    raw = raw.replace(' ', '').replace('\u00a0', '').replace('−', '-')
    if '(' in raw or ')' in raw:
        if not (raw.startswith('(') and raw.endswith(')')):
            raise ValueError('Invalid amount parentheses')
        raw = raw[1:-1]
    if ',' in raw and not re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?', raw):
        raise ValueError('Use comma thousands separators and a decimal point')
    raw = raw.replace(',', '')
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError('Invalid amount')
    if not value.is_finite():
        raise ValueError('Amount must be finite')
    return -abs(value) if negative else value

def parse_date(value, day_first):
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.date() if isinstance(value, datetime) else value
    raw = str(value).strip()
    if not raw:
        raise ValueError('Date is missing')
    if re.fullmatch(r'\d+(?:\.0)?', raw):
        number = float(raw)
        if 20000 <= number <= 80000:
            return (datetime(1899, 12, 30) + timedelta(days=number)).date()
        if re.fullmatch(r'\d{8}', raw):
            return datetime.strptime(raw, '%Y%m%d').date()
        raise ValueError('Date must be a calendar date')
    if re.match(r'^\d{4}-\d{2}-\d{2}', raw):
        return pd.to_datetime(raw, errors='raise').date()
    return pd.to_datetime(raw, dayfirst=day_first, format='mixed', errors='raise').date()

def read_statement(raw, extension):
    if not raw:
        raise HTTPException(422, 'The statement is empty')
    warnings = []
    try:
        if extension == '.csv':
            try:
                decoded = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                decoded = raw.decode('cp1252')
                warnings.append('Read using Windows-1252 encoding. Please check descriptions.')
            if '\x00' in decoded:
                raise ValueError('CSV must be a text file')
            try:
                separator = csv.Sniffer().sniff(decoded[:8192], delimiters=',;\t|').delimiter
            except csv.Error:
                separator = ','
            reader = csv.reader(StringIO(decoded), delimiter=separator, strict=True)
            header = next(reader, None)
            if not header:
                raise ValueError('Header is missing')
            if len(set(str(column).strip() for column in header)) != len(header):
                raise ValueError('Column names must be unique')
            row_count = 0
            for row_number, cells in enumerate(reader, start=2):
                if not cells or all(not value.strip() for value in cells):
                    continue
                if len(cells) != len(header):
                    raise HTTPException(422, f'Row {row_number} has a different number of columns. Check the CSV delimiter and quoting.')
                row_count += 1
                if row_count > MAX_ROWS:
                    raise HTTPException(413, 'Import at most 2,000 rows at a time')
            frame = pd.read_csv(StringIO(decoded), sep=separator, dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1)
        else:
            with ZipFile(BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(entry.file_size for entry in entries) > 25 * 1024 * 1024:
                    raise HTTPException(413, 'Excel workbook is too large when decompressed')
                if '[Content_Types].xml' not in archive.namelist() or 'xl/workbook.xml' not in archive.namelist():
                    raise ValueError('Not a valid XLSX workbook')
            frame = pd.read_excel(BytesIO(raw), engine='openpyxl', dtype=object, keep_default_na=False, nrows=MAX_ROWS + 1, engine_kwargs={'keep_links': False})
            warnings.append('Only the first worksheet is imported.')
    except HTTPException:
        raise
    except (ValueError, UnicodeError, csv.Error, BadZipFile, pd.errors.ParserError, pd.errors.EmptyDataError, KeyError, OSError, ParseError, DefusedXmlException, RuntimeError) as exc:
        raise HTTPException(422, 'Cannot parse this statement. Use a CSV or XLSX file with a header row and consistent columns.') from exc
    if len(frame) > MAX_ROWS:
        raise HTTPException(413, 'Import at most 2,000 rows at a time')
    if frame.empty:
        raise HTTPException(422, 'The statement has no transaction rows')
    if len(frame.columns) > 50:
        raise HTTPException(422, 'Statements may contain at most 50 columns')
    frame.columns = [str(column).strip() for column in frame.columns]
    if len(set(frame.columns)) != len(frame.columns):
        raise HTTPException(422, 'Column names must be unique')
    return frame, warnings

def infer_mapping(columns):
    normalized_columns = {re.sub(r'[^a-z0-9]', '', name.casefold()): name for name in columns}
    return {field: next((normalized_columns[alias] for alias in aliases if alias in normalized_columns), '') for field, aliases in ALIASES.items()}

@router.post('/preview')
def preview_statement(
    file: UploadFile = File(...), mapping: str = Form(default='{}'),
    day_first: bool = Form(default=True), default_type: Literal['income', 'expense'] = Form(default='expense'),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    try:
        extension = Path(file.filename or '').suffix.lower()
        if extension not in ('.csv', '.xlsx'):
            raise HTTPException(415, 'Upload a .csv or .xlsx statement')
        accepted = {'text/csv', 'application/csv', 'text/plain', 'application/octet-stream', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        if file.content_type and file.content_type.split(';')[0].lower() not in accepted:
            raise HTTPException(415, 'Unsupported statement content type')
        raw = file.file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, 'Statements must be 5 MB or smaller')
        frame, warnings = read_statement(raw, extension)
    finally:
        file.file.close()  # Close and delete any UploadFile spool immediately after extraction.
    columns = list(frame.columns)
    detected = infer_mapping(columns)
    try:
        overrides = json.loads(mapping)
        if not isinstance(overrides, dict) or any(key not in ALIASES or not isinstance(value, str) or value and value not in columns for key, value in overrides.items()):
            raise ValueError()
        detected.update(overrides)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Column mapping must reference columns in this statement')
    required = bool(detected['transaction_date'] and detected['description'] and (detected['amount'] or detected['debit'] or detected['credit']))
    result = {'columns': columns, 'mapping': detected, 'mapping_required': not required, 'source': extension[1:], 'warnings': warnings, 'rows': [], 'total_rows': len(frame), 'valid_rows': 0, 'invalid_rows': 0, 'duplicates': 0}
    if not required:
        result['warnings'].append('Map a date, description, and amount or debit/credit column, then parse again.')
        return result
    categories = db.scalars(select(Category)).all()
    labels = db.scalars(select(CategoryLabel).where(CategoryLabel.user_id == user.id).order_by(CategoryLabel.updated_at.desc(), CategoryLabel.id.desc())).all()
    result['warnings'].append('All amounts are treated as LKR; no currency conversion is performed.')
    result['warnings'].append('Categories use your private labels, merchant rules, then a starter text classifier. Confidence scores are uncalibrated; review suggestions before importing.')
    if detected['amount'] and not detected['transaction_type'] and not (detected['debit'] or detected['credit']):
        result['warnings'].append(f'Negative amounts are expenses; positive amounts default to {default_type}. Change the default or correct individual rows if needed.')
    valid_dates = []
    for index, row in frame.iterrows():
        values = {key: row[column] if column else '' for key, column in detected.items()}
        record = {'transaction_date': '', 'description': str(values['description']).strip(), 'merchant': str(values['merchant']).strip() or None, 'amount': '', 'transaction_type': default_type, 'category_id': None, 'source': extension[1:]}
        errors = []
        try:
            parsed_date = parse_date(values['transaction_date'], day_first)
            record['transaction_date'] = parsed_date.isoformat()
        except (ValueError, TypeError, OverflowError):
            errors.append('Invalid or missing date')
        try:
            if detected['debit'] or detected['credit']:
                debit, credit = parse_amount(values['debit']), parse_amount(values['credit'])
                if debit < 0 or credit < 0 or debit and credit:
                    raise ValueError('Use one positive debit or credit per row')
                amount = debit or credit
                direction = 'expense' if debit else 'income'
            else:
                amount = parse_amount(values['amount'])
                kind = normalized(values['transaction_type'])
                if kind in ('income', 'credit', 'cr', 'deposit'):
                    direction = 'income'
                elif kind in ('expense', 'debit', 'dr', 'withdrawal'):
                    direction = 'expense'
                elif kind:
                    raise ValueError('Unknown income/expense type')
                else:
                    direction = 'expense' if amount < 0 else default_type
            record.update(amount=str(abs(amount)), transaction_type=direction)
        except ValueError as exc:
            errors.append(str(exc))
        category_suggestion = suggest_category(db, user.id, record['description'], record['merchant'], record['transaction_type'], categories=categories, labels=labels)
        explicit = next((category for category in categories if normalized(category.name) == normalized(values['category']) and category.type == record['transaction_type']), None)
        record['category_id'] = explicit.id if explicit else category_suggestion['category_id']
        if explicit:
            category_suggestion = {**category_suggestion, 'category_id': explicit.id, 'category_name': explicit.name, 'method': 'statement_label', 'confidence': 1, 'reason': 'Category provided in the statement.'}
        if not errors:
            try:
                cleaned = TransactionCreate.model_validate(record)
                record = cleaned.model_dump(mode='json')
                record['amount'] = money_key(cleaned.amount)
                valid_dates.append(cleaned.transaction_date)
            except ValidationError as exc:
                errors.extend(f"{error['loc'][-1]}: {error['msg']}" for error in exc.errors())
        result['rows'].append({'row_number': int(index) + 2, 'transaction': record, 'errors': errors, 'duplicate': False, 'suggestion': category_suggestion})
    seen = existing_fingerprints(db, user.id, valid_dates)
    for row in result['rows']:
        if row['errors']:
            result['invalid_rows'] += 1
            continue
        key = fingerprint(row['transaction'])
        row['duplicate'] = key in seen
        seen.add(key)
        result['valid_rows'] += 1
        result['duplicates'] += int(row['duplicate'])
    return result

@router.post('/confirm', status_code=201)
def confirm_import(body: ImportConfirm, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Serialize imports for this owner so concurrent confirmations cannot insert duplicates.
    db.execute(text('SELECT pg_advisory_xact_lock(:namespace, :user_id)'), {'namespace': 1819043180, 'user_id': user.id})
    categories = {category.id: category for category in db.scalars(select(Category)).all()}
    for record in body.transactions:
        category = categories.get(record.category_id)
        if category is None or category.type != record.transaction_type:
            raise HTTPException(422, 'Every category must match its transaction type')
    seen = existing_fingerprints(db, user.id, [record.transaction_date for record in body.transactions])
    imported, skipped = 0, 0
    for record in body.transactions:
        key = fingerprint(record)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        transaction = Transaction(**record.model_dump(exclude={'source', 'category_confirmed'}), user_id=user.id, source=body.source)
        db.add(transaction)
        if record.category_confirmed:
            db.flush()
            save_label(db, transaction)
        imported += 1
    db.commit()
    return {'imported': imported, 'skipped_duplicates': skipped}
