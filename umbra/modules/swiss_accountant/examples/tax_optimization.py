#!/usr/bin/env python3
"""
Swiss Accountant Tax Optimization Example
Demonstrates Swiss tax deduction calculation and optimization strategies.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime
import tempfile
import json

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import create_swiss_accountant, get_default_config

def tax_optimization_example():
    """Demonstrate Swiss tax optimization and deduction calculation."""
    print("🧮 Swiss Accountant - Tax Optimization Example")
    print("=" * 60)
    
    # Configuration for Zurich canton
    config = get_default_config()
    config.update({
        'canton': 'ZH',
        'log_level': 'INFO'
    })
    
    # Initialize with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize Swiss Accountant
        print("\n📱 Initialize Swiss Accountant for Tax Year 2024")
        print("-" * 45)
        
        sa = create_swiss_accountant(
            db_path=db_path,
            user_id="tax_demo_user",
            config=config
        )
        print("✅ Swiss Accountant initialized")
        print("📍 Canton: Zurich (ZH)")
        print("📅 Tax Year: 2024")
        
        # Step 1: Create comprehensive sample data for a full tax year
        print("\n💰 Step 1: Create Sample Tax Year Data")
        print("-" * 45)
        
        # Professional expenses - equipment, software, books
        professional_expenses = [
            {
                'date': '2024-01-10',
                'merchant': 'Apple Store Zurich',
                'amount': 2499.00,
                'category': 'professional_equipment',
                'description': 'MacBook Pro M3 for work',
                'business_pct': 85,
                'deduction_category': 'professional_expenses'
            },
            {
                'date': '2024-02-15',
                'merchant': 'Adobe Switzerland',
                'amount': 599.88,
                'category': 'professional_software',
                'description': 'Creative Suite annual license',
                'business_pct': 100,
                'deduction_category': 'professional_expenses'
            },
            {
                'date': '2024-03-20',
                'merchant': 'Orell Füssli Thalia AG',
                'amount': 285.50,
                'category': 'professional_books',
                'description': 'Technical books and manuals',
                'business_pct': 100,
                'deduction_category': 'professional_expenses'
            },
            {
                'date': '2024-04-05',
                'merchant': 'IKEA Switzerland',
                'amount': 450.00,
                'category': 'home_office',
                'description': 'Office desk and chair',
                'business_pct': 80,
                'deduction_category': 'home_office'
            }
        ]
        
        # Commuting expenses - public transport
        commuting_expenses = [
            {
                'date': '2024-01-01',
                'merchant': 'SBB CFF FFS',
                'amount': 1380.00,
                'category': 'public_transport',
                'description': 'Annual GA Travelcard',
                'business_pct': 100,
                'deduction_category': 'commute_public_transport'
            },
            {
                'date': '2024-06-15',
                'merchant': 'VBZ Zurich',
                'amount': 155.00,
                'category': 'public_transport',
                'description': 'Monthly zone pass',
                'business_pct': 100,
                'deduction_category': 'commute_public_transport'
            }
        ]
        
        # Education and training
        education_expenses = [
            {
                'date': '2024-03-01',
                'merchant': 'University of Zurich',
                'amount': 2500.00,
                'category': 'professional_education',
                'description': 'Executive MBA course',
                'business_pct': 100,
                'deduction_category': 'education_professional'
            },
            {
                'date': '2024-05-10',
                'merchant': 'Coursera Switzerland',
                'amount': 349.00,
                'category': 'online_training',
                'description': 'Professional certification courses',
                'business_pct': 100,
                'deduction_category': 'education_professional'
            }
        ]
        
        # Insurance and pillar 3a
        insurance_expenses = [
            {
                'date': '2024-01-31',
                'merchant': 'Swiss Life AG',
                'amount': 7056.00,
                'category': 'pillar_3a',
                'description': 'Maximum pillar 3a contribution',
                'business_pct': 0,
                'deduction_category': 'insurance_pillar3a'
            },
            {
                'date': '2024-02-28',
                'merchant': 'CSS Insurance',
                'amount': 4800.00,
                'category': 'health_insurance',
                'description': 'Annual health insurance premium',
                'business_pct': 0,
                'deduction_category': 'insurance_health'
            }
        ]
        
        # Business meals and entertainment
        meal_expenses = [
            {
                'date': '2024-02-14',
                'merchant': 'Restaurant Kronenhalle',
                'amount': 145.00,
                'category': 'business_meals',
                'description': 'Client lunch meeting',
                'business_pct': 100,
                'deduction_category': 'meals_work'
            },
            {
                'date': '2024-04-20',
                'merchant': 'Hotel Baur au Lac',
                'amount': 89.50,
                'category': 'business_meals',
                'description': 'Business dinner with partners',
                'business_pct': 100,
                'deduction_category': 'meals_work'
            }
        ]
        
        # Childcare expenses
        childcare_expenses = [
            {
                'date': '2024-01-15',
                'merchant': 'Kita Zürich Zentrum',
                'amount': 18000.00,
                'category': 'childcare',
                'description': 'Annual daycare fees',
                'business_pct': 0,
                'deduction_category': 'childcare'
            }
        ]
        
        # Medical expenses
        medical_expenses = [
            {
                'date': '2024-06-10',
                'merchant': 'Praxis Dr. Mueller',
                'amount': 1250.00,
                'category': 'medical',
                'description': 'Dental treatment not covered by insurance',
                'business_pct': 0,
                'deduction_category': 'medical_expenses'
            }
        ]
        
        # Charitable donations
        donation_expenses = [
            {
                'date': '2024-12-15',
                'merchant': 'Rotes Kreuz Schweiz',
                'amount': 500.00,
                'category': 'donations',
                'description': 'Annual charitable donation',
                'business_pct': 0,
                'deduction_category': 'donations_charitable'
            }
        ]
        
        # Personal expenses (non-deductible)
        personal_expenses = [
            {
                'date': '2024-01-20',
                'merchant': 'Migros Zurich',
                'amount': 2400.00,
                'category': 'groceries',
                'description': 'Annual grocery expenses',
                'business_pct': 0,
                'deduction_category': 'non_deductible'
            },
            {
                'date': '2024-07-15',
                'merchant': 'Swiss International Air Lines',
                'amount': 1200.00,
                'category': 'vacation',
                'description': 'Personal vacation flights',
                'business_pct': 0,
                'deduction_category': 'non_deductible'
            }
        ]
        
        # Combine all expenses
        all_expenses = (professional_expenses + commuting_expenses + education_expenses + 
                       insurance_expenses + meal_expenses + childcare_expenses + 
                       medical_expenses + donation_expenses + personal_expenses)
        
        # Store expenses in database
        expense_ids = []
        category_totals = {}
        
        print(f"   💾 Storing {len(all_expenses)} expenses for tax year 2024...")
        
        for expense in all_expenses:
            expense_id = sa.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, date_local, merchant_text, amount_cents,
                    currency, category_code, pro_pct, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "tax_demo_user",
                expense['date'],
                expense['merchant'],
                int(expense['amount'] * 100),
                'CHF',
                expense['category'],
                expense['business_pct'],
                expense['description']
            ))
            expense_ids.append(expense_id)
            
            # Track category totals
            deduction_cat = expense['deduction_category']
            if deduction_cat not in category_totals:
                category_totals[deduction_cat] = {'total': 0, 'deductible': 0, 'count': 0}
            
            category_totals[deduction_cat]['total'] += expense['amount']
            category_totals[deduction_cat]['count'] += 1
            
            if expense['business_pct'] > 0:
                category_totals[deduction_cat]['deductible'] += expense['amount'] * expense['business_pct'] / 100
            elif deduction_cat != 'non_deductible':
                category_totals[deduction_cat]['deductible'] += expense['amount']
        
        print(f"   ✅ Created {len(expense_ids)} expenses")
        
        # Show category overview
        print(f"\n   📊 Expense Categories Overview:")
        for category, totals in sorted(category_totals.items()):
            deductible_pct = (totals['deductible'] / totals['total'] * 100) if totals['total'] > 0 else 0
            print(f"      {category:<25}: CHF {totals['total']:>8,.2f} (CHF {totals['deductible']:>8,.2f} deductible, {deductible_pct:.0f}%)")
        
        # Step 2: Calculate tax deductions
        print(f"\n🧮 Step 2: Calculate Swiss Tax Deductions")
        print("-" * 45)
        
        tax_result = sa.calculate_tax_deductions(year=2024, canton="ZH")
        
        if tax_result.get('success'):
            print(f"   ✅ Tax calculation completed for Canton Zurich")
            print(f"   📊 Overall Summary:")
            print(f"      Total expenses: CHF {tax_result['total_expenses']:>12,.2f}")
            print(f"      Total deductible: CHF {tax_result['total_deductible']:>12,.2f}")
            print(f"      Estimated tax savings: CHF {tax_result['estimated_tax_savings']:>12,.2f}")
            print(f"      Number of expenses: {tax_result['expense_count']:>15,}")
            
            # Detailed category breakdown
            print(f"\n   📈 Swiss Tax Deduction Categories:")
            deduction_total = 0
            
            for category, data in tax_result['deductions_by_category'].items():
                if data['deductible_amount'] > 0:
                    print(f"      {category:<30}: CHF {data['deductible_amount']:>10,.2f} ({data['expense_count']:>2} items)")
                    deduction_total += data['deductible_amount']
            
            print(f"      {'-'*30}   {'-'*15}")
            print(f"      {'TOTAL DEDUCTIONS':<30}: CHF {deduction_total:>10,.2f}")
            
        else:
            print(f"   ❌ Tax calculation failed: {tax_result.get('error')}")
        
        # Step 3: Analyze optimization opportunities
        print(f"\n💡 Step 3: Tax Optimization Analysis")
        print("-" * 45)
        
        print(f"   🎯 Deduction Limits and Optimization:")
        
        # Professional expenses analysis
        prof_expenses = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                           if cat == 'professional_expenses')
        flat_rate_limit = 4000  # CHF standard deduction
        
        print(f"\n   💼 Professional Expenses:")
        print(f"      Current deductions: CHF {prof_expenses:>8,.2f}")
        print(f"      Flat rate option: CHF {flat_rate_limit:>8,.2f}")
        if prof_expenses > flat_rate_limit:
            print(f"      ✅ Itemized deduction is CHF {prof_expenses - flat_rate_limit:,.2f} better than flat rate")
            print(f"      💡 Keep detailed records and receipts for audit")
        else:
            print(f"      ⚠️  Flat rate deduction would be CHF {flat_rate_limit - prof_expenses:,.2f} better")
            print(f"      💡 Consider additional professional expenses or use flat rate")
        
        # Commuting analysis
        commute_expenses = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                              if cat == 'commute_public_transport')
        commute_limit = 3000  # CHF federal limit
        
        print(f"\n   🚊 Commuting Expenses:")
        print(f"      Current deductions: CHF {commute_expenses:>8,.2f}")
        print(f"      Federal limit: CHF {commute_limit:>8,.2f}")
        if commute_expenses <= commute_limit:
            print(f"      ✅ Within federal limits")
            remaining_commute = commute_limit - commute_expenses
            if remaining_commute > 0:
                print(f"      💡 Could claim additional CHF {remaining_commute:,.2f} in commuting costs")
        else:
            print(f"      ⚠️  Exceeds federal limit by CHF {commute_expenses - commute_limit:,.2f}")
            print(f"      💡 Only CHF {commute_limit:,.2f} will be deductible")
        
        # Pillar 3a analysis
        pillar3a_expenses = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                               if cat == 'insurance_pillar3a')
        pillar3a_limit = 7056  # CHF maximum for employed persons
        
        print(f"\n   🏛️  Pillar 3a Contributions:")
        print(f"      Current contributions: CHF {pillar3a_expenses:>8,.2f}")
        print(f"      Maximum limit: CHF {pillar3a_limit:>8,.2f}")
        if pillar3a_expenses >= pillar3a_limit:
            print(f"      ✅ Maximum contribution achieved - optimal tax benefit")
        else:
            additional_3a = pillar3a_limit - pillar3a_expenses
            tax_savings_3a = additional_3a * 0.25  # Approximate tax rate
            print(f"      💡 Could contribute additional CHF {additional_3a:,.2f}")
            print(f"      💰 Potential additional tax savings: CHF {tax_savings_3a:,.2f}")
        
        # Childcare analysis
        childcare_expenses = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                                if cat == 'childcare')
        childcare_limit = 25000  # CHF per child federal limit
        
        print(f"\n   👶 Childcare Expenses:")
        print(f"      Current deductions: CHF {childcare_expenses:>8,.2f}")
        print(f"      Limit per child: CHF {childcare_limit:>8,.2f}")
        if childcare_expenses <= childcare_limit:
            print(f"      ✅ Within limits")
            if childcare_expenses > 0:
                print(f"      💡 Excellent deduction - high tax impact")
        else:
            print(f"      ⚠️  May exceed per-child limits")
        
        # Medical expenses analysis
        medical_expenses_total = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                                   if cat == 'medical_expenses')
        medical_threshold = 0.05  # 5% of net income threshold
        
        print(f"\n   🏥 Medical Expenses:")
        print(f"      Current medical costs: CHF {medical_expenses_total:>8,.2f}")
        print(f"      💡 Only amounts exceeding 5% of net income are deductible")
        print(f"      💡 Consider timing of elective medical procedures")
        
        # Step 4: Generate optimization recommendations
        print(f"\n🚀 Step 4: Optimization Recommendations")
        print("-" * 45)
        
        recommendations = []
        
        # Professional expenses recommendation
        if prof_expenses < flat_rate_limit:
            shortage = flat_rate_limit - prof_expenses
            recommendations.append({
                'category': 'Professional Expenses',
                'priority': 'High',
                'action': f'Add CHF {shortage:,.2f} in professional expenses or use flat rate',
                'impact': f'CHF {shortage * 0.25:,.2f} tax savings'
            })
        
        # Pillar 3a recommendation
        if pillar3a_expenses < pillar3a_limit:
            additional_3a = pillar3a_limit - pillar3a_expenses
            recommendations.append({
                'category': 'Pillar 3a',
                'priority': 'High',
                'action': f'Increase pillar 3a contributions by CHF {additional_3a:,.2f}',
                'impact': f'CHF {additional_3a * 0.25:,.2f} tax savings'
            })
        
        # Home office recommendation
        home_office_expenses = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                                  if cat == 'home_office')
        home_office_limit = 1500  # CHF typical canton limit
        if home_office_expenses < home_office_limit:
            additional_ho = home_office_limit - home_office_expenses
            recommendations.append({
                'category': 'Home Office',
                'priority': 'Medium',
                'action': f'Claim additional CHF {additional_ho:,.2f} in home office costs',
                'impact': f'CHF {additional_ho * 0.25:,.2f} tax savings'
            })
        
        # Education recommendation
        education_total = sum(data['deductible_amount'] for cat, data in tax_result['deductions_by_category'].items() 
                             if cat == 'education_professional')
        if education_total > 0:
            recommendations.append({
                'category': 'Education',
                'priority': 'Medium',
                'action': 'Continue professional development - excellent deduction',
                'impact': f'Current CHF {education_total * 0.25:,.2f} tax savings'
            })
        
        print(f"   🎯 Priority Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            priority_emoji = "🔴" if rec['priority'] == 'High' else "🟡"
            print(f"\n      {priority_emoji} Recommendation {i}: {rec['category']}")
            print(f"         Action: {rec['action']}")
            print(f"         Impact: {rec['impact']}")
        
        # Step 5: Generate tax export
        print(f"\n📤 Step 5: Generate Tax Export")
        print("-" * 45)
        
        # Export tax data
        export_result = sa.export_tax_data(year=2024, format='xlsx', canton='ZH')
        
        if export_result['success']:
            print(f"   ✅ Tax export generated successfully:")
            print(f"      Format: Excel (.xlsx)")
            print(f"      Records: {export_result['record_count']:,}")
            print(f"      Size: {export_result['size_bytes']:,} bytes")
            print(f"      Canton: Zurich (ZH)")
            
            # Save export file
            export_filename = f"tax_export_2024_zh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            with open(export_filename, 'wb') as f:
                f.write(export_result['content'])
            print(f"      Saved to: {export_filename}")
            
            print(f"\n   📋 Export includes:")
            print(f"      • All deductible expenses with categories")
            print(f"      • Business percentage calculations")
            print(f"      • VAT breakdown where applicable")
            print(f"      • Receipt references and notes")
            print(f"      • Canton-specific formatting")
        
        else:
            print(f"   ❌ Export failed: {export_result.get('error')}")
        
        # Summary
        print(f"\n🎉 Tax Optimization Complete!")
        print("=" * 60)
        print(f"✅ Comprehensive tax year analysis completed")
        print(f"✅ Swiss federal and cantonal rules applied")
        print(f"✅ Optimization opportunities identified")
        print(f"✅ Tax-ready export generated")
        
        total_deductible = tax_result.get('total_deductible', 0)
        estimated_savings = tax_result.get('estimated_tax_savings', 0)
        
        print(f"\n📊 Final Tax Summary:")
        print(f"   💰 Total deductible amount: CHF {total_deductible:>12,.2f}")
        print(f"   💵 Estimated tax savings: CHF {estimated_savings:>12,.2f}")
        print(f"   📈 Effective deduction rate: {(total_deductible / tax_result.get('total_expenses', 1) * 100):>8.1f}%")
        
        print(f"\n💡 Next Steps:")
        print(f"   1. Implement high-priority recommendations")
        print(f"   2. Set up recurring pillar 3a contributions")
        print(f"   3. Keep detailed records for professional expenses")
        print(f"   4. Review and update throughout the year")
        print(f"   5. Consult tax advisor for complex situations")
        
        return True
        
    except Exception as e:
        print(f"❌ Tax optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            # Clean up export files
            import glob
            for file in glob.glob("tax_export_*.xlsx"):
                if os.path.exists(file):
                    os.unlink(file)
            
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"\n🧹 Cleaned up demo files and database")
        except:
            pass

if __name__ == "__main__":
    success = tax_optimization_example()
    sys.exit(0 if success else 1)
