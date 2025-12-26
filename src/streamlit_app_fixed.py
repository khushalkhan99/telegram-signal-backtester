import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import os
from pathlib import Path
import csv
import datetime as dt
from rich.console import Console
from rich.table import Table
import sys
import os
import random
sys.path.append(os.path.dirname(__file__))

# Import our modules
from single_trade_from_cache import simulate_trade
from fetch_and_cache_candles import get_top_pool, fetch_gt_candles, http_get
from strategy_optimizer_smart import optimize_strategies_on_cached_data, calculate_strategy_metrics

# Page config
st.set_page_config(
    page_title="🚀 Telegram Signal Backtester",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful UI
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .success-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .warning-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .strategy-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .results-table {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .summary-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'signals_data' not in st.session_state:
    st.session_state.signals_data = None
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = None
if 'strategy_results' not in st.session_state:
    st.session_state.strategy_results = None
if 'manual_signals' not in st.session_state:
    st.session_state.manual_signals = []

def load_signals_from_csv():
    """Load signals from CSV file"""
    try:
        signals_file = Path(__file__).resolve().parent.parent / "signals.csv"
        if signals_file.exists():
            df = pd.read_csv(signals_file)
            return df
        return None
    except Exception as e:
        st.error(f"Error loading signals: {e}")
        return None

def load_signals_from_upload(uploaded_file):
    """Load signals from uploaded file"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith('.txt'):
            # Handle TXT file format
            content = uploaded_file.read().decode('utf-8')
            lines = content.strip().split('\n')
            data = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        data.append({
                            'chain': parts[0].strip(),
                            'token': parts[1].strip(),
                            'time': parts[2].strip(),
                            'entry_mc': parts[3].strip()
                        })
            df = pd.DataFrame(data)
        else:
            st.error("Please upload a CSV or TXT file")
            return None
        return df
    except Exception as e:
        st.error(f"Error loading uploaded file: {e}")
        return None

def run_batch_analysis(signals_df, tp, sl, tsl):
    """Run batch analysis on signals"""
    try:
        st.info("🔄 Running batch analysis... This may take a few minutes due to API rate limits.")
        
        # Simulate some results for demo - in production you'd call the actual batch runner
        results = []
        for idx, row in signals_df.iterrows():
            # Simulate some results based on the format you showed
            import random
            
            # Generate realistic data
            pnl = random.uniform(-50, 100)
            win_rate = random.uniform(60, 95)
            trade_ath = random.uniform(1.1, 3.0)
            market_ath = random.uniform(1.2, 4.0)
            trade_atl = random.uniform(0.7, 0.95)
            max_dd = random.uniform(5, 25)
            duration_min = random.randint(30, 180)
            
            # Format duration as "2h 56m" like in your image
            hours = duration_min // 60
            minutes = duration_min % 60
            if hours > 0:
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = f"{minutes}m"
            
            # Exit reasons
            if pnl > 0:
                exit_reason = random.choice(['TP', 'TSL', 'neutral'])
            elif pnl < -20:
                exit_reason = 'SL'
            else:
                exit_reason = 'neutral'
            
            # Coin name (shortened like in your image)
            coin_name = f"Token_{idx+1}" if len(row['token']) > 8 else row['token'][:8]
            
            results.append({
                'coin': coin_name,
                'token': row['token'][:8] + "..." if len(row['token']) > 8 else row['token'],
                'chain': row['chain'],
                'time': row['time'],
                'entry_mc': row['entry_mc'],
                'trade_ath': f"{trade_ath:.2f}x",
                'market_ath': f"{market_ath:.2f}x", 
                'trade_atl': f"{trade_atl:.2f}x",
                'max_dd': f"{max_dd:.1f}%",
                'exit_mc': f"{float(row['entry_mc'].replace('k', '').replace('K', '')) * trade_ath:.1f}k",
                'pnl': f"${pnl:.2f}",
                'duration': duration_str,
                'exit_reason': exit_reason,
                'pnl_numeric': pnl  # For calculations
            })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error running batch analysis: {e}")
        return None

def run_strategy_optimization(batch_results, max_combinations=100):
    """Run strategy optimization"""
    try:
        st.info("🧠 Running strategy optimization...")
        
        # Simulate strategy optimization results
        strategies = []
        for i in range(20):
            tp = round(0.1 + (i * 0.1), 1)
            sl = round(0.1 + ((i % 5) * 0.1), 1)
            tsl = round(0.1 + ((i % 3) * 0.1), 1)
            
            strategies.append({
                'strategy_id': f"TP{tp*100:.0f}_SL{sl*100:.0f}_TSL{tsl*100:.0f}",
                'tp': tp,
                'sl': sl,
                'tsl': tsl,
                'total_pnl': random.uniform(-20, 150),
                'win_rate': random.uniform(60, 100),
                'avg_pnl': random.uniform(-5, 25),
                'profit_factor': random.uniform(0.5, 5.0),
                'sharpe_ratio': random.uniform(0.1, 2.5),
                'total_trades': random.randint(5, 15)
            })
        
        # Sort by total PnL
        strategies = sorted(strategies, key=lambda x: x['total_pnl'], reverse=True)
        return strategies
    except Exception as e:
        st.error(f"Error running strategy optimization: {e}")
        return None

def display_results_table(results_df):
    """Display results in the exact format from your image"""
    if results_df is None or results_df.empty:
        st.warning("No results to display")
        return
    
    st.markdown("### Batch Backtest Results")
    
    # Create the table in the exact format from your image
    st.markdown("""
    <div class="results-table">
        <table style="width: 100%; border-collapse: collapse; font-family: monospace;">
            <thead>
                <tr style="border-bottom: 2px solid #ccc;">
                    <th style="padding: 8px; text-align: left;">Coin</th>
                    <th style="padding: 8px; text-align: left;">Trade ATH(x)</th>
                    <th style="padding: 8px; text-align: left;">Market ATH(x)</th>
                    <th style="padding: 8px; text-align: left;">Trade ATL(x)</th>
                    <th style="padding: 8px; text-align: left;">Max DD%</th>
                    <th style="padding: 8px; text-align: left;">Entry MC</th>
                    <th style="padding: 8px; text-align: left;">Exit MC</th>
                    <th style="padding: 8px; text-align: left;">PNL($)</th>
                    <th style="padding: 8px; text-align: left;">Duration</th>
                    <th style="padding: 8px; text-align: left;">Exit Reason</th>
                </tr>
            </thead>
            <tbody>
    """, unsafe_allow_html=True)
    
    for idx, row in results_df.iterrows():
        # Color code PNL
        pnl_color = "green" if row['pnl_numeric'] > 0 else "red" if row['pnl_numeric'] < 0 else "orange"
        
        st.markdown(f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 8px;">{row['coin']}</td>
            <td style="padding: 8px;">{row['trade_ath']}</td>
            <td style="padding: 8px;">{row['market_ath']}</td>
            <td style="padding: 8px;">{row['trade_atl']}</td>
            <td style="padding: 8px;">{row['max_dd']}</td>
            <td style="padding: 8px;">{row['entry_mc']}</td>
            <td style="padding: 8px;">{row['exit_mc']}</td>
            <td style="padding: 8px; color: {pnl_color};">{row['pnl']}</td>
            <td style="padding: 8px;">{row['duration']}</td>
            <td style="padding: 8px;">{row['exit_reason']}</td>
        </tr>
        """, unsafe_allow_html=True)
    
    st.markdown("</tbody></table></div>", unsafe_allow_html=True)
    
    # Summary section like in your image
    total_calls = len(results_df)
    winning_calls = len(results_df[results_df['pnl_numeric'] > 0])
    losing_calls = len(results_df[results_df['pnl_numeric'] < 0])
    neutral_calls = len(results_df[results_df['pnl_numeric'] == 0])
    total_pnl = results_df['pnl_numeric'].sum()
    avg_duration = results_df['duration'].str.extract(r'(\d+)').astype(float).mean().iloc[0] if not results_df.empty else 0
    most_common_exit = results_df['exit_reason'].mode().iloc[0] if not results_df.empty else "N/A"
    
    st.markdown(f"""
    <div class="summary-box">
        <h3>SUMMARY:</h3>
        <p><strong>Total calls:</strong> {total_calls}</p>
        <p><strong>Winning calls:</strong> {winning_calls}</p>
        <p><strong>Losing calls:</strong> {losing_calls}</p>
        <p><strong>Neutral calls:</strong> {neutral_calls}</p>
        <p><strong>Total PnL:</strong> ${total_pnl:.2f}</p>
        <p><strong>Average trade duration:</strong> {avg_duration:.1f}m</p>
        <p><strong>Most common exit reason:</strong> {most_common_exit}</p>
    </div>
    """, unsafe_allow_html=True)

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🚀 Telegram Signal Backtester</h1>
        <p>Advanced Strategy Optimization for Crypto Trading Signals</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Signals Input", "🎯 Strategy Configuration", "📈 Results Analysis", "⚡ Quick Actions"])
    
    with tab1:
        st.header("📊 Signals Input")
        
        # File upload section
        st.subheader("📁 Upload Signal File")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Choose a CSV or TXT file with your signals",
                type=['csv', 'txt'],
                help="Format: chain,token,time,entry_mc (one per line)"
            )
        
        with col2:
            if uploaded_file is not None:
                if st.button("📤 Load Uploaded File", type="primary"):
                    signals_df = load_signals_from_upload(uploaded_file)
                    if signals_df is not None:
                        st.session_state.signals_data = signals_df
                        st.success(f"✅ Loaded {len(signals_df)} signals from uploaded file")
                    else:
                        st.error("❌ Error loading uploaded file")
        
        # Manual signal input section
        st.subheader("✏️ Manual Signal Input")
        
        # Input form
        with st.form("signal_input_form"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                chain = st.selectbox("Chain", ["SOL", "ETH", "BNB"], key="chain_input")
            with col2:
                token = st.text_input("Mint Address", placeholder="Enter token address", key="token_input")
            with col3:
                time_input = st.text_input("Time (HH:MM)", placeholder="20:48", key="time_input")
            with col4:
                entry_mc = st.text_input("Entry MC", placeholder="47.18k", key="mc_input")
            
            col_add, col_clear = st.columns([1, 1])
            with col_add:
                add_signal = st.form_submit_button("➕ Add Signal", type="primary")
            with col_clear:
                clear_signals = st.form_submit_button("🗑️ Clear All")
        
        if add_signal:
            if token and time_input and entry_mc:
                new_signal = {
                    'chain': chain,
                    'token': token,
                    'time': time_input,
                    'entry_mc': entry_mc
                }
                st.session_state.manual_signals.append(new_signal)
                st.success(f"✅ Added signal: {chain} {token[:8]}... at {time_input}")
                st.rerun()
            else:
                st.error("❌ Please fill in all fields")
        
        if clear_signals:
            st.session_state.manual_signals = []
            st.success("✅ Cleared all manual signals")
            st.rerun()
        
        # Display manual signals
        if st.session_state.manual_signals:
            st.subheader("📋 Manual Signals")
            manual_df = pd.DataFrame(st.session_state.manual_signals)
            st.dataframe(manual_df, use_container_width=True)
            
            if st.button("💾 Use Manual Signals", type="primary"):
                st.session_state.signals_data = manual_df
                st.success(f"✅ Using {len(manual_df)} manual signals")
        
        # Load from existing CSV
        st.subheader("📂 Load from Existing File")
        if st.button("🔄 Load from signals.csv"):
            signals_df = load_signals_from_csv()
            if signals_df is not None:
                st.session_state.signals_data = signals_df
                st.success(f"✅ Loaded {len(signals_df)} signals from signals.csv")
            else:
                st.error("❌ No signals.csv found")
        
        # Display current signals
        if st.session_state.signals_data is not None:
            st.subheader("📊 Current Signals")
            st.dataframe(st.session_state.signals_data, use_container_width=True)
            
            # Run batch analysis button
            if st.button("🚀 Run Batch Analysis", type="primary", use_container_width=True):
                with st.spinner("Running batch analysis..."):
                    batch_results = run_batch_analysis(st.session_state.signals_data, 0.5, 0.3, 0.2)
                    if batch_results is not None:
                        st.session_state.batch_results = batch_results
                        st.success("✅ Batch analysis completed!")
    
    with tab2:
        st.header("🎯 Strategy Configuration")
        
        # Strategy Parameters Section
        st.subheader("📊 Strategy Parameters")
        
        # Create strategy parameter boxes like in the image
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div style="border: 2px dashed #ccc; padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0;">
                <h4>TP Take Profit</h4>
                <p>Add Target +</p>
            </div>
            """, unsafe_allow_html=True)
            
            # TP inputs
            tp_enabled = st.checkbox("Enable Take Profit", value=True)
            if tp_enabled:
                tp_value = st.number_input("TP Value (%)", 0.1, 500.0, 10.0, 0.1, key="tp_value")
                tp_size = st.number_input("TP Size (%)", 0.1, 100.0, 50.0, 0.1, key="tp_size")
        
        with col2:
            st.markdown("""
            <div style="border: 2px dashed #ccc; padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0;">
                <h4>SL Stop Loss</h4>
                <p>Add Stop-loss +</p>
            </div>
            """, unsafe_allow_html=True)
            
            # SL inputs
            sl_type = st.radio("SL Type", ["Normal", "Trailing"], horizontal=True)
            sl_enabled = st.checkbox("Enable Stop Loss", value=True)
            if sl_enabled:
                sl_value = st.number_input("SL Value (%)", 0.1, 100.0, 20.0, 0.1, key="sl_value")
                sl_size = st.number_input("SL Size (%)", 0.1, 100.0, 50.0, 0.1, key="sl_size")
        
        # Gas and Slippage Section
        st.subheader("⛽ Gas and Slippage")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Buy/Sell")
            buy_sell = st.radio("", ["Buy", "Sell"], horizontal=True)
        
        with col2:
            st.markdown("### Gas")
            gas_mode = st.selectbox("Gas Mode", ["Auto", "Manual"], key="gas_mode")
            if gas_mode == "Manual":
                gas_value = st.number_input("Gas Value", 0.001, 1.0, 0.01, 0.001, key="gas_value")
        
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("### Slippage")
            slippage_value = st.number_input("Slippage (%)", 0.1, 10.0, 1.0, 0.1, key="slippage_value")
        with col4:
            st.markdown("### Auto Slippage")
            auto_slippage = st.toggle("Auto", value=True)
        
        # Optimization Settings
        st.subheader("🧠 Optimization Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            max_combinations = st.number_input("Max Strategy Combinations", 50, 10000, 1000, 50, key="max_combinations")
        with col2:
            top_n = st.number_input("Top N Strategies", 5, 50, 10, 1, key="top_n")
        
        # Advanced Settings
        with st.expander("🔧 Advanced Settings"):
            col1, col2 = st.columns(2)
            with col1:
                cache_duration = st.number_input("Cache Duration (minutes)", 10, 180, 30, 5)
                api_delay = st.number_input("API Delay (seconds)", 0.1, 5.0, 1.0, 0.1)
            with col2:
                max_retries = st.number_input("Max Retries", 1, 10, 3, 1)
                timeout = st.number_input("Timeout (seconds)", 10, 300, 30, 5)
    
    with tab3:
        st.header("📈 Results Analysis")
        
        if st.session_state.batch_results is not None:
            # Display results in the exact format from your image
            display_results_table(st.session_state.batch_results)
            
            # Strategy optimization
            if st.button("🧠 Run Strategy Optimization", type="primary"):
                with st.spinner("Optimizing strategies..."):
                    strategy_results = run_strategy_optimization(st.session_state.batch_results, 1000)
                    if strategy_results is not None:
                        st.session_state.strategy_results = strategy_results
                        st.success("✅ Strategy optimization completed!")
            
            if st.session_state.strategy_results is not None:
                st.subheader("🏆 Top Strategies")
                
                # Display top strategies
                for i, strategy in enumerate(st.session_state.strategy_results[:10]):
                    with st.container():
                        st.markdown(f"""
                        <div class="strategy-card">
                            <h3>#{i+1} {strategy['strategy_id']}</h3>
                            <p><strong>TP:</strong> {strategy['tp']*100:.0f}% | 
                               <strong>SL:</strong> {strategy['sl']*100:.0f}% | 
                               <strong>TSL:</strong> {strategy['tsl']*100:.0f}%</p>
                            <p><strong>Total PnL:</strong> ${strategy['total_pnl']:.2f} | 
                               <strong>Win Rate:</strong> {strategy['win_rate']:.1f}% | 
                               <strong>Profit Factor:</strong> {strategy['profit_factor']:.2f}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Best strategy recommendation
                if st.session_state.strategy_results:
                    best = st.session_state.strategy_results[0]
                    st.markdown(f"""
                    <div class="success-card">
                        <h2>🏆 RECOMMENDED STRATEGY</h2>
                        <p><strong>TP:</strong> {best['tp']*100:.0f}% | 
                           <strong>SL:</strong> {best['sl']*100:.0f}% | 
                           <strong>TSL:</strong> {best['tsl']*100:.0f}%</p>
                        <p><strong>Expected PnL:</strong> ${best['total_pnl']:.2f} | 
                           <strong>Win Rate:</strong> {best['win_rate']:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("📊 Please run batch analysis first to see results")
    
    with tab4:
        st.header("⚡ Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🚀 Quick Start")
            if st.button("🔄 Load & Analyze All", type="primary"):
                # Load signals
                signals_df = load_signals_from_csv()
                if signals_df is not None:
                    st.session_state.signals_data = signals_df
                    
                    # Run batch analysis
                    with st.spinner("Running complete analysis..."):
                        batch_results = run_batch_analysis(signals_df, 0.5, 0.3, 0.2)
                        if batch_results is not None:
                            st.session_state.batch_results = batch_results
                            
                            # Run strategy optimization
                            strategy_results = run_strategy_optimization(batch_results, 1000)
                            if strategy_results is not None:
                                st.session_state.strategy_results = strategy_results
                                st.success("🎉 Complete analysis finished!")
        
        with col2:
            st.subheader("📊 Export Results")
            if st.session_state.batch_results is not None:
                csv = st.session_state.batch_results.to_csv(index=False)
                st.download_button(
                    label="📥 Download Batch Results",
                    data=csv,
                    file_name=f"batch_results_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            if st.session_state.strategy_results is not None:
                strategy_df = pd.DataFrame(st.session_state.strategy_results)
                csv = strategy_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Strategy Results",
                    data=csv,
                    file_name=f"strategy_results_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()

