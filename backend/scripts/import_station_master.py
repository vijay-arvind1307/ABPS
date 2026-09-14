#!/usr/bin/env python3
"""
backend/scripts/import_station_master.py
Bridge runner calling scripts/import_station_master.py
"""
import os
import sys

# Add project root and backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from import_station_master import import_station_master, print_audit_report

if __name__ == "__main__":
    pdf_file = os.path.join(PROJECT_ROOT, "documents", "TN-station list.pdf")
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    
    if not os.path.exists(pdf_file):
        # Check relative
        if os.path.exists(os.path.join("..", pdf_file)):
            pdf_file = os.path.join("..", pdf_file)

    report = import_station_master(pdf_file)
    print_audit_report(report)
