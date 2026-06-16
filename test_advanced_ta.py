"""
Test script for Advanced TA features
Tests Volume Profile, Market Regime, and enhanced scoring
"""
import asyncio
import json
from app.services.ta_engine import generate_llm_summary

async def test_advanced_features():
    print("=" * 80)
    print("ADVANCED TECHNICAL ANALYSIS TEST")
    print("=" * 80)
    
    # Test with a BIST stock
    test_tickers = ["THYAO", "ASELS", "EREGL"]
    
    for ticker in test_tickers:
        print(f"\n{'='*80}")
        print(f"Testing: {ticker}")
        print(f"{'='*80}\n")
        
        try:
            result = await generate_llm_summary(ticker)
            
            if "error" in result:
                print(f"❌ Error: {result['error']}")
                continue
            
            print(f"✓ Ticker: {result['ticker']}")
            print(f"✓ Close: {result['close']} TL")
            print(f"✓ Score: {result['score']}/100 (Confidence: {result['confidence']})")
            print(f"✓ Trend: {result['trend']} (Daily) | {result['weekly_trend']} (Weekly)")
            
            # Market Regime
            if "market_regime" in result:
                regime = result['market_regime']
                print(f"\n📊 MARKET REGIME:")
                print(f"   • Type: {regime.get('regime', 'N/A')}")
                print(f"   • Direction: {regime.get('trend_direction', 'N/A')}")
                print(f"   • Volatility: {regime.get('volatility_regime', 'N/A')}")
                print(f"   • ADX: {regime.get('adx', 0):.1f}")
                print(f"   • Strategy: {regime.get('recommended_strategy', 'N/A')[:80]}...")
            
            # Volume Profile
            if "volume_profile" in result:
                vp = result['volume_profile']
                if "error" not in vp:
                    print(f"\n📈 VOLUME PROFILE:")
                    print(f"   • POC (Point of Control): {vp.get('poc', 0):.2f} TL")
                    print(f"   • Value Area High: {vp.get('value_area_high', 0):.2f} TL")
                    print(f"   • Value Area Low: {vp.get('value_area_low', 0):.2f} TL")
            
            # Support/Resistance Zones
            if "support_resistance_zones" in result:
                sr = result['support_resistance_zones']
                if "error" not in sr:
                    print(f"\n🎯 SUPPORT & RESISTANCE:")
                    print(f"   • Current: {sr.get('current_price', 0):.2f} TL")
                    
                    if sr.get('nearest_support'):
                        ns = sr['nearest_support']
                        print(f"   • Nearest Support: {ns['price']:.2f} TL ({ns['type']}, Strength: {ns['strength']}%)")
                    
                    if sr.get('nearest_resistance'):
                        nr = sr['nearest_resistance']
                        print(f"   • Nearest Resistance: {nr['price']:.2f} TL ({nr['type']}, Strength: {nr['strength']}%)")
            
            # Liquidity Voids
            if "liquidity_voids" in result and result['liquidity_voids']:
                print(f"\n⚡ LIQUIDITY VOIDS:")
                for i, void in enumerate(result['liquidity_voids'][:3], 1):
                    print(f"   {i}. {void['gap_start']:.2f} → {void['gap_end']:.2f} TL "
                          f"({void['direction']}, {void['bars_ago']} bars ago)")
            
            # Signals (top 5)
            print(f"\n🔔 TOP SIGNALS:")
            for i, signal in enumerate(result.get('signals', [])[:5], 1):
                print(f"   {i}. {signal}")
            
            # Score Components
            if "score_components" in result:
                comp = result['score_components']
                print(f"\n📊 SCORE BREAKDOWN:")
                print(f"   • Trend: {comp.get('trend', 0)}")
                print(f"   • Momentum: {comp.get('momentum', 0)}")
                print(f"   • Volume: {comp.get('volume', 0)}")
            
            # LLM Summary (first 500 chars)
            if "llm_summary_prompt" in result:
                print(f"\n📝 CHATBOT CONTEXT (Preview):")
                print(result['llm_summary_prompt'][:500] + "...")
            
            print(f"\n{'='*80}")
            
        except Exception as e:
            print(f"❌ Exception for {ticker}: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay between tickers
        await asyncio.sleep(1)
    
    print("\n✅ Advanced TA Test Completed!")

if __name__ == "__main__":
    asyncio.run(test_advanced_features())
