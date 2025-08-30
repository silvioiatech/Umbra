"""
Entry point for running Umbra Bot as a module.

Usage: python -m umbra.bot
"""

import asyncio
from .bot import main

if __name__ == "__main__":
    asyncio.run(main())