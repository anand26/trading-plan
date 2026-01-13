# TQQQ/SQQQ Trading Dashboard

Streamlit-based performance visualization dashboard for the TQQQ/SQQQ adaptive trading system.

## Features

### 📊 Overview Page
- Key performance metrics (Total P&L, Win Rate, Sharpe Ratio, Max Drawdown)
- Equity curve visualization
- Daily P&L distribution
- Recent trades table

### 📈 Trade Analysis
- Individual trade performance scatter plot
- Win/Loss distribution by time of day
- Trade duration analysis
- Entry/Exit price analysis

### 🎯 Regime Analysis
- Market regime detection visualization
- Regime-based performance breakdown
- RSI and momentum indicators over time
- Regime transition analysis

### 🧠 Learning Insights
- Parameter performance comparison
- Learning history timeline
- Suggested corrections based on recent performance
- Optimal parameter recommendations

### ⚙️ System Status
- Database connection health
- Algorithm deployment status
- Recent backtest results
- System alerts and notifications

## Installation

```bash
# Navigate to dashboard directory
cd dashboard

# Install dependencies
pip install -e .

# Or install directly
pip install streamlit pandas plotly pyodbc python-dotenv
```

## Configuration

Create a `.env` file with your database connection:

```env
DB_SERVER=localhost
DB_NAME=TradingDB
DB_DRIVER=ODBC Driver 17 for SQL Server
```

## Running the Dashboard

```bash
# From dashboard directory
streamlit run src/dashboard/app.py

# Or using the installed command
dashboard
```

The dashboard will be available at `http://localhost:8501`

## Architecture

```
dashboard/
├── src/dashboard/
│   ├── app.py              # Main Streamlit application
│   ├── config.py           # Configuration management
│   ├── database.py         # SQL Server connection
│   ├── pages/
│   │   ├── overview.py     # Overview page
│   │   ├── trades.py       # Trade analysis
│   │   ├── regimes.py      # Regime analysis
│   │   ├── learning.py     # Learning insights
│   │   └── status.py       # System status
│   └── components/
│       ├── charts.py       # Plotly chart components
│       ├── metrics.py      # Metric display components
│       └── tables.py       # Table components
└── pyproject.toml
```

## Data Sources

The dashboard connects to the TradingDB SQL Server database and reads from:

- `dbo.Trades` - Individual trade records
- `dbo.DailyPerformance` - Daily P&L summaries
- `dbo.BacktestRuns` / `dbo.BacktestMetrics` - Backtest results
- `dbo.MarketRegimes` - Market regime classifications
- `dbo.LearningStore` - Learning history
- `dbo.OptimalParameters` - Parameter recommendations
- `dbo.Parameters` - Current algorithm parameters

## Screenshots

*Coming soon*

## License

MIT License
