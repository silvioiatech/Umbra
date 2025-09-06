"""
BOT2 Test Script - Test the enhanced status command functionality.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from umbra.core.config import config
from umbra.core.health import HealthChecker, ServiceStatus

async def test_health_checker():
    """Test the health checker functionality."""
    print("🧪 Testing BOT2 Health Checker...\n")
    
    # Create health checker
    health_checker = HealthChecker(config)
    
    # Test basic health checks
    print("📊 Running basic health checks...")
    basic_results = await health_checker.check_all_services(verbose=False)
    
    print("\n✅ Basic Health Check Results:")
    for service, result in basic_results.items():
        status_emoji = {
            ServiceStatus.ACTIVE: "🟢",
            ServiceStatus.DEGRADED: "🟡",
            ServiceStatus.INACTIVE: "⚪",
            ServiceStatus.ERROR: "🔴",
            ServiceStatus.UNKNOWN: "❓"
        }.get(result.status, "❓")
        
        configured_emoji = "🟢" if result.configured else "⚪"
        
        print(f"  {status_emoji} {service}: {result.status.value} {configured_emoji}")
        print(f"    └─ {result.details}")
        if result.response_time_ms > 0:
            print(f"    └─ Response time: {result.response_time_ms:.1f}ms")
    
    # Test verbose health checks 
    print("\n🔍 Running verbose health checks...")
    verbose_results = await health_checker.check_all_services(verbose=True)
    
    print("\n✅ Verbose Health Check Results:")
    verbose_only_services = set(verbose_results.keys()) - set(basic_results.keys())
    
    for service in verbose_only_services:
        result = verbose_results[service]
        status_emoji = {
            ServiceStatus.ACTIVE: "🟢",
            ServiceStatus.DEGRADED: "🟡",
            ServiceStatus.INACTIVE: "⚪",
            ServiceStatus.ERROR: "🔴",
            ServiceStatus.UNKNOWN: "❓"
        }.get(result.status, "❓")
        
        print(f"  {status_emoji} {service}: {result.status.value}")
        print(f"    └─ {result.details}")
        if result.response_time_ms > 0:
            print(f"    └─ Response time: {result.response_time_ms:.1f}ms")
    
    # Summary
    total_services = len(verbose_results)
    active_services = len([r for r in verbose_results.values() if r.status == ServiceStatus.ACTIVE])
    degraded_services = len([r for r in verbose_results.values() if r.status == ServiceStatus.DEGRADED])
    error_services = len([r for r in verbose_results.values() if r.status in [ServiceStatus.ERROR, ServiceStatus.INACTIVE]])
    
    print(f"\n📈 Summary:")
    print(f"  • Total services checked: {total_services}")
    print(f"  • Active: {active_services}")
    print(f"  • Degraded: {degraded_services}")
    print(f"  • Error/Inactive: {error_services}")
    
    if error_services > 0:
        overall_status = "🔴 System has issues"
    elif degraded_services > 0:
        overall_status = "🟡 System partially degraded"
    else:
        overall_status = "🟢 System healthy"
    
    print(f"  • Overall: {overall_status}")

async def test_configuration_status():
    """Test configuration status reporting."""
    print("\n⚙️ Testing Configuration Status...\n")
    
    print("📋 Current Configuration:")
    print(f"  • Telegram Bot Token: {'✅ Set' if config.TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    print(f"  • Allowed Users: {'✅' if config.ALLOWED_USER_IDS else '❌'} {len(config.ALLOWED_USER_IDS)} users")
    print(f"  • Admin Users: {'✅' if config.ALLOWED_ADMIN_IDS else '❌'} {len(config.ALLOWED_ADMIN_IDS)} admins")
    
    print(f"\n🤖 AI Integration:")
    openrouter_key = getattr(config, 'OPENROUTER_API_KEY', None)
    print(f"  • OpenRouter API Key: {'✅ Set' if openrouter_key else '❌ Missing'}")
    if openrouter_key:
        print(f"  • Default Model: {getattr(config, 'OPENROUTER_DEFAULT_MODEL', 'Not set')}")
    
    print(f"\n☁️ Storage:")
    r2_configured = all([
        getattr(config, 'R2_ACCOUNT_ID', None),
        getattr(config, 'R2_ACCESS_KEY_ID', None),
        getattr(config, 'R2_SECRET_ACCESS_KEY', None),
        getattr(config, 'R2_BUCKET', None)
    ])
    print(f"  • R2 Storage: {'✅ Configured' if r2_configured else '❌ Not configured'}")
    if r2_configured:
        print(f"  • Bucket: {getattr(config, 'R2_BUCKET', 'Not set')}")
    
    print(f"\n🌍 Environment:")
    print(f"  • Environment: {config.ENVIRONMENT}")
    print(f"  • Locale: {config.LOCALE_TZ}")
    print(f"  • Rate Limit: {config.RATE_LIMIT_PER_MIN}/min")

def test_status_emojis():
    """Test status emoji mapping."""
    print("\n🎨 Testing Status Emojis...\n")
    
    from umbra.bot import UmbraBot
    
    # Create a bot instance to test the emoji method
    bot = UmbraBot(config)
    
    print("📊 Status Emoji Mapping:")
    statuses = [
        ServiceStatus.ACTIVE,
        ServiceStatus.DEGRADED,
        ServiceStatus.INACTIVE,
        ServiceStatus.ERROR,
        ServiceStatus.UNKNOWN
    ]
    
    for status in statuses:
        emoji = bot._get_status_emoji(status)
        print(f"  {emoji} {status.value}")

async def main():
    """Main test function."""
    print("🤖 BOT2 - Enhanced Status Command Test\n")
    print("=" * 50)
    
    try:
        # Test configuration
        await test_configuration_status()
        
        # Test health checker
        await test_health_checker()
        
        # Test emoji mapping
        test_status_emojis()
        
        print("\n" + "=" * 50)
        print("✅ BOT2 Tests completed successfully!")
        print("\n💡 To test in Telegram:")
        print("  • Try: /status")
        print("  • Try: /status verbose (admin only)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
