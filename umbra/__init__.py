"""
Umbra MCP - Claude Desktop-style AI with MCP Modules
Version 3.0.0
"""

__version__ = "3.0.0"
__author__ = "Silvio Correia"
__description__ = "Claude Desktop-style AI assistant with MCP modules for VPS and business management"

# Conditional imports to avoid telegram dependency during testing
try:
    from .bot import UmbraAIAgent, UmbraBot
    __all__ = ['UmbraAIAgent', 'UmbraBot', '__version__']
except ImportError:
    # When telegram is not available, only export version
    __all__ = ['__version__']
