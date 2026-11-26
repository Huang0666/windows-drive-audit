"""Command-line entry point and offline report writer."""

import argparse
import base64
import csv
from datetime import datetime
import gzip
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


VERSION = '1.0.0'
CSV_COLUMNS = ['完整路径', '所属软件或用途', '归属依据', '处理建议', '具体说明', '读取状态',
               '仅本层计入字节', '含子目录计入字节', '含子目录按路径字节', '可见文件数',
               '读取有缺项目录数', '未展开链接数']


def drive_root(value):
    if not re.fullmatch(r'[A-Za-z](?::[\\/]?)?', value.strip()):
        raise argparse.ArgumentTypeError('Use a drive letter such as C: or D:.')
    return value.strip()[0].upper() + ':\\'


def windows_store_apps(root):
    from rules import relative_to_drive

    program_files = relative_to_drive(root, os.environ.get('ProgramW6432') or os.environ.get('ProgramFiles', ''))
    stores = {'windowsapps'}
    if program_files:
        stores.add((program_files + '\\WindowsApps').casefold())
    system_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    powershell = system_root / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    if not powershell.is_file():
        return stores, {}
    command = ('[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); '
               'ConvertTo-Json -InputObject @(Get-AppxPackage -ErrorAction Stop | '
               'Select-Object Name,InstallLocation) -Compress')
    try:
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, encoding='utf-8-sig', errors='replace', timeout=25,
                                check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        packages = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return stores, {}
    records = {}
    for item in packages:
        location = item.get('InstallLocation')
        if not location:
            continue
        path = relative_to_drive(root, location)
        parent, separator, _ = path.rpartition('\\')
        if separator and parent.split('\\')[-1].casefold() == 'windowsapps':
            stores.add(parent.casefold())
            records[path] = item['Name']
    return stores, records


def report_rows(rows, root, programs, packages, stores):
    from rules import build_rules, classify, relative_to_drive

    rules = build_rules(root, programs, packages, stores)
    profile = relative_to_drive(root, os.environ.get('USERPROFILE', '')).casefold()
    labels = []
    label_ids = {}
    for row in rows:
        parent = labels[rows[row[1]][9]] if row[1] >= 0 else rules['']
        label = classify(row, parent, rules, profile)
        if label not in label_ids:
            label_ids[label] = len(labels)
            labels.append(label)
        row.append(label_ids[label])
    return labels


def csv_literal(value):
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r', '\n'):
        return "'" + value
    return value


def write_reports(directory, model):
    def csv_rows():
        for row in model['rows']:
            yield [model['root'] + row[0], *map(csv_literal, model['labels'][row[9]]), row[2], *row[3:9]]

    compressed = directory / 'directories.csv.zip'
    with zipfile.ZipFile(compressed, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        with archive.open('directories.csv', 'w') as member, io.TextIOWrapper(
            member, encoding='utf-8-sig', errors='backslashreplace', newline=''
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(CSV_COLUMNS)
            writer.writerows(csv_rows())

    asset_root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    template = (asset_root / 'assets' / 'report.html').read_text(encoding='utf-8')
    payload = json.dumps(model, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    encoded_payload = base64.b64encode(gzip.compress(payload, compresslevel=5)).decode('ascii')
    html = directory / 'index.html'
    html.write_text(template.replace('__INVENTORY_DATA__', encoded_payload), encoding='utf-8')
    return html, compressed


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only Windows drive inventory. Outputs offline HTML and a ZIP containing CSV.')
    parser.add_argument('--drive', type=drive_root, default='C:', help='Local drive letter (default C:)')
    parser.add_argument('--output-dir', type=Path, default=Path.home() / 'Documents' / 'WindowsDriveAudit',
                        help='Base directory for reports')
    parser.add_argument('--no-open', action='store_true', help='Generate reports without opening the browser')
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args(argv)
    if sys.platform != 'win32' or sys.version_info < (3, 12):
        parser.error('Windows and Python 3.12 or later are required for the source version.')

    from win_scan import installed_programs, scan, volume_format

    root = args.drive
    filesystem = volume_format(root)
    stamp = datetime.now().astimezone()
    print(f'Scanning {root} ({filesystem}) ...', flush=True)
    stores, packages = windows_store_apps(root)
    programs = installed_programs(root)
    rows, usage = scan(root, filesystem, stores, packages, progress=lambda count: print(f'{count:,} folders indexed...', flush=True))
    model = {'rows': rows, 'labels': report_rows(rows, root, programs, packages, stores),
             'root': root, 'filesystem': filesystem, 'volume': usage,
             'day': stamp.date().isoformat(), 'allocated': filesystem.upper() == 'NTFS'}
    base = args.output_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    prefix = root[0] + '-' + stamp.strftime('%Y%m%d-%H%M%S') + '-'
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
    html, csv_zip = write_reports(directory, model)
    print(f'Folders: {len(rows) - 1:,} | Partial reads: {rows[0][7]:,} | Skipped links: {rows[0][8]:,}')
    print(f'HTML: {html}\nCSV:  {csv_zip}', flush=True)
    if not args.no_open:
        try:
            os.startfile(html)
        except OSError:
            print('Open the HTML path above in Edge or Chrome.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='backslashreplace')
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Scan stopped.', file=sys.stderr)
        raise SystemExit(130) from None
    except (OSError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        if getattr(sys, 'frozen', False) and len(sys.argv) == 1 and sys.stdin.isatty():
            input('Press Enter to close.')
        raise SystemExit(1) from None
