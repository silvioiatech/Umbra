"""
BOT2 Demo - Showcase the enhanced status command capabilities.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_header():
    """Print demo header."""
    print("🎯" + "="*60)
    print("🤖 UMBRA BOT2 - Enhanced Status Command Demo")
    print("🎯" + "="*60)
    print()
    print("BOT2 adds comprehensive health monitoring:")
    print("• 🔍 Per-service health checks")
    print("• ⚡ Time-boxed parallel execution")
    print("• 🔧 Admin verbose diagnostics")
    print("• 🛡️ Secret-safe reporting")
    print("• 📊 Visual status dashboard")
    print()

def print_basic_status_demo():
    """Show what the basic status looks like."""
    print("📊 BASIC STATUS COMMAND DEMO")
    print("-" * 40)
    print()
    print("🤖 **Umbra Bot Status Dashboard**")
    print()
    print("**🔧 Core Services:**")
    print("🟢 Telegram: active 🟢")
    print("🟢 Openrouter: active 🟢")
    print("🟡 R2 Storage: degraded ⚪")
    print("🟢 Database: active 🟢")
    print()
    print("**⚙️ System Components:**")
    print("🟢 Modules: All 5 modules active")
    print("🟢 Rate Limiter: Active, 3 users tracked")
    print("🟢 Permissions: 2 users, 1 admins")
    print()
    print("🟢 **Overall: Healthy** (6/7 services active)")
    print()
    print("**📊 Bot Info:**")
    print("• Mode: F3R1 (OpenRouter + Tools)")
    print("• Uptime: 2h 15m")
    print("• Environment: production")
    print("• Locale: Europe/Zurich")
    print()
    print("_Use_ `/status verbose` _for detailed diagnostics._")
    print()

def print_verbose_status_demo():
    """Show what the verbose status looks like."""
    print("🔍 VERBOSE STATUS COMMAND DEMO (Admin Only)")
    print("-" * 40)
    print()
    print("🤖 **Umbra Bot Status Dashboard**")
    print()
    print("**🔧 Core Services:**")
    print("🟢 Telegram: active 🟢")
    print("   ↳ Bot token configured and ready")
    print("🟢 Openrouter: active 🟢")  
    print("   ↳ Connected, model: anthropic/claude-3.5-sonnet:beta")
    print("🟡 R2 Storage: degraded ⚪")
    print("   ↳ R2 credentials not fully configured")
    print("🟢 Database: active 🟢")
    print("   ↳ SQLite database responding (2.1ms)")
    print()
    print("**⚙️ System Components:**")
    print("🟢 Modules: All 5 modules active")
    print("🟢 Rate Limiter: Active, 3 users tracked")
    print("🟢 Permissions: 2 users, 1 admins")
    print()
    print("**🔍 Detailed Diagnostics:**")
    print("🟢 System Resources: Healthy: CPU 15.2%, RAM 34.8%, Disk 12.1%")
    print("   ↳ Response time: 112.3ms")
    print("🟢 Network: Internet connectivity OK (89.2ms)")
    print("   ↳ Response time: 89.2ms")
    print("🟡 Configuration: Basic config only, no optional features")
    print("   ↳ Response time: 1.1ms")
    print()
    print("🟡 **Overall: Partial** (8/10 services active)")
    print()
    print("**📊 Bot Info:**")
    print("• Mode: F3R1 (OpenRouter + Tools)")
    print("• Uptime: 2h 15m")
    print("• Environment: production")
    print("• Locale: Europe/Zurich")
    print()
    print("_Detailed diagnostics mode active._")
    print()

def print_health_architecture():
    """Show the health checking architecture."""
    print("🏗️ HEALTH CHECKING ARCHITECTURE")
    print("-" * 40)
    print()
    print("📦 **Core Services (Always Checked):**")
    print("   🔸 Telegram - Bot token & API connectivity")
    print("   🔸 OpenRouter - AI provider availability")  
    print("   🔸 R2 Storage - Cloudflare R2 configuration")
    print("   🔸 Database - SQLite performance & connectivity")
    print()
    print("⚙️ **System Components (Always Checked):**")
    print("   🔸 Modules - Registry status & module health")
    print("   🔸 Rate Limiter - Active user tracking")
    print("   🔸 Permissions - User & admin configuration")
    print()
    print("🔍 **Verbose Diagnostics (Admin Only):**")
    print("   🔸 System Resources - CPU, RAM, Disk usage")
    print("   🔸 Network - Internet connectivity test")
    print("   🔸 Configuration - Completeness assessment")
    print()
    print("⚡ **Performance Features:**")
    print("   🔸 Parallel execution (all checks run simultaneously)")
    print("   🔸 Time-boxed (1.5s per check, 10s total timeout)")
    print("   🔸 Graceful degradation (partial results on timeout)")
    print("   🔸 Secret-safe (no credential leakage)")
    print()

def print_status_states():
    """Show the different status states."""
    print("🎨 STATUS STATES & EMOJIS")
    print("-" * 40)
    print()
    print("🟢 **ACTIVE** - Service is working normally")
    print("   • All checks passed")
    print("   • Response times within normal range")
    print("   • No errors detected")
    print()
    print("🟡 **DEGRADED** - Service has issues but still functional")
    print("   • Some checks failed or slow")
    print("   • Service partially available")
    print("   • Performance issues detected")
    print()
    print("⚪ **INACTIVE** - Service is disabled or not configured")
    print("   • Required configuration missing")
    print("   • Service intentionally disabled")
    print("   • Not a system error")
    print()
    print("🔴 **ERROR** - Service has critical issues")
    print("   • Health checks failed with errors")
    print("   • Service unreachable or broken")
    print("   • Immediate attention required")
    print()
    print("❓ **UNKNOWN** - Status could not be determined")
    print("   • Health checks timed out")
    print("   • Unexpected errors during checking")
    print("   • Need manual investigation")
    print()

def print_usage_examples():
    """Show usage examples."""
    print("🚀 USAGE EXAMPLES")
    print("-" * 40)
    print()
    print("💬 **In Telegram Chat:**")
    print()
    print("1️⃣ Basic Status Check:")
    print("   User: /status")
    print("   Bot: [Shows core services + system components]")
    print()
    print("2️⃣ Verbose Diagnostics (Admin Only):")
    print("   Admin: /status verbose")
    print("   Bot: [Shows everything + detailed diagnostics]")
    print()
    print("3️⃣ Non-Admin Verbose Attempt:")
    print("   User: /status verbose")
    print("   Bot: [Shows basic status + 'Admin users can access verbose diagnostics']")
    print()
    print("🎯 **Key Benefits:**")
    print("   ✅ Quick system overview in <3 seconds")
    print("   ✅ Proactive issue detection")
    print("   ✅ Performance monitoring")
    print("   ✅ Configuration validation")
    print("   ✅ Admin-level troubleshooting")
    print()

async def run_live_demo():
    """Run a live demo of the health checker."""
    print("🔥 LIVE HEALTH CHECK DEMO")
    print("-" * 40)
    print()
    print("Running actual health checks...")
    
    try:
        from umbra.core.health import HealthChecker, ServiceStatus
        from umbra.core.config import config
        
        # Create health checker
        health_checker = HealthChecker(config)
        
        print("⏱️ Starting health checks (max 10s timeout)...")
        import time
        start_time = time.time()
        
        # Run basic checks
        results = await health_checker.check_all_services(verbose=False)
        
        duration = time.time() - start_time
        print(f"✅ Completed in {duration:.2f}s")
        print()
        
        # Show results
        print("📊 **Live Results:**")
        for service, result in results.items():
            status_emoji = {
                ServiceStatus.ACTIVE: "🟢",
                ServiceStatus.DEGRADED: "🟡",
                ServiceStatus.INACTIVE: "⚪",
                ServiceStatus.ERROR: "🔴",
                ServiceStatus.UNKNOWN: "❓"
            }.get(result.status, "❓")
            
            print(f"   {status_emoji} {service}: {result.status.value}")
            if result.details:
                print(f"      └─ {result.details}")
        
        # Summary
        active_count = len([r for r in results.values() if r.status == ServiceStatus.ACTIVE])
        total_count = len(results)
        
        print(f"\n📈 **Summary:** {active_count}/{total_count} services active")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("   (This is expected if not in a proper Umbra environment)")

def main():
    """Main demo function."""
    print_header()
    
    print_basic_status_demo()
    print_verbose_status_demo()
    print_health_architecture()
    print_status_states()
    print_usage_examples()
    
    # Ask if user wants live demo
    print("🔥 OPTIONAL: Live Demo")
    print("-" * 40)
    response = input("Run live health check demo? (y/N): ").lower().strip()
    
    if response in ['y', 'yes']:
        print()
        asyncio.run(run_live_demo())
    
    print("\n" + "🎯" + "="*60)
    print("✅ BOT2 Demo Complete!")
    print()
    print("🚀 **Next Steps:**")
    print("   1. Deploy to Railway with OPENROUTER_API_KEY")
    print("   2. Test /status in Telegram")
    print("   3. Test /status verbose as admin")
    print("   4. Monitor system health proactively")
    print()
    print("📋 **What's Next After BOT2:**")
    print("   • C1 - Concierge v0 (core ops)")
    print("   • C3 - Concierge Instances Registry")
    print("   • BUS1 - Business (instance gateway)")
    print("🎯" + "="*60)

if __name__ == "__main__":
    main()
