"""
Market Data Downloader using yfinance

Downloads historical market data for TQQQ and SQQQ using yfinance library.
Note: yfinance provides aggregated OHLCV data, not tick-level data.
The smallest interval available is 1-minute data.

Usage:
    python download_market_data.py

Configuration:
    Modify the parameters below to customize the data download:
    - SYMBOLS: List of symbols to download
    - INTERVAL: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    - PERIOD: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    - Or use START_DATE and END_DATE for custom date range
"""

import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= Configuration =============
SYMBOLS = ['TQQQ', 'SQQQ']

# Data interval options: 1m, 2m, 5m, 15m, 30m, 60m, 1h, 1d, 5d, 1wk, 1mo, 3mo
# Note: 1m data is only available for the last 7 days (use '7d' for 1m)
# For YTD or longer periods, use 1h (hourly) or 1d (daily) intervals
INTERVAL = '1m'  # Daily data for YTD (use '1h' for hourly, '1m' for last 7 days only)

# For recent data (use PERIOD)
PERIOD = 'ytd'  # Year to date

# For custom date range (comment out PERIOD and uncomment these)
# START_DATE = '2024-01-01'
# END_DATE = '2025-01-14'

# Output directory
DATA_DIR = Path('Data')
OUTPUT_SUBDIR = 'yfinance'  # Will create Data/yfinance/

# ============================================


def create_output_directory():
    """Create output directory structure."""
    output_dir = DATA_DIR / OUTPUT_SUBDIR
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir.absolute()}")
    return output_dir


def download_symbol_data(symbol, interval, period=None, start_date=None, end_date=None):
    """
    Download historical data for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'TQQQ')
        interval: Data interval (e.g., '1m', '1d')
        period: Time period (e.g., '7d', '1mo')
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
    
    Returns:
        pandas DataFrame with OHLCV data
    """
    logger.info(f"Downloading {symbol} data...")
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Download data
        if period:
            df = ticker.history(period=period, interval=interval)
            logger.info(f"  Downloaded {len(df)} rows for period: {period}")
        else:
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            logger.info(f"  Downloaded {len(df)} rows from {start_date} to {end_date}")
        
        if df.empty:
            logger.warning(f"  No data returned for {symbol}")
            return None
        
        # Add symbol column
        df['Symbol'] = symbol
        
        # Clean up the data
        df = df.reset_index()
        
        # Rename 'Datetime' or 'Date' column to 'Timestamp'
        if 'Datetime' in df.columns:
            df = df.rename(columns={'Datetime': 'Timestamp'})
        elif 'Date' in df.columns:
            df = df.rename(columns={'Date': 'Timestamp'})
        
        # Reorder columns for clarity
        cols = ['Timestamp', 'Symbol', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = df[[col for col in cols if col in df.columns]]
        
        logger.info(f"  Data range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        logger.info(f"  Columns: {', '.join(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.error(f"  Error downloading {symbol}: {str(e)}")
        return None


def save_data(df, symbol, output_dir, interval):
    """
    Save DataFrame to CSV file.
    
    Args:
        df: pandas DataFrame with market data
        symbol: Stock symbol
        output_dir: Output directory path
        interval: Data interval (for filename)
    """
    if df is None or df.empty:
        logger.warning(f"No data to save for {symbol}")
        return
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{symbol}_{interval}_{timestamp}.csv"
    filepath = output_dir / filename
    
    # Save to CSV
    df.to_csv(filepath, index=False)
    logger.info(f"Saved to: {filepath}")
    logger.info(f"File size: {filepath.stat().st_size / 1024:.2f} KB")


def save_combined_data(dataframes, output_dir, interval):
    """
    Save combined data for all symbols to a single CSV file.
    
    Args:
        dataframes: Dictionary of {symbol: DataFrame}
        output_dir: Output directory path
        interval: Data interval (for filename)
    """
    # Combine all dataframes
    combined_df = pd.concat(dataframes.values(), ignore_index=True)
    
    # Sort by timestamp and symbol
    combined_df = combined_df.sort_values(['Timestamp', 'Symbol'])
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"combined_TQQQ_SQQQ_{interval}_{timestamp}.csv"
    filepath = output_dir / filename
    
    # Save to CSV
    combined_df.to_csv(filepath, index=False)
    logger.info(f"\nCombined file saved to: {filepath}")
    logger.info(f"Total rows: {len(combined_df)}")
    logger.info(f"File size: {filepath.stat().st_size / 1024:.2f} KB")


def display_summary(dataframes):
    """Display summary statistics for downloaded data."""
    logger.info("\n" + "="*60)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*60)
    
    for symbol, df in dataframes.items():
        if df is not None and not df.empty:
            logger.info(f"\n{symbol}:")
            logger.info(f"  Rows: {len(df)}")
            logger.info(f"  Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
            logger.info(f"  Price range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
            logger.info(f"  Avg volume: {df['Volume'].mean():,.0f}")


def main():
    """Main execution function."""
    logger.info("="*60)
    logger.info("Market Data Downloader - yfinance")
    logger.info("="*60)
    logger.info(f"Symbols: {', '.join(SYMBOLS)}")
    logger.info(f"Interval: {INTERVAL}")
    logger.info(f"Period: {PERIOD if PERIOD else f'{START_DATE} to {END_DATE}'}")
    logger.info("="*60 + "\n")
    
    # Check for yfinance
    try:
        import yfinance
        logger.info(f"yfinance version: {yfinance.__version__}")
    except ImportError:
        logger.error("yfinance not installed. Install with: pip install yfinance")
        return
    
    # Create output directory
    output_dir = create_output_directory()
    
    # Download data for each symbol
    dataframes = {}
    for symbol in SYMBOLS:
        if PERIOD:
            df = download_symbol_data(symbol, INTERVAL, period=PERIOD)
        else:
            df = download_symbol_data(symbol, INTERVAL, 
                                     start_date=START_DATE, end_date=END_DATE)
        
        if df is not None:
            dataframes[symbol] = df
            save_data(df, symbol, output_dir, INTERVAL)
        
        logger.info("")  # Empty line for readability
    
    # Save combined file
    if dataframes:
        save_combined_data(dataframes, output_dir, INTERVAL)
        display_summary(dataframes)
    
    logger.info("\n" + "="*60)
    logger.info("Download complete!")
    logger.info("="*60)
    
    # Important note about 1-minute data
    if INTERVAL == '1m':
        logger.info("\nNOTE: 1-minute data from yfinance is limited to the last 7 days.")
        logger.info("For historical 1-minute data, consider:")
        logger.info("  - Using daily/hourly intervals for longer periods")
        logger.info("  - Downloading data in rolling 7-day windows")
        logger.info("  - Using alternative data sources (Alpaca, IEX, etc.)")
    
    # Add a note about the data interval used
    logger.info(f"\nData saved with {INTERVAL} interval for period: {PERIOD if PERIOD else f'{START_DATE} to {END_DATE}'}")
    logger.info(f"Location: {output_dir.absolute()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Keep window open so you can see the results
        input("\n\nPress Enter to close...")
