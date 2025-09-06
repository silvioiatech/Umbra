"""
Document ingestion module for Swiss Accountant
Handles OCR, document parsing, and statement processing.
"""

from .ocr import OCRProcessor, create_ocr_processor
from .parsers import DocumentParser, DocumentType, create_document_parser
from .statements import StatementParser, StatementFormat, create_statement_parser

__all__ = [
    'OCRProcessor', 'create_ocr_processor',
    'DocumentParser', 'DocumentType', 'create_document_parser',
    'StatementParser', 'StatementFormat', 'create_statement_parser'
]
