#!/usr/bin/env python3
"""
UMBRA Branch Setup Validator
Validates that a feature branch is properly set up for development.
Based on the validation logic from ACTION_PLAN.md Phase 8.
"""

import sys
import os
import argparse
from pathlib import Path
import importlib.util

def check_python_version():
    """Check Python version compatibility."""
    if sys.version_info < (3, 11):
        print(f"❌ Python 3.11+ required. Current: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def check_project_structure():
    """Check that all required project files exist."""
    print("\n🔍 Checking project structure...")
    
    required_files = [
        'main.py',
        'requirements.txt',
        'umbra/__init__.py',
        'umbra/bot.py',
        'umbra/core/config.py',
        'umbra/core/logger.py',
        'umbra/storage/database.py',
        'umbra/ai/claude_agent.py',
        'umbra/modules/__init__.py',
        'umbra/modules/concierge_mcp.py',
        'umbra/modules/finance_mcp.py',
        'umbra/modules/business_mcp.py',
        'umbra/modules/production_mcp.py',
        'umbra/modules/creator_mcp.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ All required project files present")
    return True

def check_dependencies():
    """Check that all required dependencies can be imported."""
    print("\n🔍 Checking Python dependencies...")
    
    critical_imports = [
        ('telegram', 'python-telegram-bot'),
        ('aiohttp', 'aiohttp'),
        ('aiosqlite', 'aiosqlite'),
        ('dotenv', 'python-dotenv'),
        ('psutil', 'psutil'),
        ('httpx', 'httpx'),
        ('structlog', 'structlog'),
        ('pydantic', 'pydantic'),
    ]
    
    optional_imports = [
        ('openai', 'openai'),
        ('boto3', 'boto3'),
        ('PIL', 'Pillow'),
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
    ]
    
    missing_critical = []
    missing_optional = []
    
    for module, package in critical_imports:
        try:
            importlib.import_module(module)
            print(f"✅ {package}")
        except ImportError:
            missing_critical.append(package)
            print(f"❌ {package}")
    
    for module, package in optional_imports:
        try:
            importlib.import_module(module)
            print(f"✅ {package} (optional)")
        except ImportError:
            missing_optional.append(package)
            print(f"⚠️ {package} (optional - some features may be limited)")
    
    if missing_critical:
        print(f"\n❌ Missing critical dependencies: {', '.join(missing_critical)}")
        print("💡 Run: pip install -r requirements.txt")
        return False
    
    if missing_optional:
        print(f"\n⚠️ Missing optional dependencies: {', '.join(missing_optional)}")
        print("💡 Some advanced features may be unavailable")
    
    print("✅ All critical dependencies available")
    return True

def check_umbra_imports():
    """Check that UMBRA modules can be imported."""
    print("\n🔍 Checking UMBRA module imports...")
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    umbra_modules = [
        'umbra.core.config',
        'umbra.core.logger', 
        'umbra.storage.database',
        'umbra.ai.claude_agent',
        'umbra.modules.concierge_mcp',
        'umbra.modules.finance_mcp',
        'umbra.modules.business_mcp',
        'umbra.modules.production_mcp',
        'umbra.modules.creator_mcp',
    ]
    
    failed_imports = []
    for module in umbra_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError as e:
            failed_imports.append(f"{module}: {e}")
            print(f"❌ {module}: {e}")
    
    if failed_imports:
        print(f"\n❌ Failed to import UMBRA modules:")
        for error in failed_imports:
            print(f"   - {error}")
        return False
    
    print("✅ All UMBRA modules import successfully")
    return True

def check_environment_template():
    """Check that environment template exists."""
    print("\n🔍 Checking environment configuration...")
    
    if Path('.env.dev').exists():
        print("✅ Development environment template (.env.dev) exists")
    else:
        print("⚠️ No .env.dev template found")
    
    if Path('.env.example').exists():
        print("✅ Environment example (.env.example) exists")
    else:
        print("⚠️ No .env.example found")
    
    if Path('.env').exists():
        print("✅ Environment file (.env) exists")
        return True
    else:
        print("ℹ️ No .env file found - copy .env.dev or .env.example to .env")
        return True  # Not a failure - just needs setup

def check_development_directories():
    """Check that development directories are set up."""
    print("\n🔍 Checking development directory structure...")
    
    dev_dirs = ['data/dev', 'logs/dev', 'temp/dev']
    created_dirs = []
    
    for dir_path in dev_dirs:
        dir_obj = Path(dir_path)
        if dir_obj.exists():
            print(f"✅ {dir_path}")
        else:
            dir_obj.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dir_path)
            print(f"📁 Created {dir_path}")
    
    if created_dirs:
        print(f"✅ Created development directories: {', '.join(created_dirs)}")
    
    return True

def check_seeding_status():
    """Check if the branch has been seeded."""
    print("\n🔍 Checking branch seeding status...")
    
    if Path('.github/.seeded').exists():
        print("✅ Branch has been seeded")
        try:
            with open('.github/.seeded', 'r') as f:
                seeding_info = f.read().strip()
            print(f"📋 Seeding info:\n{seeding_info}")
        except Exception as e:
            print(f"⚠️ Could not read seeding info: {e}")
        return True
    else:
        print("ℹ️ Branch has not been automatically seeded yet")
        return True  # Not a failure

def run_final_check():
    """Run additional checks for final validation."""
    print("\n🏁 Running final validation checks...")
    
    # Check if we can instantiate the config
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from umbra.core.config import UmbraConfig
        config = UmbraConfig()
        print("✅ Configuration object can be created")
        
        # Get status summary
        status = config.get_status_summary()
        print("\n📊 Configuration Status:")
        for key, value in status.items():
            print(f"   {key}: {value}")
            
    except Exception as e:
        print(f"❌ Could not create configuration: {e}")
        return False
    
    return True

def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate UMBRA feature branch setup')
    parser.add_argument('--final-check', action='store_true', 
                       help='Run additional final validation checks')
    parser.add_argument('--quiet', action='store_true',
                       help='Only show errors and final status')
    
    args = parser.parse_args()
    
    if not args.quiet:
        print("🔍 UMBRA Feature Branch Setup Validator")
        print("=" * 50)
    
    # Define all checks
    checks = [
        ("Python Version", check_python_version),
        ("Project Structure", check_project_structure), 
        ("Dependencies", check_dependencies),
        ("UMBRA Modules", check_umbra_imports),
        ("Environment", check_environment_template),
        ("Development Directories", check_development_directories),
        ("Seeding Status", check_seeding_status),
    ]
    
    if args.final_check:
        checks.append(("Final Validation", run_final_check))
    
    # Run all checks
    passed_checks = 0
    failed_checks = []
    
    for check_name, check_func in checks:
        if not args.quiet:
            print(f"\n{'='*20} {check_name} {'='*20}")
        
        try:
            if check_func():
                passed_checks += 1
                if args.quiet:
                    print(f"✅ {check_name}")
            else:
                failed_checks.append(check_name)
                if args.quiet:
                    print(f"❌ {check_name}")
        except Exception as e:
            failed_checks.append(f"{check_name} (Exception: {e})")
            if args.quiet:
                print(f"❌ {check_name}: {e}")
    
    # Summary
    total_checks = len(checks)
    
    print(f"\n{'='*50}")
    print(f"📊 Validation Summary: {passed_checks}/{total_checks} checks passed")
    
    if failed_checks:
        print(f"\n❌ Failed checks:")
        for check in failed_checks:
            print(f"   - {check}")
        print(f"\n💡 Fix the issues above and run validation again")
        return 1
    else:
        print(f"\n✅ All checks passed! Feature branch is ready for development")
        print(f"\n🚀 Next steps:")
        print(f"   1. Configure .env file with your values")
        print(f"   2. Start development: python main.py")
        print(f"   3. Check DEVELOPMENT.md for branch-specific info")
        return 0

if __name__ == "__main__":
    sys.exit(main())