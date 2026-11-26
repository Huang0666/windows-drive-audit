---
name: windows-drive-audit
description: Scan a selected local Windows drive and generate a read-only per-folder disk inventory with software attribution, storage usage, and cleanup guidance. Use for requests to find what is filling C or another local drive, inspect AppData or Windows folders, or list cleanup candidates for the user to review.
---

# Windows Drive Audit

Run `python -B scripts/drive_audit.py --drive C: --output-dir <report-directory> --no-open` from this skill's folder. Use the drive letter the user gives, or C: for an unspecified Windows system drive. The source runner uses Python 3.12+ and its standard library. A portable Windows executable can run the same scanner without Python.

Return the HTML and ZIP paths printed by the command. The HTML shows a directory tree, global search and cleanup filters. The ZIP contains one CSV row for each discovered directory. Keep generated reports local unless the user authorizes sharing them. They can contain usernames, software names and private directory paths.

Explain ownership using the reported evidence. Installed-app registration is stronger evidence than a folder-name clue. Treat a parent's total as inclusive of descendants, and use the direct-file byte column for additive rollups. Disk usage is a separate volume-level reading. Some folders are protected or redirected, and the difference between drive usage and summed NTFS file allocations is unassigned. Other file systems report logical file sizes.

The scanner reads metadata and recommends actions. A cleanup request is a separate operation. Treat mixed application data, backups, system stores and unknown names accordingly, and respect the user's authorization and normal Windows tools before any change.
