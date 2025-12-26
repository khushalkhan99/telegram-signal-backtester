# 🚀 Telegram Signal Backtester

Advanced strategy optimization system for crypto trading signals with beautiful Streamlit interface.

## ✨ Features

- **📊 Signal Analysis**: Load and analyze Telegram trading signals
- **🎯 Strategy Optimization**: Test 50k+ strategy combinations automatically  
- **📈 Performance Charts**: Beautiful visualizations and metrics
- **⚡ Quick Actions**: One-click analysis and export
- **🎨 Modern UI**: Beautiful Streamlit interface with gradients and animations

## 🚀 Quick Start

### Option 1: Launch App (Recommended)
```bash
python launch_app.py
```

### Option 2: Direct Streamlit
```bash
streamlit run src/streamlit_app.py
```

### Option 3: Command Line
```bash
# Run batch analysis
python src/batch_trade_runner.py --input signals.csv --tp 0.5 --sl 0.3 --tsl 0.2

# Run strategy optimization  
python src/strategy_optimizer_smart.py --max-combinations 1000 --top-n 10
```

## 📋 Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Add Your Signals**:
   - Edit `signals.csv` with your Telegram signals
   - Format: `chain,token,time,entry_mc`

3. **Run Analysis**:
   - Use the beautiful Streamlit interface
   - Or run command line tools

## 📊 Signal Format

Your `signals.csv` should look like:
```csv
chain,token,time,entry_mc
SOL,8NneNgCVZQ9i6MK2R7TRgYWv8QceCoeaR2NFWrGxpump,20:48,47.18k
SOL,FLAPDjcAgUBN9QQJXui7mZFZrj6Yt7CmRD3wjHcSpump,19:35,82.06k
```

## 🎯 Strategy Optimization

The system automatically tests:
- **TP (Take Profit)**: 10% to 500%
- **SL (Stop Loss)**: 5% to 100%  
- **TSL (Trailing Stop Loss)**: 5% to 100%

## 📈 Key Metrics

- **Total PnL**: Total profit/loss across all trades
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Maximum loss from peak

## 🏆 Best Strategy Output

The system finds the optimal strategy for your channel:
```
🏆 BEST STRATEGY:
TP: 10% | SL: 100% | TSL: 70%
Total PnL: $4.63 | Win Rate: 100.0%
Profit Factor: ∞ | Sharpe Ratio: 0.00
```

## 🎨 Beautiful Interface

- **Modern Design**: Gradient backgrounds and smooth animations
- **Real-time Updates**: Live progress bars and status updates
- **Interactive Charts**: Plotly visualizations with hover details
- **Responsive Layout**: Works on desktop and mobile
- **Dark/Light Themes**: Automatic theme detection

## ⚡ Performance

- **Smart Caching**: 30-minute cache per signal (API efficient)
- **Rate Limit Safe**: No API spam, respects limits
- **Fast Optimization**: Tests 1000+ strategies in seconds
- **Memory Efficient**: Optimized for large datasets

## 🔧 Advanced Usage

### Custom Strategy Testing
```python
# Test your own strategies
python src/simple_strategy_tester.py --input signals.csv --max-strategies 50
```

### Batch Processing
```python
# Process multiple signal files
python src/batch_trade_runner.py --input signals.csv --tp 0.2 --sl 0.1 --tsl 0.15
```

## 📁 Project Structure

```
tg_backtester/
├── src/
│   ├── streamlit_app.py          # Beautiful web interface
│   ├── batch_trade_runner.py     # Batch signal processing
│   ├── strategy_optimizer_smart.py # Strategy optimization
│   ├── single_trade_from_cache.py # Trade simulation
│   └── fetch_and_cache_candles.py # Data fetching
├── signals.csv                    # Your trading signals
├── out/                          # Results and exports
├── cache/                        # Cached market data
├── launch_app.py                # Quick launcher
└── requirements.txt             # Dependencies
```

## 🎯 Use Cases

1. **Channel Analysis**: Find best strategy for each Telegram channel
2. **Signal Validation**: Test signals before using in live trading
3. **Strategy Research**: Discover profitable trading patterns
4. **Risk Management**: Optimize stop losses and take profits
5. **Performance Tracking**: Monitor strategy effectiveness over time

## 🚀 Next Steps

1. **Load Your Signals**: Add signals to `signals.csv`
2. **Run Analysis**: Use the Streamlit interface
3. **Find Best Strategy**: Get optimal TP/SL/TSL parameters
4. **Implement in Bot**: Use the recommended strategy
5. **Monitor Results**: Track performance over 2 days

## 💡 Tips

- **Start Small**: Test with 5-10 signals first
- **Use Cached Data**: Avoid API rate limits
- **Monitor Performance**: Check results after 2 days
- **Adjust Parameters**: Fine-tune based on results
- **Export Data**: Save results for analysis

---

**🎉 Ready to optimize your trading strategies!**

