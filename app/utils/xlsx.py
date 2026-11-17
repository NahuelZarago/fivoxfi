"""
Escritor mínimo de archivos .xlsx (Excel) y CSV, sin dependencias externas.

Un .xlsx es un ZIP con XML. Acá se genera una hoja con encabezado fijo, filtros, anchos de
columna y formatos de moneda/fecha. Los textos se guardan como texto (inlineStr), nunca como
fórmulas, así que un producto llamado "=CMD()" no se ejecuta.
"""
import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

# Tipos de columna
TEXT = 'text'
INT = 'int'
MONEY = 'money'
DATETIME = 'datetime'

_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]')
_EPOCH = datetime(1899, 12, 30)
_MAX_ROWS = 1_048_575          # Límite de filas de Excel menos el encabezado
_FORMULA_START = ('=', '+', '-', '@', '\t', '\r')


def _clean(value):
    return _CONTROL.sub('', str(value))


def col_letter(index):
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _serial(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    if isinstance(value, datetime):
        delta = value - _EPOCH
    else:
        delta = datetime(value.year, value.month, value.day) - _EPOCH
    return delta.days + delta.seconds / 86400


def _cell(ref, value, kind, style_ids):
    if value is None or value == '':
        return ''
    if kind == MONEY:
        return f'<c r="{ref}" s="{style_ids[MONEY]}"><v>{Decimal(value):f}</v></c>'
    if kind == INT:
        return f'<c r="{ref}" s="{style_ids[INT]}"><v>{int(value)}</v></c>'
    if kind == DATETIME and isinstance(value, (datetime, date)):
        return f'<c r="{ref}" s="{style_ids[DATETIME]}"><v>{_serial(value):.6f}</v></c>'
    text = escape(_clean(value))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


_STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy\\ hh:mm"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF16A34A"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

_STYLE_IDS = {MONEY: 2, DATETIME: 3, INT: 4}


def build_xlsx(sheet_name, columns, rows):
    """
    columns: lista de (título, tipo, ancho). rows: iterable de secuencias, una por fila.
    Devuelve los bytes del .xlsx.
    """
    safe_name = re.sub(r'[\[\]\*\?/\\:]', ' ', sheet_name)[:31] or 'Datos'
    out = []
    header = ''.join(_cell(f'{col_letter(i)}1', title, TEXT, _STYLE_IDS).replace('<c ', '<c s="1" ', 1)
                     for i, (title, _kind, _w) in enumerate(columns))
    out.append(f'<row r="1">{header}</row>')
    count = 0
    for n, row in enumerate(rows, start=2):
        if n - 1 > _MAX_ROWS:
            break
        cells = ''.join(_cell(f'{col_letter(i)}{n}', row[i], columns[i][1], _STYLE_IDS)
                        for i in range(len(columns)))
        out.append(f'<row r="{n}">{cells}</row>')
        count += 1
    last = f'{col_letter(len(columns) - 1)}{max(count + 1, 1)}'
    cols = ''.join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                   for i, (_t, _k, w) in enumerate(columns))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             f'<cols>{cols}</cols><sheetData>{"".join(out)}</sheetData>'
             f'<autoFilter ref="A1:{last}"/></worksheet>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets><sheet name="{escape(safe_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                     '</Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
               '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
               '</Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', root_rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        z.writestr('xl/styles.xml', _STYLES)
        z.writestr('xl/worksheets/sheet1.xml', sheet)
    return buf.getvalue()


def _csv_value(value, kind):
    if value is None:
        return ''
    if kind == MONEY:
        return f'{Decimal(value):.2f}'.replace('.', ',')
    if kind == DATETIME and isinstance(value, (datetime, date)):
        return value.strftime('%d/%m/%Y %H:%M') if isinstance(value, datetime) else value.strftime('%d/%m/%Y')
    text = _clean(value)
    if kind == TEXT and text.startswith(_FORMULA_START):
        text = "'" + text          # Evita que Excel lo interprete como fórmula
    return text


def build_csv(columns, rows):
    """CSV para Excel en español: separador ';', coma decimal y BOM UTF-8 para los acentos."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=';', lineterminator='\r\n')
    writer.writerow([_clean(t) for t, _k, _w in columns])
    for row in rows:
        writer.writerow([_csv_value(row[i], columns[i][1]) for i in range(len(columns))])
    return ('﻿' + buf.getvalue()).encode('utf-8')
