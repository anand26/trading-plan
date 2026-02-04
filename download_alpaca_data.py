"""
Alpaca Market Data Downloader

Downloads 1-minute historical bar data for TQQQ and SQQQ using Alpaca API.
Alpaca provides up to several years of 1-minute data for free.

Usage:
    python download_alpaca_data.py

Requirements:
    - Valid Alpaca API credentials in .env file
    - alpaca-py library installed
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# ============= Configuration =============
SYMBOLS = ['TQQQ', 'SQQQ', 'QQQ']

# Data interval - Alpaca supports: Minute, Hour, Day
# Note: Minute data is available for several years from Alpaca (unlike yfinance's 7-day limit)
INTERVAL = '1m'  # 1-minute data for YTD (use '1h' for hourly, '1d' for daily)

# Alpaca API credentials
API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')

# Date range for download
# Alpaca allows up to several years of 1-minute data
# For YTD: start from January 1 of current year
START_DATE = datetime(2026, 1, 1)  # YTD
END_DATE = datetime.now()

# Output directory
DATA_DIR = Path('Data')
OUTPUT_SUBDIR = 'alpaca'  # Will create Data/alpaca/

# ============================================


def validate_credentials():
    """Validate that Alpaca credentials are configured."""
    if not API_KEY or not SECRET_KEY:
        logger.error("Alpaca API credentials not found!")
        logger.error("Please configure ALPACA_API_KEY and ALPACA_SECRET_KEY in your .env file")
        return False
    
    if 'PASTE_YOUR' in API_KEY or 'PASTE_YOUR' in SECRET_KEY:
        logger.error("Please replace placeholder values in .env with your actual Alpaca API credentials")
        return False
    
    return True


def create_output_directory():
    """Create output directory structure."""
    output_dir = DATA_DIR / OUTPUT_SUBDIR
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir.absolute()}")
    return output_dir


def download_minute_bars(symbol, start_date, end_date, client):
    """
    Download 1-minute bar data for a symbol from Alpaca.
    
    Args:
        symbol: Stock symbol (e.g., 'TQQQ')
        start_date: Start datetime
        end_date: End datetime
        client: Alpaca StockHistoricalDataClient
    
    Returns:
        pandas DataFrame with OHLCV data
    """
    logger.info(f"Downloading {symbol} 1-minute bars...")
    logger.info(f"  Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    try:
        # Create request for 1-minute bars
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_date,
            end=end_date
        )
        
        # Fetch the data
        bars = client.get_stock_bars(request_params)
        
        # Convert to DataFrame
        df = bars.df
        
        if df.empty:
            logger.warning(f"  No data returned for {symbol}")
            return None
        
        # Reset index to get timestamp and symbol as columns
        df = df.reset_index()
        
        # Rename columns for consistency
        df = df.rename(columns={
            'timestamp': 'Timestamp',
            'symbol': 'Symbol',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'trade_count': 'TradeCount',
            'vwap': 'VWAP'
        })
        
        logger.info(f"  Downloaded {len(df)} 1-minute bars")
        logger.info(f"  Data range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        logger.info(f"  Columns: {', '.join(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.error(f"  Error downloading {symbol}: {str(e)}")
        return None


def save_data(df, symbol, output_dir):
    """
    Save DataFrame to CSV file.
    
    Args:
        df: pandas DataFrame with market data
        symbol: Stock symbol
        output_dir: Output directory path
    """
    if df is None or df.empty:
        logger.warning(f"No data to save for {symbol}")
        return
    
    # Create filename with date range
    start_date = df['Timestamp'].min().strftime('%Y%m%d')
    end_date = df['Timestamp'].max().strftime('%Y%m%d')
    filename = f"{symbol}_1min_{start_date}_{end_date}.csv"
    filepath = output_dir / filename
    
    # Save to CSV
    df.to_csv(filepath, index=False)
    logger.info(f"Saved to: {filepath}")
    logger.info(f"File size: {filepath.stat().st_size / 1024:.2f} KB")


def save_combined_data(dataframes, output_dir):
    """
    Save combined data for all symbols to a single CSV file.
    
    Args:
        dataframes: Dictionary of {symbol: DataFrame}
        output_dir: Output directory path
    """
    if not dataframes:
        return
    
    # Combine all dataframes
    combined_df = pd.concat(dataframes.values(), ignore_index=True)
    
    # Sort by timestamp and symbol
    combined_df = combined_df.sort_values(['Timestamp', 'Symbol'])
    
    # Create filename with date range
    start_date = combined_df['Timestamp'].min().strftime('%Y%m%d')
    end_date = combined_df['Timestamp'].max().strftime('%Y%m%d')
    filename = f"combined_TQQQ_SQQQ_1min_{start_date}_{end_date}.csv"
    filepath = output_dir / filename
    
    # Save to CSV
    combined_df.to_csv(filepath, index=False)
    logger.info(f"\nCombined file saved to: {filepath}")
    logger.info(f"Total rows: {len(combined_df):,}")
    logger.info(f"File size: {filepath.stat().st_size / (1024*1024):.2f} MB")


def display_summary(dataframes):
    """Display summary statistics for downloaded data."""
    logger.info("\n" + "="*60)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*60)
    
    for symbol, df in dataframes.items():
        if df is not None and not df.empty:
            logger.info(f"\n{symbol}:")
            logger.info(f"  Bars: {len(df):,}")
            logger.info(f"  Date range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
            logger.info(f"  Price range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
            logger.info(f"  Avg volume: {df['Volume'].mean():,.0f}")
            if 'TradeCount' in df.columns:
                logger.info(f"  Avg trades per bar: {df['TradeCount'].mean():.1f}")


def main():
    """Main execution function."""
    logger.info("="*60)
    logger.info("Alpaca Market Data Downloader - 1-Minute Bars")
    logger.info("="*60)
    logger.info(f"Symbols: {', '.join(SYMBOLS)}")
    logger.info(f"Date range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    logger.info("="*60 + "\n")
    
    # Validate credentials
    if not validate_credentials():
        return
    
    # Create output directory
    output_dir = create_output_directory()
    
    # Initialize Alpaca client
    try:
        logger.info("Connecting to Alpaca...")
        client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
        logger.info("✓ Connected to Alpaca successfully\n")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {str(e)}")
        return
    
    # Download data for each symbol
    dataframes = {}
    for symbol in SYMBOLS:
        df = download_minute_bars(symbol, START_DATE, END_DATE, client)
        
        if df is not None:
            dataframes[symbol] = df
            save_data(df, symbol, output_dir)
        
        logger.info("")  # Empty line for readability
    
    # Save combined file
    if dataframes:
        save_combined_data(dataframes, output_dir)
        display_summary(dataframes)
    
    logger.info("\n" + "="*60)
    logger.info("Download complete!")
    logger.info("="*60)
    logger.info(f"\nData location: {output_dir.absolute()}")
    
    # Calculate total days and expected bars
    total_days = (END_DATE - START_DATE).days
    trading_hours = 6.5  # Market hours per day
    expected_bars_per_day = trading_hours * 60  # 390 bars per trading day
    logger.info(f"\nTime period: {total_days} calendar days")
    logger.info(f"Expected bars per trading day: ~{expected_bars_per_day:.0f}")


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

