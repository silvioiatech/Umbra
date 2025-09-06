#!/usr/bin/env python3
"""
Swiss Accountant Receipt Processing Example
Demonstrates OCR-based receipt processing with various document types.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime
import tempfile
import json
from io import BytesIO

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import create_swiss_accountant, get_default_config

# Try to import PIL for creating sample receipt images
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  PIL not available - using text-based simulation")

def create_sample_receipt_image(receipt_data: dict, filename: str) -> bool:
    """Create a sample receipt image for testing OCR."""
    if not PIL_AVAILABLE:
        return False
    
    try:
        # Create a white background image
        width, height = 400, 600
        image = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(image)
        
        # Try to use a default font, fallback to basic if not available
        try:
            font_large = ImageFont.truetype("Arial.ttf", 16)
            font_medium = ImageFont.truetype("Arial.ttf", 12)
            font_small = ImageFont.truetype("Arial.ttf", 10)
        except OSError:
            # Fallback to default font
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        y_pos = 20
        
        # Header
        draw.text((20, y_pos), receipt_data['merchant'], fill='black', font=font_large)
        y_pos += 30
        
        draw.text((20, y_pos), receipt_data['address'], fill='black', font=font_small)
        y_pos += 20
        
        draw.text((20, y_pos), f"VAT: {receipt_data['vat_number']}", fill='black', font=font_small)
        y_pos += 40
        
        # Items
        draw.text((20, y_pos), "ITEMS:", fill='black', font=font_medium)
        y_pos += 25
        
        total = 0
        for item in receipt_data['items']:
            item_line = f"{item['name']:<20} CHF {item['price']:>6.2f}"
            draw.text((20, y_pos), item_line, fill='black', font=font_small)
            y_pos += 18
            total += item['price']
        
        y_pos += 20
        
        # Totals
        draw.text((20, y_pos), f"Subtotal:                CHF {total:>6.2f}", fill='black', font=font_small)
        y_pos += 18
        
        vat_amount = total * receipt_data['vat_rate'] / 100
        draw.text((20, y_pos), f"VAT {receipt_data['vat_rate']}%:                  CHF {vat_amount:>6.2f}", fill='black', font=font_small)
        y_pos += 18
        
        total_with_vat = total + vat_amount
        draw.text((20, y_pos), f"TOTAL:                   CHF {total_with_vat:>6.2f}", fill='black', font=font_medium)
        y_pos += 30
        
        # Footer
        draw.text((20, y_pos), f"Date: {receipt_data['date']}", fill='black', font=font_small)
        y_pos += 18
        draw.text((20, y_pos), f"Payment: {receipt_data['payment_method']}", fill='black', font=font_small)
        y_pos += 18
        draw.text((20, y_pos), f"Receipt #: {receipt_data['receipt_number']}", fill='black', font=font_small)
        
        # Save the image
        image.save(filename)
        return True
        
    except Exception as e:
        print(f"Failed to create sample receipt image: {e}")
        return False

def receipt_processing_example():
    """Demonstrate receipt processing with various document types."""
    print("🧾 Swiss Accountant - Receipt Processing Example")
    print("=" * 60)
    
    # Configuration
    config = get_default_config()
    config.update({
        'canton': 'ZH',
        'log_level': 'INFO',
        'ocr_confidence_threshold': 0.7
    })
    
    # Initialize with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize Swiss Accountant
        print("\n📱 Initialize Swiss Accountant")
        print("-" * 40)
        
        sa = create_swiss_accountant(
            db_path=db_path,
            user_id="receipt_demo_user",
            config=config
        )
        print("✅ Swiss Accountant initialized for receipt processing")
        
        # Sample receipt data for different scenarios
        sample_receipts = [
            {
                'type': 'grocery_receipt',
                'merchant': 'Migros Basel',
                'address': 'Bahnhofstrasse 1, 4001 Basel',
                'vat_number': 'CHE-116.281.277',
                'date': '15.01.2024',
                'payment_method': 'Maestro Card',
                'receipt_number': 'R2024011500123',
                'vat_rate': 2.6,
                'items': [
                    {'name': 'Brot Vollkorn', 'price': 3.20},
                    {'name': 'Milch 1L', 'price': 1.85},
                    {'name': 'Bananen 1kg', 'price': 2.95},
                    {'name': 'Käse Gruyère', 'price': 8.40},
                    {'name': 'Joghurt Natural', 'price': 2.10}
                ]
            },
            {
                'type': 'transport_receipt',
                'merchant': 'SBB CFF FFS',
                'address': 'Bahnhof Zürich HB, 8001 Zürich',
                'vat_number': 'CHE-116.169.445',
                'date': '10.01.2024',
                'payment_method': 'SwissPass',
                'receipt_number': 'T2024011000456',
                'vat_rate': 8.1,
                'items': [
                    {'name': 'Tageskarte Zonen 110-121', 'price': 24.00}
                ]
            },
            {
                'type': 'business_equipment',
                'merchant': 'Apple Store Zurich',
                'address': 'Bahnhofstrasse 77, 8001 Zürich',
                'vat_number': 'CHE-116.281.053',
                'date': '08.01.2024',
                'payment_method': 'Credit Card',
                'receipt_number': 'AP2024010800789',
                'vat_rate': 8.1,
                'items': [
                    {'name': 'MacBook Air M3 15"', 'price': 1599.00},
                    {'name': 'USB-C Adapter', 'price': 69.00}
                ]
            },
            {
                'type': 'restaurant_business',
                'merchant': 'Restaurant Kronenhalle',
                'address': 'Rämistrasse 4, 8001 Zürich',
                'vat_number': 'CHE-123.456.789',
                'date': '12.01.2024',
                'payment_method': 'Cash',
                'receipt_number': 'RK2024011200234',
                'vat_rate': 8.1,
                'items': [
                    {'name': 'Business Lunch Menu', 'price': 45.00},
                    {'name': 'Mineralwasser', 'price': 4.50},
                    {'name': 'Espresso', 'price': 4.00}
                ]
            }
        ]
        
        print(f"\n🧾 Processing {len(sample_receipts)} Sample Receipts")
        print("-" * 40)
        
        processed_receipts = []
        
        for i, receipt_data in enumerate(sample_receipts):
            print(f"\n📋 Receipt {i+1}: {receipt_data['merchant']} ({receipt_data['type']})")
            
            # Create sample receipt image (if PIL available)
            receipt_filename = f"sample_receipt_{i+1}.png"
            image_created = False
            
            if PIL_AVAILABLE:
                image_created = create_sample_receipt_image(receipt_data, receipt_filename)
                if image_created:
                    print(f"   ✅ Created sample receipt image: {receipt_filename}")
                else:
                    print(f"   ⚠️  Failed to create receipt image, using simulation")
            
            # Simulate OCR text extraction (in real usage, this would come from pytesseract)
            ocr_text = generate_simulated_ocr_text(receipt_data)
            
            # Process using document parser
            print(f"   🔍 Analyzing document content...")
            
            # Detect document type
            detection_result = sa.document_parser.detect_document_type(ocr_text, receipt_filename)
            print(f"   📄 Document type: {detection_result['document_type'].value} (confidence: {detection_result['confidence']:.2f})")
            
            # Parse receipt content
            if detection_result['document_type'].value == 'receipt':
                parse_result = sa.document_parser.parse_receipt(ocr_text)
            else:
                # Use common field extraction
                common_fields = sa.document_parser.extract_common_fields(ocr_text)
                parse_result = {
                    'document_type': detection_result['document_type'].value,
                    'merchant': common_fields['merchants'][0]['name'] if common_fields['merchants'] else None,
                    'date': common_fields['dates'][0]['date'] if common_fields['dates'] else None,
                    'total_amount': common_fields['amounts'][-1]['value'] if common_fields['amounts'] else None,
                    'confidence': 0.7
                }
            
            print(f"   💰 Extracted amount: CHF {parse_result.get('total_amount', 0):.2f}")
            print(f"   🏪 Detected merchant: {parse_result.get('merchant', 'Unknown')}")
            print(f"   📅 Transaction date: {parse_result.get('date', 'Unknown')}")
            
            # Normalize merchant name
            merchant_result = sa.merchant_normalizer.normalize_merchant_name(
                parse_result.get('merchant', receipt_data['merchant'])
            )
            print(f"   🏷️  Normalized merchant: {merchant_result.get('canonical', 'Unknown')}")
            print(f"      Confidence: {merchant_result.get('confidence', 0):.2f}")
            
            # Map to tax category
            category_result = sa.category_mapper.map_expense_to_deduction_category(
                expense_category=receipt_data['type'],
                merchant_name=merchant_result.get('canonical'),
                description=ocr_text[:200],
                amount=parse_result.get('total_amount', 0),
                date=datetime.strptime(receipt_data['date'], '%d.%m.%Y').date()
            )
            
            print(f"   📊 Tax category: {category_result.get('deduction_category')}")
            print(f"      Applicable: {category_result.get('applicable', False)}")
            print(f"      Confidence: {category_result.get('confidence', 0):.2f}")
            
            # Determine business percentage based on type
            business_percentage = {
                'grocery_receipt': 0,
                'transport_receipt': 100,  # Assume commuting
                'business_equipment': 80,  # Mixed business/personal use
                'restaurant_business': 100  # Business meal
            }.get(receipt_data['type'], 0)
            
            # Calculate amounts
            total_amount = parse_result.get('total_amount', 0)
            business_amount = total_amount * business_percentage / 100
            
            print(f"   💼 Business percentage: {business_percentage}%")
            print(f"   💰 Business amount: CHF {business_amount:.2f}")
            
            # Store in database
            expense_id = sa.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, date_local, merchant_text, merchant_id,
                    amount_cents, currency, category_code, pro_pct,
                    notes, payment_method, vat_breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "receipt_demo_user",
                receipt_data['date'].replace('.', '-')[:10] if '.' in receipt_data['date'] else receipt_data['date'],
                parse_result.get('merchant', receipt_data['merchant']),
                merchant_result.get('merchant_id'),
                int(total_amount * 100),
                'CHF',
                category_result.get('deduction_category', 'other_deductions'),
                business_percentage,
                f"Processed from {receipt_filename}. Items: {len(receipt_data['items'])}",
                receipt_data['payment_method'],
                json.dumps({
                    'rate': receipt_data['vat_rate'],
                    'amount': total_amount * receipt_data['vat_rate'] / (100 + receipt_data['vat_rate'])
                })
            ))
            
            print(f"   ✅ Stored as expense ID: {expense_id}")
            
            processed_receipts.append({
                'expense_id': expense_id,
                'receipt_data': receipt_data,
                'parse_result': parse_result,
                'merchant_result': merchant_result,
                'category_result': category_result,
                'business_amount': business_amount,
                'image_file': receipt_filename if image_created else None
            })
            
            # Cleanup image file
            if image_created and os.path.exists(receipt_filename):
                os.unlink(receipt_filename)
        
        # Summary of processed receipts
        print(f"\n📊 Processing Summary")
        print("-" * 40)
        
        total_processed = len(processed_receipts)
        total_amount = sum(r['receipt_data']['items'][0]['price'] * len(r['receipt_data']['items']) 
                          for r in processed_receipts 
                          if r['receipt_data']['items'])
        total_business = sum(r['business_amount'] for r in processed_receipts)
        
        print(f"✅ Successfully processed {total_processed} receipts")
        print(f"💰 Total amount: CHF {total_amount:.2f}")
        print(f"💼 Business amount: CHF {total_business:.2f}")
        print(f"🧮 Personal amount: CHF {total_amount - total_business:.2f}")
        
        # Category breakdown
        print(f"\n📈 Category Breakdown:")
        categories = {}
        for receipt in processed_receipts:
            category = receipt['category_result'].get('deduction_category', 'other')
            amount = receipt['business_amount'] if receipt['business_amount'] > 0 else sum(item['price'] for item in receipt['receipt_data']['items'])
            categories[category] = categories.get(category, 0) + amount
        
        for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"   {category:<25}: CHF {amount:>8.2f}")
        
        # Test retrieval and dashboard
        print(f"\n📋 Retrieved Expenses")
        print("-" * 40)
        
        expenses = sa.get_expenses(limit=10)
        for expense in expenses:
            business_marker = "💼" if expense['pro_pct'] > 0 else "👤"
            print(f"   {business_marker} {expense['merchant_text']:<25} CHF {expense['amount_chf']:>8.2f} ({expense['category_code']})")
        
        print(f"\n🎉 Receipt Processing Complete!")
        print("=" * 60)
        print(f"✅ All receipts processed and categorized")
        print(f"✅ Merchants normalized and stored")
        print(f"✅ Tax categories automatically assigned")
        print(f"✅ Business percentages applied")
        print(f"✅ Data ready for reconciliation and export")
        
        print(f"\n💡 In real usage:")
        print(f"   1. Place receipt images in a folder")
        print(f"   2. Use: sa.process_receipt(image_path)")
        print(f"   3. Review and adjust business percentages")
        print(f"   4. Reconcile with bank statements")
        print(f"   5. Export for tax preparation")
        
        return True
        
    except Exception as e:
        print(f"❌ Receipt processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"\n🧹 Cleaned up demo database")
        except:
            pass

def generate_simulated_ocr_text(receipt_data: dict) -> str:
    """Generate simulated OCR text for testing document parser."""
    items_text = "\n".join([f"{item['name']} CHF {item['price']:.2f}" 
                           for item in receipt_data['items']])
    
    total_without_vat = sum(item['price'] for item in receipt_data['items'])
    vat_amount = total_without_vat * receipt_data['vat_rate'] / 100
    total_with_vat = total_without_vat + vat_amount
    
    ocr_text = f"""
{receipt_data['merchant']}
{receipt_data['address']}
MWST-Nr: {receipt_data['vat_number']}

QUITTUNG / RECEIPT

{items_text}

Zwischensumme: CHF {total_without_vat:.2f}
MWST {receipt_data['vat_rate']}%: CHF {vat_amount:.2f}
TOTAL: CHF {total_with_vat:.2f}

Bezahlung: {receipt_data['payment_method']}
Datum: {receipt_data['date']}
Beleg-Nr: {receipt_data['receipt_number']}

Vielen Dank für Ihren Einkauf!
""".strip()
    
    return ocr_text

if __name__ == "__main__":
    success = receipt_processing_example()
    sys.exit(0 if success else 1)
