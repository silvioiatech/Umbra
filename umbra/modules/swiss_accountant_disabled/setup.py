#!/usr/bin/env python3
"""
Swiss Accountant Setup Script
Automated installation and configuration for Swiss Accountant module.
"""

import os
import sys
import subprocess
import platform
import json
import shutil
from pathlib import Path
import tempfile

def print_header():
    """Print setup header."""
    print("🇨🇭 Swiss Accountant Setup")
    print("=" * 50)
    print("Automated installation and configuration")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print("")

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print("✅ Python version compatible")
    return True

def install_python_dependencies():
    """Install required Python packages."""
    print("\n📦 Installing Python Dependencies")
    print("-" * 35)
    
    required_packages = [
        "Pillow>=9.0.0",
        "pytesseract>=0.3.8", 
        "openpyxl>=3.0.9"
    ]
    
    optional_packages = [
        "pdf2image>=1.16.0",  # For PDF processing
        "opencv-python>=4.5.0",  # For image enhancement
    ]
    
    success = True
    
    # Install required packages
    for package in required_packages:
        print(f"   Installing {package}...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True, text=True)
            print(f"   ✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to install {package}: {e}")
            success = False
    
    # Install optional packages (don't fail if these don't work)
    print(f"\n   Installing optional packages...")
    for package in optional_packages:
        print(f"   Installing {package} (optional)...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True, text=True)
            print(f"   ✅ {package} installed successfully")
        except subprocess.CalledProcessError:
            print(f"   ⚠️  {package} installation failed (optional, continuing)")
    
    return success

def check_tesseract():
    """Check if Tesseract OCR is installed."""
    print("\n🔍 Checking Tesseract OCR")
    print("-" * 25)
    
    try:
        result = subprocess.run(["tesseract", "--version"], 
                              capture_output=True, text=True, check=True)
        version_line = result.stdout.split('\n')[0]
        print(f"   ✅ Tesseract found: {version_line}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   ❌ Tesseract OCR not found")
        return False

def install_tesseract_instructions():
    """Provide Tesseract installation instructions."""
    print("\n📥 Tesseract Installation Instructions")
    print("-" * 40)
    
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        print("   macOS installation:")
        print("   1. Install Homebrew if not already installed:")
        print("      /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        print("   2. Install Tesseract:")
        print("      brew install tesseract tesseract-lang")
        print("   3. Verify installation:")
        print("      tesseract --version")
        
    elif system == "linux":
        print("   Linux (Ubuntu/Debian) installation:")
        print("   1. Update package list:")
        print("      sudo apt-get update")
        print("   2. Install Tesseract and language packs:")
        print("      sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita")
        print("   3. Verify installation:")
        print("      tesseract --version")
        
    elif system == "windows":
        print("   Windows installation:")
        print("   1. Download Tesseract installer from:")
        print("      https://github.com/UB-Mannheim/tesseract/wiki")
        print("   2. Run the installer and follow instructions")
        print("   3. Add Tesseract to your PATH environment variable")
        print("   4. Verify installation:")
        print("      tesseract --version")
    
    else:
        print(f"   Unsupported platform: {system}")
        print("   Please refer to Tesseract documentation for installation instructions")
    
    print("\n   📝 Note: Swiss Accountant supports German, French, Italian, and English")
    print("      Make sure to install language packs for all required languages")

def test_tesseract_languages():
    """Test if required language packs are available."""
    print("\n🌍 Testing Tesseract Language Support")
    print("-" * 38)
    
    required_languages = {
        'deu': 'German',
        'fra': 'French', 
        'ita': 'Italian',
        'eng': 'English'
    }
    
    available_languages = []
    missing_languages = []
    
    try:
        result = subprocess.run(["tesseract", "--list-langs"], 
                              capture_output=True, text=True, check=True)
        installed_langs = result.stdout.strip().split('\n')[1:]  # Skip header
        
        for lang_code, lang_name in required_languages.items():
            if lang_code in installed_langs:
                print(f"   ✅ {lang_name} ({lang_code}) - Available")
                available_languages.append(lang_code)
            else:
                print(f"   ❌ {lang_name} ({lang_code}) - Missing")
                missing_languages.append(lang_code)
        
        if missing_languages:
            print(f"\n   ⚠️  Missing language packs: {', '.join(missing_languages)}")
            print(f"      Install with your package manager or Tesseract installer")
            return False
        else:
            print(f"\n   ✅ All required languages available")
            return True
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   ❌ Cannot check languages - Tesseract not properly installed")
        return False

def create_config_file():
    """Create default configuration file."""
    print("\n⚙️  Creating Configuration File")
    print("-" * 32)
    
    config_path = Path(__file__).parent / "config.json"
    
    if config_path.exists():
        print(f"   ⚠️  Configuration file already exists: {config_path}")
        response = input("   Do you want to overwrite it? (y/N): ").lower()
        if response != 'y':
            print("   ⏭️  Skipping configuration file creation")
            return True
    
    # Get user preferences
    print(f"   📝 Configuration Setup:")
    
    # Canton selection
    swiss_cantons = [
        'AG', 'AI', 'AR', 'BE', 'BL', 'BS', 'FR', 'GE', 'GL', 'GR',
        'JU', 'LU', 'NE', 'NW', 'OW', 'SG', 'SH', 'SO', 'SZ', 'TG',
        'TI', 'UR', 'VD', 'VS', 'ZG', 'ZH'
    ]
    
    print(f"   Available cantons: {', '.join(swiss_cantons)}")
    canton = input("   Enter your canton (e.g., ZH, GE, VD): ").upper()
    
    if canton not in swiss_cantons:
        print(f"   ⚠️  Unknown canton '{canton}', using ZH as default")
        canton = 'ZH'
    
    # Database path
    default_db_path = str(Path.home() / "swiss_accountant.db")
    db_path = input(f"   Database path [{default_db_path}]: ").strip()
    if not db_path:
        db_path = default_db_path
    
    # Log level
    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    print(f"   Log levels: {', '.join(log_levels)}")
    log_level = input("   Log level [INFO]: ").upper()
    if log_level not in log_levels:
        log_level = 'INFO'
    
    # Create configuration
    config = {
        "database_path": db_path,
        "log_level": log_level,
        "canton": canton,
        "ocr_language": "deu+fra+ita+eng",
        "default_currency": "CHF",
        "default_vat_rate": 8.1,
        "reconciliation_auto_accept": True,
        "export_formats": ["csv", "xlsx", "json"],
        
        "_comment": "Swiss Accountant Configuration",
        "_created": str(Path(__file__).parent / "setup.py"),
        "_canton_info": f"Tax calculations for canton {canton}",
        
        "reconciliation": {
            "exact_match_tolerance_days": 2,
            "probable_match_tolerance_days": 7,
            "amount_tolerance_percentage": 0.01,
            "minimum_match_score": 0.7,
            "auto_accept_exact_threshold": 0.95,
            "auto_accept_probable_threshold": 0.85
        },
        
        "merchant_normalization": {
            "auto_learn": True,
            "confidence_threshold": 0.8,
            "fuzzy_match_threshold": 0.6
        },
        
        "storage": {
            "receipts_directory": "receipts",
            "statements_directory": "statements", 
            "exports_directory": "exports",
            "max_file_size_mb": 50
        }
    }
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Configuration saved to: {config_path}")
        print(f"      Canton: {canton}")
        print(f"      Database: {db_path}")
        print(f"      Log level: {log_level}")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to create configuration: {e}")
        return False

def test_installation():
    """Test the Swiss Accountant installation."""
    print("\n🧪 Testing Installation")
    print("-" * 25)
    
    try:
        # Add current directory to path for testing
        current_dir = Path(__file__).parent.parent.parent.parent
        sys.path.insert(0, str(current_dir))
        
        # Import and test
        from umbra.modules.swiss_accountant import quick_start, get_version
        
        print(f"   ✅ Swiss Accountant module imported successfully")
        print(f"   📋 Version: {get_version()}")
        
        # Create temporary database for testing
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            test_db_path = tmp_db.name
        
        try:
            # Test initialization
            sa = quick_start(user_id="test_setup_user", db_path=test_db_path)
            print(f"   ✅ Swiss Accountant initialized successfully")
            
            # Test health check
            health = sa.health_check()
            print(f"   ✅ Health check: {health['status']}")
            
            # Test basic functionality
            dashboard = sa.get_dashboard_summary()
            if 'error' not in dashboard:
                print(f"   ✅ Dashboard functionality working")
            
            print(f"   ✅ All basic tests passed")
            return True
            
        finally:
            # Cleanup test database
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
        
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        print(f"      Make sure you're running this script from the correct directory")
        return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    print("\n📁 Creating Directories")
    print("-" * 23)
    
    directories = [
        "receipts",
        "statements", 
        "exports",
        "backups"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        try:
            dir_path.mkdir(exist_ok=True)
            print(f"   ✅ Created/verified: {directory}/")
        except Exception as e:
            print(f"   ❌ Failed to create {directory}/: {e}")
            return False
    
    return True

def show_completion_message():
    """Show setup completion message."""
    print("\n🎉 Setup Complete!")
    print("=" * 50)
    print("✅ Swiss Accountant is ready to use")
    print("")
    print("📚 Getting Started:")
    print("   1. Run the test script:")
    print("      python test_swiss_accountant.py")
    print("")
    print("   2. Try the examples:")
    print("      python examples/complete_workflow.py")
    print("      python examples/receipt_processing.py")
    print("      python examples/bank_reconciliation.py")
    print("      python examples/tax_optimization.py")
    print("")
    print("   3. Use the command line interface:")
    print("      python -m umbra.modules.swiss_accountant.cli --help")
    print("")
    print("   4. Or use programmatically:")
    print("      from umbra.modules.swiss_accountant import quick_start")
    print("      sa = quick_start(user_id='your_user_id')")
    print("")
    print("💡 Next Steps:")
    print("   • Process your first receipt with process_receipt()")
    print("   • Import bank statements with process_bank_statement()")
    print("   • Reconcile expenses with reconcile_expenses()")
    print("   • Calculate tax deductions with calculate_tax_deductions()")
    print("   • Export data with export_tax_data()")
    print("")
    print("📖 Documentation:")
    print("   • README.md - Comprehensive guide")
    print("   • config.json - Configuration options")
    print("   • examples/ - Usage examples")
    print("")
    print("🆘 Support:")
    print("   • Run health check: python -c \"from umbra.modules.swiss_accountant import quick_start; quick_start('test').health_check()\"")
    print("   • Check logs in swiss_accountant.log")

def main():
    """Main setup function."""
    print_header()
    
    # Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    # Install Python dependencies
    if not install_python_dependencies():
        print("\n❌ Failed to install required Python packages")
        print("   Please install manually and run setup again")
        sys.exit(1)
    
    # Check Tesseract
    tesseract_available = check_tesseract()
    if not tesseract_available:
        install_tesseract_instructions()
        print("\n⚠️  Tesseract OCR is required for receipt processing")
        print("   You can continue setup and install Tesseract later")
        print("   OCR functionality will not work until Tesseract is installed")
        
        response = input("\nContinue setup without Tesseract? (y/N): ").lower()
        if response != 'y':
            print("Setup cancelled. Please install Tesseract and run setup again.")
            sys.exit(1)
    else:
        # Test language support
        if not test_tesseract_languages():
            print("\n⚠️  Some language packs are missing")
            print("   OCR may not work properly for all Swiss languages")
            
            response = input("Continue anyway? (y/N): ").lower()
            if response != 'y':
                print("Setup cancelled. Please install language packs and run setup again.")
                sys.exit(1)
    
    # Create directories
    if not create_directories():
        print("\n❌ Failed to create directories")
        sys.exit(1)
    
    # Create configuration
    if not create_config_file():
        print("\n❌ Failed to create configuration")
        sys.exit(1)
    
    # Test installation
    if not test_installation():
        print("\n❌ Installation test failed")
        print("   Please check error messages above and fix issues")
        sys.exit(1)
    
    # Success!
    show_completion_message()

if __name__ == "__main__":
    main()
