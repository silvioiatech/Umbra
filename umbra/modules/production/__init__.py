"""
Production Module Package

Advanced n8n workflow creation and management with AI-powered assistance.
"""

from .planner import WorkflowPlanner, ComplexityTier
from .catalog import CatalogManager, NodeInfo, CatalogEntry
from .selector import NodeSelector, NodeMapping
from .builder import WorkflowBuilder, WorkflowConnection, WorkflowNode
from .controller import ProductionController, EscalationLevel, ProcessingStage
from .validator import WorkflowValidator, ValidationIssue, ValidationResult
from .tester import WorkflowTester, TestExecution, TestResult
from .importer import WorkflowImporter, ImportConflict, ImportDiff, ImportResult
from .exporter import WorkflowExporter, ExportOptions, ExportResult
from .stickies import StickyNotesManager, StickyNote, StickyNotesResult
from .redact import ProductionRedactor, RedactionRule, RedactionResult
from .costs import CostManager, CostEntry, BudgetLimit, CostSummary
from .n8n_client import N8nClient, N8nCredentials

__version__ = "0.1.0"

__all__ = [
    # Core components
    "WorkflowPlanner",
    "CatalogManager", 
    "NodeSelector",
    "WorkflowBuilder",
    "ProductionController",
    "WorkflowValidator",
    "WorkflowTester",
    "WorkflowImporter",
    "WorkflowExporter",
    "StickyNotesManager",
    "ProductionRedactor",
    "CostManager",
    "N8nClient",
    
    # Data classes
    "ComplexityTier",
    "NodeInfo",
    "CatalogEntry",
    "NodeMapping",
    "WorkflowConnection",
    "WorkflowNode",
    "EscalationLevel",
    "ProcessingStage",
    "ValidationIssue",
    "ValidationResult",
    "TestExecution",
    "TestResult",
    "ImportConflict",
    "ImportDiff",
    "ImportResult",
    "ExportOptions",
    "ExportResult",
    "StickyNote",
    "StickyNotesResult",
    "RedactionRule",
    "RedactionResult",
    "CostEntry",
    "BudgetLimit",
    "CostSummary",
    "N8nCredentials"
]
